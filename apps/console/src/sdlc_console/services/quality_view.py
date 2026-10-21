"""Vue Performance & données : budgets, signaux, PII, migrations et sauvegardes."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import GateFinding, GateRun, Project
from ..paths import PathSecurityError, resolve_within
from ..redaction import redact_value
from .gate_config import performance_thresholds
from .gate_data import BackupStatus, load_backup_status
from .gates import latest_gate_runs


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _latest_run(session: Session, project: Project, gate_key: str) -> GateRun | None:
    return session.scalar(
        select(GateRun)
        .where(GateRun.project_id == project.id, GateRun.gate_key == gate_key)
        .order_by(GateRun.id.desc())
    )


def _controls(run: GateRun | None) -> list[dict[str, Any]]:
    if run is None:
        return []
    raw = _loads(run.controls_json, [])
    return [item for item in raw if isinstance(item, dict)]


def _findings(session: Session, run: GateRun | None) -> list[dict[str, Any]]:
    if run is None:
        return []
    rows = session.scalars(
        select(GateFinding)
        .where(GateFinding.gate_run_id == run.id)
        .order_by(GateFinding.id)
    ).all()
    return [
        {
            "id": finding.id,
            "key": finding.key,
            "control": finding.control_key,
            "severity": finding.severity,
            "message": finding.message,
            "file": finding.file_path,
            "line": finding.line,
            "evidence": finding.evidence_path,
        }
        for finding in rows
    ]


def _gate_summary(
    session: Session,
    project: Project,
    run: GateRun | None,
    *,
    current_fingerprint: str | None,
) -> dict[str, Any] | None:
    if run is None:
        return None
    latest = {
        item.get("gate_key"): item
        for item in latest_gate_runs(
            session,
            project,
            current_fingerprint=current_fingerprint,
        )
    }
    return latest.get(run.gate_key)


def _schema_state(session: Session) -> dict[str, Any]:
    """État Alembic de la base, sans jamais inventer de révision."""
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        ini = Path(__file__).resolve().parents[3] / "alembic.ini"
        if not ini.is_file():
            raise FileNotFoundError(str(ini))
        config = Config(str(ini))
        head = ScriptDirectory.from_config(config).get_current_head()
        current = MigrationContext.configure(session.connection()).get_current_revision()
        return {
            "status": "measured",
            "current": current,
            "head": head,
            "up_to_date": bool(current == head),
            "source": "alembic",
        }
    except Exception as exc:  # noqa: BLE001 — un schéma inconnu reste non mesuré
        return {
            "status": "not_measured",
            "current": None,
            "head": None,
            "up_to_date": None,
            "source": "alembic",
            "detail": str(exc)[:300],
        }


def _backup_from_controls(
    controls: list[dict[str, Any]],
    *,
    root: Path,
) -> dict[str, Any]:
    control = next((item for item in controls if item.get("key") == "backup"), None)
    # On privilégie l'état réel du fichier de preuve quand il existe.
    candidate = root / "reports" / "data" / "backup.json"
    status: BackupStatus | None = None
    try:
        source = resolve_within(root, candidate)
        status = load_backup_status(source, root=root)
    except (PathSecurityError, FileNotFoundError, OSError):
        status = None
    if status is not None:
        return {
            "status": "measured",
            "verified": status.verified,
            "restore_tested": status.restore_tested,
            "age_hours": status.age_hours,
            "source": status.source,
            "verdict": control.get("verdict") if control else None,
            "reason": control.get("reason") if control else None,
        }
    if control is not None:
        return {
            "status": "measured",
            "verified": None,
            "restore_tested": None,
            "age_hours": None,
            "source": "reports/gates/data.json",
            "verdict": control.get("verdict"),
            "reason": control.get("reason"),
        }
    return {
        "status": "not_measured",
        "verified": None,
        "restore_tested": None,
        "age_hours": None,
        "source": "reports/data/backup.json",
        "verdict": None,
        "reason": "aucune sauvegarde vérifiée",
    }


def build_performance_data_view(
    session: Session,
    project: Project,
    *,
    root: str | Path | None = None,
    config: Mapping[str, Any] | None = None,
    current_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Construit la vue Performance & données depuis les gates persistés."""
    root_path = Path(root or Path.cwd()).resolve()
    perf_run = _latest_run(session, project, "performance")
    data_run = _latest_run(session, project, "data")
    perf_controls = _controls(perf_run)
    data_controls = _controls(data_run)
    perf_findings = _findings(session, perf_run)
    data_findings = _findings(session, data_run)

    cases: list[dict[str, Any]] = []
    thresholds = performance_thresholds(config)
    for control in perf_controls:
        details = control.get("details")
        if isinstance(details, dict):
            raw_cases = details.get("cases")
            if isinstance(raw_cases, list):
                cases.extend(item for item in raw_cases if isinstance(item, dict))
            raw_thresholds = details.get("thresholds")
            if isinstance(raw_thresholds, dict):
                thresholds.update(
                    {
                        key: value
                        for key, value in raw_thresholds.items()
                        if value is not None
                    }
                )
    signals = [
        finding
        for finding in perf_findings
        if finding["control"] == "static" or str(finding["key"]).startswith("perf:static")
    ]
    observed = [
        finding
        for finding in perf_findings
        if finding["control"] == "observed" or str(finding["key"]).startswith("perf:")
    ]
    pii = [finding for finding in data_findings if finding["control"] == "pii"]
    migrations = [
        finding for finding in data_findings if finding["control"] == "migrations"
    ]
    backup = _backup_from_controls(data_controls, root=root_path)
    retention_days = _retention_days(config)
    if retention_days is None:
        retention_control = next(
            (item for item in data_controls if item.get("key") == "retention"),
            None,
        )
        details = retention_control.get("details") if retention_control else None
        if isinstance(details, dict) and isinstance(details.get("retention_days"), int):
            retention_days = details["retention_days"]

    data_summary = {
        "status": "measured" if data_run is not None else "not_measured",
        "verdict": data_run.verdict if data_run is not None else "not_run",
        "blocks": data_run.blocks if data_run is not None else False,
        "report_path": data_run.report_path if data_run is not None else None,
        "generated_at": _iso(data_run.created_at) if data_run is not None else None,
    }
    payload = {
        "generated_at": _iso(datetime.now(UTC)),
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "performance": {
            "status": "measured" if perf_run is not None else "not_measured",
            "verdict": perf_run.verdict if perf_run is not None else "not_run",
            "blocks": perf_run.blocks if perf_run is not None else False,
            "report_path": perf_run.report_path if perf_run is not None else None,
            "generated_at": _iso(perf_run.created_at) if perf_run is not None else None,
            "budgets": thresholds,
            "cases": cases,
            "signals": signals,
            "findings": observed,
            "controls": perf_controls,
        },
        "data": {
            **data_summary,
            "controls": data_controls,
            "pii": pii,
            "migrations": migrations,
            "backup": backup,
            "retention_days": retention_days,
            "schema": _schema_state(session),
        },
        "gates": {
            key: _gate_summary(session, project, run, current_fingerprint=current_fingerprint)
            for key, run in (("performance", perf_run), ("data", data_run))
        },
        "sources": {
            "performance": "reports/perf/*.json + reports/gates/performance.json",
            "data": "reports/data/* + reports/gates/data.json",
            "backup": backup["source"],
            "schema": "alembic",
        },
    }
    return redact_value(payload)  # type: ignore[return-value]


def _retention_days(config: Mapping[str, Any] | None) -> int | None:
    quality = (config or {}).get("quality")
    quality = quality if isinstance(quality, Mapping) else {}
    data = quality.get("data")
    data = data if isinstance(data, Mapping) else {}
    retention = (config or {}).get("retention")
    retention = retention if isinstance(retention, Mapping) else {}
    value = retention.get("default_days", data.get("retention_days"))
    return int(value) if isinstance(value, int) else None
