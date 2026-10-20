"""Dérogations datées sur un gate, un run ou un finding."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from ..models import GateFinding, GateRun, GateWaiverRecord, Project, utc_now
from .audit import append_audit

TARGET_TYPES = frozenset({"gate", "gate_run", "finding"})


class WaiverError(ValueError):
    """Dérogation invalide."""


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def waiver_status(record: GateWaiverRecord, now: datetime | None = None) -> str:
    moment = _utc(now or utc_now())
    if record.revoked_at is not None:
        return "revoked"
    return "expired" if _utc(record.expires_at) <= moment else "active"


def waiver_data(record: GateWaiverRecord, now: datetime | None = None) -> dict[str, Any]:
    return {
        "id": record.id,
        "gate_key": record.gate_key,
        "target_type": record.target_type,
        "target_id": record.target_id,
        "reason": record.reason,
        "owner": record.owner,
        "approver": record.approver,
        "expires_at": _utc(record.expires_at).isoformat(),
        "created_at": _utc(record.created_at).isoformat(),
        "status": waiver_status(record, now),
        "active": waiver_status(record, now) == "active",
    }


def _validate_target(
    session: Session,
    project: Project,
    gate_key: str,
    target_type: str,
    target_id: str | None,
) -> None:
    if target_type not in TARGET_TYPES:
        raise WaiverError(f"type de cible invalide : {target_type}")
    if target_type == "gate":
        run = session.scalar(
            select(GateRun).where(
                GateRun.project_id == project.id,
                GateRun.gate_key == gate_key,
            ).order_by(GateRun.id.desc())
        )
        if run is None:
            raise WaiverError(f"aucun run pour le gate : {gate_key}")
        return
    if not target_id:
        raise WaiverError("identifiant de cible requis")
    if target_type == "gate_run":
        try:
            run_id = int(target_id)
        except ValueError as exc:
            raise WaiverError(f"identifiant de run invalide : {target_id}") from exc
        run = session.scalar(
            select(GateRun).where(
                GateRun.id == run_id,
                GateRun.project_id == project.id,
                GateRun.gate_key == gate_key,
            )
        )
        if run is None:
            raise WaiverError(f"run de gate introuvable : {target_id}")
        return
    finding = session.scalars(
        select(GateFinding)
        .join(GateRun, GateFinding.gate_run_id == GateRun.id)
        .where(
            GateRun.project_id == project.id,
            GateRun.gate_key == gate_key,
            or_(
                GateFinding.key == target_id,
                GateFinding.id == int(target_id) if target_id.isdigit() else false(),
            ),
        )
    ).first()
    if finding is None:
        raise WaiverError(f"finding introuvable : {target_id}")


def create_waiver(
    session: Session,
    project: Project,
    *,
    gate_key: str,
    target_type: str,
    target_id: str | None,
    reason: str,
    owner: str,
    approver: str,
    expires_at: datetime,
    actor_label: str = "orchestrateur",
) -> GateWaiverRecord:
    """Crée une dérogation motivée, datée et auditée."""
    key = gate_key.strip()
    if not key:
        raise WaiverError("clé de gate requise")
    if not reason.strip():
        raise WaiverError("motif de dérogation requis")
    if not owner.strip():
        raise WaiverError("propriétaire de dérogation requis")
    if not approver.strip():
        raise WaiverError("approbateur de dérogation requis")
    expiry = _utc(expires_at)
    if expiry <= utc_now():
        raise WaiverError("la date d'expiration doit être future")
    _validate_target(session, project, key, target_type, target_id)
    record = GateWaiverRecord(
        project_id=project.id,
        gate_key=key,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        reason=reason.strip(),
        owner=owner.strip(),
        approver=approver.strip(),
        expires_at=expiry,
    )
    session.add(record)
    session.flush()
    append_audit(
        session,
        project_id=project.id,
        action="waiver.created",
        object_type="gate_waiver",
        object_id=record.id,
        actor_label=actor_label,
        payload={
            "gate_key": key,
            "target_type": target_type,
            "target_id": record.target_id,
            "owner": record.owner,
            "approver": record.approver,
            "reason": record.reason,
            "expires_at": expiry.isoformat(),
        },
    )
    return record


def list_waivers(
    session: Session,
    project: Project,
    *,
    gate_key: str | None = None,
) -> list[GateWaiverRecord]:
    query = select(GateWaiverRecord).where(
        GateWaiverRecord.project_id == project.id
    )
    if gate_key:
        query = query.where(GateWaiverRecord.gate_key == gate_key)
    return list(session.scalars(query.order_by(GateWaiverRecord.id.desc())).all())


def _run_waivers(session: Session, run: GateRun) -> list[GateWaiverRecord]:
    finding_ids = [str(finding.id) for finding in run.findings]
    finding_keys = [finding.key for finding in run.findings]
    return list(
        session.scalars(
            select(GateWaiverRecord)
            .where(
                GateWaiverRecord.project_id == run.project_id,
                GateWaiverRecord.gate_key == run.gate_key,
                or_(
                    GateWaiverRecord.target_type == "gate",
                    (
                        (GateWaiverRecord.target_type == "gate_run")
                        & (GateWaiverRecord.target_id == str(run.id))
                    ),
                    (
                        (GateWaiverRecord.target_type == "finding")
                        & GateWaiverRecord.target_id.in_(finding_ids + finding_keys)
                    ),
                ),
            )
            .order_by(GateWaiverRecord.id.desc())
        ).all()
    )


def effective_for_run(session: Session, run: GateRun) -> dict[str, Any]:
    """Calcule le verdict effectif en tenant compte des dérogations."""
    now = utc_now()
    waivers = _run_waivers(session, run)
    active = next(
        (record for record in waivers if waiver_status(record, now) == "active"),
        None,
    )
    expired = next(
        (record for record in waivers if waiver_status(record, now) == "expired"),
        None,
    )
    selected = active or expired
    verdict = run.verdict
    blocks = run.blocks
    if active is not None and verdict in {"fail", "warn", "not_run"}:
        verdict = "waived"
        blocks = False
    return {
        "verdict": verdict,
        "blocks": blocks,
        "waiver": waiver_data(selected, now) if selected is not None else None,
        "waivers": [waiver_data(record, now) for record in waivers],
    }
