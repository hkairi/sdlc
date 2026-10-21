"""Vue Déploiements : environnements, historique, DORA et go/no-go."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Deployment, Project
from ..redaction import redact_value
from .dora import build_dora
from .gates import latest_gate_runs

ENVIRONMENTS = ("dev", "preprod", "prod")
ENV_ALIASES = {
    "dev": "dev",
    "development": "dev",
    "développement": "dev",
    "preprod": "preprod",
    "préprod": "preprod",
    "staging": "preprod",
    "recette": "preprod",
    "prod": "prod",
    "production": "prod",
}
GATE_KEYS = ("tests", "coverage", "security", "performance", "data")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()


def _environment(value: str) -> str:
    lowered = value.strip().lower()
    return ENV_ALIASES.get(lowered, lowered)


def _when(deployment: Deployment) -> datetime:
    value = deployment.started_at or deployment.finished_at or deployment.imported_at
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _deployment_data(deployment: Deployment) -> dict[str, Any]:
    return {
        "id": deployment.id,
        "deploy_id": deployment.deploy_id,
        "environment": _environment(deployment.env),
        "raw_environment": deployment.env,
        "version": deployment.version,
        "status": deployment.status,
        "is_rollback": deployment.is_rollback,
        "rollback_of_version": deployment.rollback_of_version,
        "started_at": _iso(deployment.started_at),
        "finished_at": _iso(deployment.finished_at),
        "by": deployment.by_label or (
            deployment.by_person.display_name if deployment.by_person is not None else None
        ),
        "repository": (
            deployment.repository.name
            if deployment.repository is not None
            else deployment.repository_label
        ),
        "feature_key": deployment.feature_key,
        "note": deployment.note,
        "origin": "deploys.jsonl",
    }


def _gate_checklist(
    session: Session,
    project: Project,
    *,
    current_fingerprint: str | None,
) -> list[dict[str, Any]]:
    latest = {
        str(item.get("gate_key")): item
        for item in latest_gate_runs(
            session,
            project,
            current_fingerprint=current_fingerprint,
        )
    }
    rows: list[dict[str, Any]] = []
    labels = {
        "tests": "Tests",
        "coverage": "Couverture",
        "security": "Sécurité",
        "performance": "Performance",
        "data": "Données",
    }
    for key in GATE_KEYS:
        item = latest.get(key)
        if item is None:
            status = "not_run"
            detail = "gate absent"
            evidence = "reports/gates"
        else:
            verdict = str(item.get("verdict") or "not_run")
            status = "pass" if verdict in {"pass", "waived", "not_applicable"} else (
                "warn" if verdict == "warn" else "fail"
            )
            detail = str(item.get("reason") or verdict)
            evidence = str(item.get("report_path") or f"reports/gates/{key}.json")
        rows.append(
            {
                "key": key,
                "label": labels[key],
                "status": status,
                "blocking": status in {"fail", "not_run"},
                "detail": detail,
                "evidence": evidence,
                "source": "reports/gates",
            }
        )
    for key, item in latest.items():
        if key in GATE_KEYS or key == "recette":
            continue
        verdict = str(item.get("verdict") or "not_run")
        status = "pass" if verdict in {"pass", "waived", "not_applicable"} else (
            "warn" if verdict == "warn" else "fail"
        )
        rows.append(
            {
                "key": key,
                "label": str(item.get("name") or key),
                "status": status,
                "blocking": status in {"fail", "not_run"},
                "detail": str(item.get("reason") or verdict),
                "evidence": str(item.get("report_path") or f"reports/gates/{key}.json"),
                "source": "reports/gates",
            }
        )
    return rows


def _recette_checklist(
    project: Project,
    *,
    root: Path,
    current_fingerprint: str | None,
    session: Session,
) -> dict[str, Any]:
    latest = {
        str(item.get("gate_key")): item
        for item in latest_gate_runs(
            session,
            project,
            current_fingerprint=current_fingerprint,
        )
    }
    gate = latest.get("recette")
    files = sorted((root / "docs" / "recette").glob("*.md"))
    if gate is not None:
        verdict = str(gate.get("verdict") or "not_run")
        status = "pass" if verdict in {"pass", "waived"} else (
            "warn" if verdict == "warn" else "fail"
        )
        detail = str(gate.get("reason") or verdict)
        evidence = str(gate.get("report_path") or "reports/gates/recette.json")
    elif files:
        status = "pass"
        detail = f"{len(files)} matrice(s) de recette trouvée(s)"
        evidence = str(files[0])
    else:
        status = "not_run"
        detail = "aucune recette ni matrice de recette"
        evidence = "docs/recette"
    return {
        "key": "recette",
        "label": "Recette",
        "status": status,
        "blocking": status in {"fail", "not_run"},
        "detail": detail,
        "evidence": evidence,
        "source": "docs/recette + reports/gates/recette.json",
    }


def _deployment_checklist(deployments: list[Deployment]) -> dict[str, Any]:
    if not deployments:
        return {
            "key": "deploiements",
            "label": "Historique des déploiements",
            "status": "not_run",
            "blocking": False,
            "detail": "aucun déploiement ingéré",
            "evidence": "docs/journal/deploys.jsonl",
            "source": "deploys.jsonl",
        }
    latest = max(deployments, key=_when)
    return {
        "key": "deploiements",
        "label": "Historique des déploiements",
        "status": "pass",
        "blocking": False,
        "detail": f"{len(deployments)} déploiement(s), dernier {latest.version or latest.deploy_id}",
        "evidence": "docs/journal/deploys.jsonl",
        "source": "deploys.jsonl",
    }


def build_deployments_view(
    session: Session,
    project: Project,
    *,
    env: str | None = None,
    limit: int = 50,
    offset: int = 0,
    window_days: int = 30,
    root: str | Path | None = None,
    current_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Construit la vue Déploiements avec preuves de go/no-go."""
    root_path = Path(root or Path.cwd()).resolve()
    all_deployments = list(
        session.scalars(
            select(Deployment)
            .where(Deployment.project_id == project.id)
            .order_by(Deployment.id.desc())
        ).all()
    )
    selected_env = _environment(env) if env else None
    filtered = [
        deployment
        for deployment in all_deployments
        if selected_env is None or _environment(deployment.env) == selected_env
    ]
    history = sorted(filtered, key=_when, reverse=True)
    total = len(history)
    paged = history[offset : offset + limit]
    environments: dict[str, Any] = {}
    for key in ENVIRONMENTS:
        values = [
            deployment
            for deployment in all_deployments
            if _environment(deployment.env) == key
        ]
        latest = max(values, key=_when) if values else None
        environments[key] = {
            "status": "measured" if values else "not_measured",
            "count": len(values),
            "latest": _deployment_data(latest) if latest is not None else None,
        }
    rollbacks = [
        _deployment_data(deployment)
        for deployment in all_deployments
        if deployment.is_rollback or deployment.status.lower() == "rollback"
    ]
    dora = build_dora(
        session,
        project,
        window_days=window_days,
        incident_paths=sorted((root_path / "docs" / "incidents").glob("*.md")),
    )
    checklist = _gate_checklist(
        session,
        project,
        current_fingerprint=current_fingerprint,
    )
    checklist.append(
        _recette_checklist(
            project,
            root=root_path,
            current_fingerprint=current_fingerprint,
            session=session,
        )
    )
    checklist.append(_deployment_checklist(all_deployments))
    conditions = [
        item for item in checklist if item["blocking"] and item["status"] != "pass"
    ]
    payload = {
        "generated_at": _iso(datetime.now(UTC)),
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "filters": {"env": selected_env},
        "environments": environments,
        "history": [_deployment_data(item) for item in paged],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(paged) < total,
        "next_offset": offset + len(paged) if offset + len(paged) < total else None,
        "rollbacks": rollbacks,
        "dora": dora,
        "go_no_go": {
            "verdict": "no-go" if conditions else "go",
            "conditions": conditions,
            "checklist": checklist,
            "evidence": [item["evidence"] for item in checklist],
        },
        "sources": {
            "deployments": "docs/journal/deploys.jsonl",
            "dora": "deploys.jsonl + features + docs/incidents",
            "go_no_go": "reports/gates + docs/recette",
        },
    }
    return redact_value(payload)  # type: ignore[return-value]
