"""Ingestion des journaux `runs.jsonl` et `deploys.jsonl`.

Les journaux sont des fichiers JSON Lines. L'ingestion est idempotente : un run
est identifié par `run_id`, un déploiement par `deploy_id`, dans le périmètre du
projet. Un run local (`origin = "lancée"`) n'est jamais écrasé par le journal.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Deployment, IngestionRun, Project, Repository, TaskRun, utc_now
from ..paths import is_secret_path
from .people import resolve_person
from .projects import list_repositories
from .providers.common import parse_datetime

RUN_STATUSES = frozenset({"queued", "running", "done", "failed", "timeout", "cancelled"})
DEPLOY_STATUSES = frozenset({"success", "failed", "rollback", "in_progress", "cancelled"})
JournalKind = Literal["runs", "deploys"]


class JournalIngestionError(RuntimeError):
    """Erreur de lecture ou de validation d'un journal."""


@dataclass(frozen=True)
class ParsedRun:
    run_id: str
    task_key: str | None
    agent_id: str | None
    model: str | None
    role: str | None
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    cost_eur: float | None
    estimated_cost_eur: float | None
    budget_eur: float | None
    tokens_in: int | None
    tokens_out: int | None
    pid: int | None
    process_group: int | None
    exit_code: int | None
    log_path: str | None
    report_path: str | None
    cancel_requested: bool
    repository_label: str | None


@dataclass(frozen=True)
class ParsedDeployment:
    deploy_id: str
    env: str
    version: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    by_label: str | None
    by_info: Mapping[str, Any]
    note: str | None
    feature_key: str | None
    is_rollback: bool
    rollback_of_version: str | None
    repository_label: str | None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first(record: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    return None


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "oui", "rollback"}
    return False


