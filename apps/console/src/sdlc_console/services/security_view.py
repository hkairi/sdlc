"""Vue Sécurité : gate, findings, SBOM, licences, dérogations et surface agentique."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AuditEvent, GateFinding, GateRun, Project, Repository, TaskRun
from ..paths import PathSecurityError, resolve_within
from ..redaction import redact_value
from .gate_security import parse_sbom
from .gates import GateError, latest_gate_runs
from .waivers import effective_for_run, list_waivers, waiver_data


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


def _latest_security_run(session: Session, project: Project) -> GateRun | None:
    return session.scalar(
        select(GateRun)
        .where(GateRun.project_id == project.id, GateRun.gate_key == "security")
        .order_by(GateRun.id.desc())
    )


def _evidence_from_run(run: GateRun | None) -> list[dict[str, Any]]:
    if run is None:
        return []
    raw = _loads(run.evidence_json, [])
    return [item for item in raw if isinstance(item, dict)]


def _sbom_from_run(
    run: GateRun | None,
    *,
    root: Path,
) -> dict[str, Any]:
    evidence = _evidence_from_run(run)
    candidate = next(
        (item for item in evidence if str(item.get("kind")) == "sbom" and item.get("path")),
        None,
    )
    if candidate is None:
        return {
            "status": "not_measured",
            "path": None,
            "format": None,
            "components": None,
            "licenses": [],
            "packages": [],
            "detail": "aucun SBOM lié au dernier run de sécurité",
        }
    path = str(candidate["path"])
    try:
        source = resolve_within(root, path)
        info = parse_sbom(source, root=root)
    except (PathSecurityError, GateError, FileNotFoundError, OSError) as exc:
        return {
            "status": "unreadable",
            "path": path,
            "format": None,
            "components": None,
            "licenses": [],
            "packages": [],
            "detail": str(exc),
        }
    return {
        "status": "measured",
        "path": info.path,
        "format": info.format,
        "components": info.components,
        "licenses": list(info.licenses),
        "packages": list(info.packages),
        "detail": f"{info.components} composant(s), {len(info.licenses)} licence(s)",
    }


def _license_policy(config: Mapping[str, Any] | None) -> dict[str, Any]:
    quality = (config or {}).get("quality")
    quality = quality if isinstance(quality, Mapping) else {}
    security = quality.get("security")
    security = security if isinstance(security, Mapping) else {}
    allowed = security.get("allowed_licenses")
    denied = security.get("denied_licenses")
    return {
        "allowed": list(allowed) if isinstance(allowed, (list, tuple)) else [],
        "denied": list(denied) if isinstance(denied, (list, tuple)) else [],
        "status": "declared" if allowed or denied else "not_declared",
    }


def _finding_data(
    finding: GateFinding,
    waivers: list[dict[str, Any]],
) -> dict[str, Any]:
    matching = [
        waiver
        for waiver in waivers
        if waiver["target_type"] == "gate"
        or (
            waiver["target_type"] == "finding"
            and waiver["target_id"] in {str(finding.id), finding.key}
        )
    ]
    return {
        "id": finding.id,
        "key": finding.key,
        "control": finding.control_key,
        "severity": finding.severity,
        "message": finding.message,
        "file": finding.file_path,
        "line": finding.line,
        "evidence": finding.evidence_path,
        "waivers": matching,
        "waived": any(item["status"] == "active" for item in matching),
    }


def _agent_surface(
    session: Session,
    project: Project,
    *,
    config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw_agents = (config or {}).get("agents")
    agents = raw_agents if isinstance(raw_agents, Mapping) else {}
    declared = []
    for agent_id, raw in agents.items():
        if not isinstance(raw, Mapping):
            continue
        models = raw.get("models")
        declared.append(
            {
                "id": str(agent_id),
                "enabled": bool(raw.get("enabled", False)),
                "cli": str(raw.get("cli") or ""),
                "models": list(models) if isinstance(models, Mapping) else [],
            }
        )
    runs = list(
        session.scalars(
            select(TaskRun)
            .where(TaskRun.project_id == project.id)
            .order_by(TaskRun.id.desc())
            .limit(20)
        ).all()
    )
    statuses: dict[str, int] = {}
    for run in runs:
        statuses[run.status] = statuses.get(run.status, 0) + 1
    repositories = list(
        session.scalars(
            select(Repository)
            .where(Repository.project_id == project.id, Repository.retired_at.is_(None))
            .order_by(Repository.name)
        ).all()
    )
    refused = int(
        session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.project_id == project.id,
                AuditEvent.action == "agent.git_write_refused",
            )
        )
        or 0
    )
    read_only_reviews = int(
        session.scalar(
            select(func.count(TaskRun.id)).where(
                TaskRun.project_id == project.id,
                TaskRun.role == "reviewer",
            )
        )
        or 0
    )
    return {
        "agents": declared,
        "repositories": [
            {"id": repository.id, "name": repository.name, "provider": repository.provider}
            for repository in repositories
        ],
        "recent_runs": [
            {
                "run_id": run.run_id,
                "agent_id": run.agent_id,
                "role": run.role,
                "model": run.model,
                "status": run.status,
                "cost_eur": run.cost_eur,
                "origin": run.origin,
                "log_url": f"/api/runs/{run.run_id}/events",
            }
            for run in runs
        ],
        "runs_by_status": statuses,
        "read_only_reviews": read_only_reviews,
        "git_write_refused": refused,
        "environment_policy": "jetons purgés ; Git en écriture refusé ; revue en lecture seule",
        "surface": "modèles de commande configurés uniquement",
    }


def build_security_view(
    session: Session,
    project: Project,
    *,
    root: str | Path | None = None,
    config: Mapping[str, Any] | None = None,
    current_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Construit la vue Sécurité depuis le dernier gate et ses preuves."""
    root_path = Path(root or Path.cwd()).resolve()
    run = _latest_security_run(session, project)
    gate = next(
        (
            item
            for item in latest_gate_runs(
                session,
                project,
                current_fingerprint=current_fingerprint,
            )
            if item.get("gate_key") == "security"
        ),
        None,
    )
    waivers_raw = list_waivers(session, project, gate_key="security")
    waivers = [waiver_data(record) for record in waivers_raw]
    findings = []
    if run is not None:
        findings = [
            _finding_data(finding, waivers)
            for finding in session.scalars(
                select(GateFinding)
                .where(GateFinding.gate_run_id == run.id)
                .order_by(GateFinding.id)
            ).all()
        ]
    counts = {
        severity: sum(1 for finding in findings if finding["severity"] == severity)
        for severity in ("critical", "error", "warning", "info")
    }
    sbom = _sbom_from_run(run, root=root_path)
    effective = effective_for_run(session, run) if run is not None else None
    data = {
        "generated_at": _iso(datetime.now(UTC)),
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "status": "measured" if run is not None else "not_measured",
        "gate": gate,
        "run": {
            "id": run.id if run is not None else None,
            "verdict": effective["verdict"] if effective is not None else "not_run",
            "base_verdict": run.verdict if run is not None else None,
            "blocks": effective["blocks"] if effective is not None else False,
            "report_path": run.report_path if run is not None else None,
            "generated_at": _iso(run.created_at) if run is not None else None,
        },
        "findings": findings,
        "finding_counts": counts,
        "sbom": sbom,
        "licenses": {
            "values": sbom["licenses"],
            "count": len(sbom["licenses"]),
            "status": "measured" if sbom["status"] == "measured" else "not_measured",
            "policy": _license_policy(config),
        },
        "waivers": waivers,
        "agent_surface": _agent_surface(session, project, config=config),
        "sources": {
            "gate": "reports/gates/security.json",
            "sbom": sbom["path"] or "reports/security/*",
            "waivers": "gate_waivers",
            "agents": "sdlc.config.yaml + task_runs + audit_events",
        },
    }
    return redact_value(data)  # type: ignore[return-value]
