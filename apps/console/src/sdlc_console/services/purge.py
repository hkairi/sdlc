"""Purge de rétention : données anciennes, logs et rapports, audit exclu."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from ..models import (
    AuditEvent,
    Commit,
    Deployment,
    GateRun,
    IngestionRun,
    Project,
    Repository,
    TaskRun,
    utc_now,
)
from .audit import anchor_audit, append_audit, reseal_audit_event, verify_audit_chain
from .backup import list_backups

DEFAULT_RETENTION_DAYS = 365
PURGE_TABLES = (
    ("commits", Commit, "committed_at"),
    ("deployments", Deployment, "started_at"),
    ("task_runs", TaskRun, "started_at"),
    ("gate_runs", GateRun, "created_at"),
    ("ingestion_runs", IngestionRun, "started_at"),
)


class PurgeError(ValueError):
    """Purge refusée ou impossible."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def retention_days(config: Mapping[str, Any] | None) -> int:
    config = config or {}
    retention = config.get("retention")
    retention = retention if isinstance(retention, Mapping) else {}
    quality = config.get("quality")
    quality = quality if isinstance(quality, Mapping) else {}
    data = quality.get("data")
    data = data if isinstance(data, Mapping) else {}
    value = retention.get("default_days", data.get("retention_days"))
    return int(value) if isinstance(value, int) and value > 0 else DEFAULT_RETENTION_DAYS


def _backup_guard(backups_dir: str | Path) -> dict[str, Any]:
    listing = list_backups(backups_dir)
    latest = listing.get("latest")
    if not isinstance(latest, dict):
        raise PurgeError(
            "backup_too_old",
            "purge refusée : aucune sauvegarde vérifiée disponible",
        )
    if not latest.get("verified"):
        raise PurgeError("backup_invalid", "purge refusée : sauvegarde non vérifiée")
    if latest.get("fresh") is False:
        raise PurgeError(
            "backup_too_old",
            f"purge refusée : sauvegarde âgée de {latest.get('age_hours')} h (> 24 h)",
        )
    return latest


def _ingestion_running(session: Session, project: Project) -> bool:
    return bool(
        session.scalar(
            select(func.count(IngestionRun.id)).where(
                IngestionRun.project_id == project.id,
                IngestionRun.status == "running",
            )
        )
    )


def _delete_old_rows(
    session: Session,
    project: Project,
    cutoff: datetime,
) -> dict[str, int]:
    deleted: dict[str, int] = {}
    for label, model, field_name in PURGE_TABLES:
        field = getattr(model, field_name)
        condition = field < cutoff
        if field_name == "started_at":
            imported = getattr(model, "imported_at", None)
            condition = or_(field < cutoff, field.is_(None))
            if imported is not None:
                condition = or_(
                    field < cutoff,
                    and_(field.is_(None), imported < cutoff),
                )
        if model is Commit:
            repository_ids = select(Repository.id).where(Repository.project_id == project.id)
            result = session.execute(
                delete(Commit).where(
                    Commit.repository_id.in_(repository_ids),
                    Commit.committed_at < cutoff,
                )
            )
        else:
            project_column = model.project_id  # type: ignore[union-attr]
            result = session.execute(
                delete(model).where(
                    project_column == project.id,
                    condition,
                )
            )
        deleted[label] = int(getattr(result, "rowcount", 0) or 0)
    return deleted


def _delete_old_files(root: Path, cutoff: datetime) -> list[str]:
    deleted: list[str] = []
    for directory_name in ("reports", "logs"):
        directory = root / directory_name
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            except OSError:
                continue
            if modified < cutoff:
                try:
                    path.unlink()
                    deleted.append(path.relative_to(root).as_posix())
                except OSError:
                    continue
    return deleted


def run_purge(
    session: Session,
    project: Project,
    *,
    backups_dir: str | Path,
    config: Mapping[str, Any] | None = None,
    root: str | Path | None = None,
    confirm: bool = False,
    actor_label: str = "purge depuis le poste local",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Exécute une purge standard ; l'audit n'est jamais inclus."""
    if not confirm:
        raise PurgeError("confirmation_required", "confirmation explicite requise")
    if _ingestion_running(session, project):
        raise PurgeError("purge_busy", "une ingestion est en cours ; purge refusée")
    latest = _backup_guard(backups_dir)
    chain = verify_audit_chain(session, project.id)
    if not chain["valid"]:
        raise PurgeError(
            "audit_invalid",
            "chaîne d'audit invalide ; purge refusée : " + "; ".join(chain["issues"]),
        )
    days = retention_days(config)
    moment = now or utc_now()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    cutoff = moment - timedelta(days=days)
    deleted = _delete_old_rows(session, project, cutoff)
    root_path = Path(root or Path.cwd()).resolve()
    files = _delete_old_files(root_path, cutoff)
    event = append_audit(
        session,
        project_id=project.id,
        action="purge.completed",
        object_type="project",
        object_id=project.id,
        actor_label=actor_label,
        payload={
            "cutoff": cutoff.isoformat(),
            "retention_days": days,
            "deleted": deleted,
            "files_deleted": files,
            "backup_id": latest.get("id"),
            "audit_excluded": True,
        },
    )
    session.flush()
    return {
        "status": "done",
        "cutoff": cutoff.isoformat(),
        "retention_days": days,
        "deleted": deleted,
        "files_deleted": files,
        "backup": {
            "id": latest.get("id"),
            "age_hours": latest.get("age_hours"),
        },
        "audit_event_id": event.id,
        "audit_excluded": True,
    }


def run_audit_purge(
    session: Session,
    project: Project,
    *,
    cutoff: datetime | None = None,
    actor_label: str = "purge d'audit locale",
) -> dict[str, Any]:
    """Ancre la chaîne puis supprime les événements antérieurs à la coupure."""
    moment = cutoff or (utc_now() - timedelta(days=DEFAULT_RETENTION_DAYS))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    anchor = anchor_audit(
        session,
        project.id,
        actor_label=actor_label,
        reason="purge explicite de l'audit",
    )
    result = session.execute(
        delete(AuditEvent).where(
            AuditEvent.project_id == project.id,
            AuditEvent.created_at < moment,
            AuditEvent.id != anchor.id,
        )
    )
    # L'ancre conservée devient le premier maillon de la nouvelle génération.
    reseal_audit_event(anchor, generation=anchor.generation + 1)
    session.flush()
    check = verify_audit_chain(session, project.id)
    if not check["valid"]:
        raise PurgeError("audit_invalid", "; ".join(check["issues"]))
    return {
        "status": "done",
        "deleted": int(getattr(result, "rowcount", 0) or 0),
        "anchor_event_id": anchor.id,
        "integrity": check,
    }