def _record_id(record: Mapping[str, Any], keys: tuple[str, ...], prefix: str) -> str:
    for key in keys:
        value = _text(record.get(key))
        if value:
            return value
    digest = hashlib.sha256(
        json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _load_jsonl(path: str | Path) -> list[tuple[int, dict[str, Any]]]:
    journal_path = Path(path).expanduser().resolve()
    if not journal_path.is_file():
        raise JournalIngestionError(f"journal introuvable : {journal_path}")
    if is_secret_path(journal_path):
        raise JournalIngestionError(f"lecture de secret refusée : {journal_path}")
    try:
        lines = journal_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise JournalIngestionError(f"journal illisible : {journal_path} : {exc}") from exc
    records: list[tuple[int, dict[str, Any]]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JournalIngestionError(
                f"ligne {line_number} : JSON invalide ({exc.msg})"
            ) from exc
        if not isinstance(payload, dict):
            raise JournalIngestionError(f"ligne {line_number} : objet JSON attendu")
        records.append((line_number, payload))
    return records


def _run_status(record: Mapping[str, Any], line_number: int) -> str:
    status = (_text(record.get("status")) or "").lower()
    if status == "canceled":
        status = "cancelled"
    if status not in RUN_STATUSES:
        raise JournalIngestionError(
            f"ligne {line_number} : statut de run invalide ({status or 'absent'})"
        )
    return status


def _deploy_status(record: Mapping[str, Any], line_number: int) -> tuple[str, bool]:
    explicit_rollback = _as_bool(
        record.get("is_rollback") if "is_rollback" in record else record.get("rollback")
    )
    raw = (_text(record.get("status")) or "").lower().replace("-", "_")
    aliases = {
        "succeeded": "success",
        "ok": "success",
        "deployed": "success",
        "failure": "failed",
        "error": "failed",
        "rolled_back": "rollback",
        "running": "in_progress",
        "started": "in_progress",
        "canceled": "cancelled",
    }
    status = aliases.get(raw, raw)
    if explicit_rollback:
        status = "rollback"
    if status not in DEPLOY_STATUSES:
        raise JournalIngestionError(
            f"ligne {line_number} : statut de déploiement invalide ({status or 'absent'})"
        )
    return status, status == "rollback"


def _parse_by(record: Mapping[str, Any]) -> tuple[str | None, Mapping[str, Any]]:
    raw_by = record.get("by") or record.get("actor") or record.get("author")
    label = _text(record.get("by_label") or record.get("actor_label") or record.get("author_label"))
    info: Mapping[str, Any]
    if isinstance(raw_by, Mapping):
        info = raw_by
        label = label or _text(
            raw_by.get("name") or raw_by.get("login") or raw_by.get("username") or raw_by.get("email")
        )
    else:
        text = _text(raw_by)
        info = {"name": text} if text else {}
        label = label or text
    return label, info


def _parse_agent(record: Mapping[str, Any]) -> str | None:
    raw = record.get("agent_id") or record.get("agent")
    if isinstance(raw, Mapping):
        return _text(raw.get("id") or raw.get("name") or raw.get("slug"))
    return _text(raw)


def _parse_run(record: Mapping[str, Any], line_number: int) -> ParsedRun:
    return ParsedRun(
        run_id=_record_id(record, ("run_id", "id", "run"), "run"),
        task_key=_text(record.get("task_key") or record.get("task") or record.get("task_id")),
        agent_id=_parse_agent(record),
        model=_text(record.get("model")),
        role=_text(record.get("role")),
        status=_run_status(record, line_number),
        started_at=parse_datetime(_first(record, ("started_at", "started", "start"))),
        ended_at=parse_datetime(_first(record, ("ended_at", "ended", "finished_at"))),
        cost_eur=_as_float(_first(record, ("cost_eur", "cost"))),
        estimated_cost_eur=_as_float(
            _first(record, ("estimated_cost_eur", "estimated_cost"))
        ),
        budget_eur=_as_float(_first(record, ("budget_eur", "budget"))),
        tokens_in=_as_int(_first(record, ("tokens_in", "input_tokens"))),
        tokens_out=_as_int(_first(record, ("tokens_out", "output_tokens"))),
        pid=_as_int(record.get("pid")),
        process_group=_as_int(record.get("process_group")),
        exit_code=_as_int(record.get("exit_code")),
        log_path=_text(record.get("log_path")),
        report_path=_text(record.get("report_path")),
        cancel_requested=_as_bool(record.get("cancel_requested")),
        repository_label=_text(
            record.get("repository") or record.get("repo") or record.get("repository_name")
        ),
    )


def _parse_deploy(record: Mapping[str, Any], line_number: int) -> ParsedDeployment:
    env = _text(record.get("env") or record.get("environment"))
    if env is None:
        raise JournalIngestionError(f"ligne {line_number} : environnement absent")
    status, is_rollback = _deploy_status(record, line_number)
    by_label, by_info = _parse_by(record)
    feature = record.get("feature_key") or record.get("feature") or record.get("feature_id")
    if isinstance(feature, Mapping):
        feature = feature.get("key") or feature.get("name")
    repository = record.get("repository") or record.get("repo") or record.get("repository_name")
    if isinstance(repository, Mapping):
        repository = repository.get("name") or repository.get("url")
    return ParsedDeployment(
        deploy_id=_record_id(record, ("deploy_id", "id", "deployment_id"), "deploy"),
        env=env,
        version=_text(_first(record, ("version", "tag", "release"))),
        status=status,
        started_at=parse_datetime(
            _first(record, ("started_at", "started", "deployed_at", "date", "timestamp"))
        ),
        finished_at=parse_datetime(_first(record, ("finished_at", "finished", "ended_at"))),
        by_label=by_label,
        by_info=by_info,
        note=_text(record.get("note") or record.get("reason") or record.get("message")),
        feature_key=_text(feature),
        is_rollback=is_rollback,
        rollback_of_version=_text(
            record.get("rollback_of_version")
            or record.get("rollback_of")
            or record.get("previous_version")
        ),
        repository_label=_text(repository),
    )


def _resolve_repository(
    session: Session,
    project: Project,
    label: str | None,
) -> Repository | None:
    if not label:
        return None
    for repository in list_repositories(session, project):
        if label in {repository.name, repository.url, repository.local_path}:
            return repository
    return None


def _resolve_by_person(
    session: Session,
    project: Project,
    info: Mapping[str, Any],
) -> int | None:
    email = _text(info.get("email"))
    login = _text(info.get("login") or info.get("username"))
    provider = _text(info.get("provider"))
    name = _text(info.get("name")) or login or email
    if login and provider in {"github", "gitlab"}:
        person = resolve_person(
            session,
            project,
            provider=provider,
            external_id=login,
            email=email,
            display_name=name or login,
        )
    elif email:
        person = resolve_person(
            session,
            project,
            email=email,
            display_name=name or email,
        )
    else:
        return None
    return person.id


def _upsert_run(session: Session, project: Project, parsed: ParsedRun) -> str:
    existing = session.scalar(
        select(TaskRun).where(
            TaskRun.project_id == project.id,
            TaskRun.run_id == parsed.run_id,
        )
    )
    if existing is not None and existing.origin == "lancée":
        return "skipped"
    repository = _resolve_repository(session, project, parsed.repository_label)
    values: dict[str, Any] = {
        "task_key": parsed.task_key,
        "agent_id": parsed.agent_id,
        "primary_repository_id": repository.id if repository is not None else None,
        "model": parsed.model,
        "role": parsed.role,
        "started_at": parsed.started_at,
        "ended_at": parsed.ended_at,
        "status": parsed.status,
        "cost_eur": parsed.cost_eur,
        "estimated_cost_eur": parsed.estimated_cost_eur,
        "budget_eur": parsed.budget_eur,
        "tokens_in": parsed.tokens_in,
        "tokens_out": parsed.tokens_out,
        "pid": parsed.pid,
        "process_group": parsed.process_group,
        "exit_code": parsed.exit_code,
        "log_path": parsed.log_path,
        "report_path": parsed.report_path,
        "cancel_requested": parsed.cancel_requested,
        "origin": "ingérée",
        "imported_at": utc_now(),
    }
    if existing is None:
        session.add(
            TaskRun(
                project_id=project.id,
                run_id=parsed.run_id,
                **values,
            )
        )
        return "inserted"
    for key, value in values.items():
        setattr(existing, key, value)
    return "updated"


def _upsert_deploy(session: Session, project: Project, parsed: ParsedDeployment) -> str:
    existing = session.scalar(
        select(Deployment).where(
            Deployment.project_id == project.id,
            Deployment.deploy_id == parsed.deploy_id,
        )
    )
    repository = _resolve_repository(session, project, parsed.repository_label)
    values: dict[str, Any] = {
        "repository_id": repository.id if repository is not None else None,
        "repository_label": parsed.repository_label,
        "env": parsed.env,
        "version": parsed.version,
        "status": parsed.status,
        "started_at": parsed.started_at,
        "finished_at": parsed.finished_at,
        "by_person_id": _resolve_by_person(session, project, parsed.by_info),
        "by_label": parsed.by_label,
        "note": parsed.note,
        "feature_key": parsed.feature_key,
        "is_rollback": parsed.is_rollback,
        "rollback_of_version": parsed.rollback_of_version,
        "imported_at": utc_now(),
    }
    if existing is None:
        session.add(
            Deployment(
                project_id=project.id,
                deploy_id=parsed.deploy_id,
                **values,
            )
        )
        return "inserted"
    for key, value in values.items():
        setattr(existing, key, value)
    return "updated"


def _ingest_journal(
    session: Session,
    project: Project,
    path: str | Path,
    *,
    kind: JournalKind,
) -> IngestionRun:
    source = "runs.jsonl" if kind == "runs" else "deploys.jsonl"
    run = IngestionRun(
        project_id=project.id,
        repository_id=None,
        source=source,
        started_at=utc_now(),
        status="running",
    )
    session.add(run)
    session.flush()
    try:
        records = _load_jsonl(path)
        parsed: list[ParsedRun | ParsedDeployment]
        if kind == "runs":
            parsed = [_parse_run(record, line) for line, record in records]
        else:
            parsed = [_parse_deploy(record, line) for line, record in records]
        stats = {"scanned": len(parsed), "inserted": 0, "updated": 0, "skipped": 0}
        with session.begin_nested():
            for item in parsed:
                if isinstance(item, ParsedRun):
                    outcome = _upsert_run(session, project, item)
                else:
                    outcome = _upsert_deploy(session, project, item)
                stats[outcome] += 1
        run.status = "done"
        run.finished_at = utc_now()
        run.stats_json = json.dumps(stats, sort_keys=True)
        session.flush()
        return run
    except Exception as exc:  # noqa: BLE001 - l'échec est journalisé puis propagé
        run.status = "failed"
        run.finished_at = utc_now()
        run.error = str(exc)[:2000]
        run.stats_json = json.dumps({"error": str(exc)[:500]}, ensure_ascii=False)
        session.flush()
        if isinstance(exc, JournalIngestionError):
            raise
        raise JournalIngestionError(str(exc)) from exc


def ingest_runs(session: Session, project: Project, path: str | Path) -> IngestionRun:
    """Ingère `runs.jsonl` pour un projet."""
    return _ingest_journal(session, project, path, kind="runs")


def ingest_deploys(session: Session, project: Project, path: str | Path) -> IngestionRun:
    """Ingère `deploys.jsonl` pour un projet."""
    return _ingest_journal(session, project, path, kind="deploys")


def ingest_journals(
    session: Session,
    project: Project,
    *,
    runs_path: str | Path | None = None,
    deploys_path: str | Path | None = None,
) -> list[IngestionRun]:
    """Ingère les journaux fournis, dans l'ordre runs puis deploys."""
    runs: list[IngestionRun] = []
    if runs_path is not None:
        runs.append(ingest_runs(session, project, runs_path))
    if deploys_path is not None:
        runs.append(ingest_deploys(session, project, deploys_path))
    return runs
