"""Vue d'ensemble : KPI, décisions, pipeline et risques."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Deployment, Feature, GateRun, Project, Task, TaskRun, utc_now
from .waivers import effective_for_run


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _json_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def _kpi(
    key: str,
    label: str,
    value: Any,
    unit: str | None,
    source: str,
    *,
    detail: str | None = None,
) -> dict[str, Any]:
    measured = value is not None
    return {
        "key": key,
        "label": label,
        "value": value,
        "unit": unit,
        "source": source,
        "status": "measured" if measured else "not_measured",
        "detail": detail or ("mesuré" if measured else "non mesuré"),
    }


def _phase_status(statuses: list[str]) -> str:
    if any(status in {"failed", "blocked"} for status in statuses):
        return "failed"
    if statuses and all(status == "done" for status in statuses):
        return "done"
    if any(status in {"doing", "done", "in_progress"} for status in statuses):
        return "doing"
    return "todo"


def _deployment_status(deployments: list[Deployment]) -> tuple[str, str | None, str]:
    prod = [
        deployment
        for deployment in deployments
        if deployment.env.strip().lower() in {"prod", "production"}
    ]
    if not prod:
        return "not_measured", None, "aucun déploiement prod ingéré"
    latest = max(prod, key=lambda deployment: deployment.started_at or deployment.imported_at)
    status = latest.status.lower()
    if status == "success":
        return "done", latest.version, "dernier déploiement prod réussi"
    if status in {"failed", "rollback"}:
        return "failed", latest.version, "dernier déploiement prod en échec ou rollback"
    return "doing", latest.version, "déploiement prod en cours"


def _pipeline(
    features: list[Feature],
    tasks: list[Task],
    deployments: list[Deployment],
) -> list[dict[str, Any]]:
    phase_order: list[tuple[int, str, str, list[str]]] = []
    seen: set[str] = set()
    for feature in features:
        for index, phase in enumerate(_json_list(feature.phases_json)):
            if not isinstance(phase, dict):
                continue
            phase_id = str(phase.get("id") or phase.get("name") or f"phase-{index}")
            phase_name = str(phase.get("name") or phase_id)
            if phase_id in seen:
                continue
            seen.add(phase_id)
            raw_items = phase.get("items")
            items: list[Any] = raw_items if isinstance(raw_items, list) else []
            statuses = [
                str(item.get("status", "todo")).lower()
                for item in items
                if isinstance(item, dict)
            ]
            try:
                order = int(phase.get("order", len(phase_order) + 1))
            except (TypeError, ValueError):
                order = len(phase_order) + 1
            phase_order.append((order, phase_id, phase_name, statuses))
    phase_order.sort(key=lambda item: item[0])

    if phase_order:
        stages: list[dict[str, Any]] = []
        task_statuses = [task.status for task in tasks]
        for _order, phase_id, phase_name, statuses in phase_order:
            stage_status = _phase_status(statuses) if statuses else "not_measured"
            source = "state.json"
            detail = f"{len(statuses)} contrôle(s)"
            if not statuses and phase_id in {"impl", "implementation"}:
                if task_statuses and all(status == "done" for status in task_statuses):
                    stage_status = "done"
                elif any(status in {"doing", "done"} for status in task_statuses):
                    stage_status = "doing"
                elif task_statuses:
                    stage_status = "todo"
                else:
                    stage_status = "not_measured"
                source = "state.json + tasks"
                detail = f"{len(task_statuses)} tâche(s)"
            stages.append(
                {
                    "id": phase_id,
                    "label": phase_name,
                    "status": stage_status,
                    "source": source,
                    "detail": detail,
                }
            )
        return stages

    task_statuses = [task.status for task in tasks]
    if task_statuses and all(status == "done" for status in task_statuses):
        implementation = "done"
    elif any(status in {"doing", "done"} for status in task_statuses):
        implementation = "doing"
    elif task_statuses:
        implementation = "todo"
    else:
        implementation = "not_measured"
    deployment_status, _version, deployment_detail = _deployment_status(deployments)
    cadrage = "done" if any(feature.spec_path or feature.objective for feature in features) else "todo"
    planification = "done" if tasks else "todo"
    cloture = (
        "done"
        if features and all(feature.delivered for feature in features)
        else "doing"
        if any(feature.delivered for feature in features)
        else "todo"
    )
    return [
        {
            "id": "cadrage",
            "label": "Cadrage",
            "status": cadrage,
            "source": "features",
            "detail": "",
        },
        {
            "id": "planification",
            "label": "Planification",
            "status": planification,
            "source": "features/tasks",
            "detail": "",
        },
        {
            "id": "implementation",
            "label": "Implémentation",
            "status": implementation,
            "source": "tasks",
            "detail": "",
        },
        {
            "id": "validation",
            "label": "Validation",
            "status": "not_measured",
            "source": "reports/gates",
            "detail": "gates non mesurés",
        },
        {
            "id": "deploiement",
            "label": "Déploiement",
            "status": deployment_status,
            "source": "deploys.jsonl",
            "detail": deployment_detail,
        },
        {
            "id": "cloture",
            "label": "Clôture",
            "status": cloture,
            "source": "features",
            "detail": "",
        },
    ]


def build_overview(session: Session, project: Project) -> dict[str, Any]:
    """Construit la vue d'ensemble sans inventer de mesure absente."""
    features = list(
        session.scalars(
            select(Feature).where(Feature.project_id == project.id).order_by(Feature.key)
        ).all()
    )
    tasks = [task for feature in features for task in feature.tasks]
    deployments = list(
        session.scalars(
            select(Deployment).where(Deployment.project_id == project.id)
        ).all()
    )
    runs_with_cost = list(
        session.scalars(
            select(TaskRun).where(
                TaskRun.project_id == project.id,
                TaskRun.cost_eur.is_not(None),
            )
        ).all()
    )
    gate_runs = list(
        session.scalars(
            select(GateRun)
            .where(GateRun.project_id == project.id)
            .order_by(GateRun.id.desc())
        ).all()
    )
    latest_gates: dict[str, GateRun] = {}
    for run in gate_runs:
        latest_gates.setdefault(run.gate_key, run)
    blocking_gates = sum(
        1 for run in latest_gates.values() if effective_for_run(session, run)["blocks"]
    )
    coverage_percent: float | None = None
    coverage_run = latest_gates.get("coverage")
    if coverage_run is not None:
        try:
            controls = json.loads(coverage_run.controls_json)
        except (TypeError, json.JSONDecodeError):
            controls = []
        for control in controls if isinstance(controls, list) else []:
            if isinstance(control, dict) and control.get("key") == "global":
                metric = (control.get("details") or {}).get("metric") or {}
                value = metric.get("percent")
                if isinstance(value, (int, float)):
                    coverage_percent = float(value)
                break
    vulnerabilities: int | None = None
    vulnerability_detail = "aucun rapport de sécurité ingéré"
    security_run = latest_gates.get("security")
    if security_run is not None:
        try:
            security_controls = json.loads(security_run.controls_json)
        except (TypeError, json.JSONDecodeError):
            security_controls = []
        for control in security_controls if isinstance(security_controls, list) else []:
            if isinstance(control, dict) and control.get("key") == "vulnerabilities":
                details = control.get("details") or {}
                blocking = int(details.get("blocking") or 0)
                warnings = int(details.get("warnings") or 0)
                vulnerabilities = blocking + warnings
                vulnerability_detail = (
                    f"{blocking} bloquante(s), {warnings} avertissement(s)"
                )
                break
    total_tasks = len(tasks)
    done_tasks = sum(1 for task in tasks if task.status == "done")
    blocked_tasks = [task for task in tasks if task.status == "blocked"]
    blocked_features = [feature for feature in features if feature.blocked]
    progress = round(done_tasks * 100 / total_tasks) if total_tasks else None
    ai_cost = round(sum(run.cost_eur or 0.0 for run in runs_with_cost), 2) if runs_with_cost else None

    kpis = [
        _kpi(
            "progress",
            "Avancement",
            progress,
            "%",
            "state.json",
            detail=f"{done_tasks} / {total_tasks} tâches terminées",
        ),
        _kpi(
            "gates",
            "Gates",
            blocking_gates if latest_gates else None,
            "bloquant(s)",
            "reports/gates/*.json",
            detail=(
                f"{len(latest_gates)} gate(s) exécuté(s) — {blocking_gates} bloquant(s)"
                if latest_gates
                else "aucun gate exécuté"
            ),
        ),
        _kpi(
            "coverage",
            "Couverture",
            coverage_percent,
            "%",
            "reports/coverage",
            detail=(
                "dernier gate de couverture"
                if coverage_percent is not None
                else "aucune preuve de couverture"
            ),
        ),
        _kpi(
            "vulnerabilities",
            "Vulnérabilités",
            vulnerabilities,
            None,
            "reports/security",
            detail=vulnerability_detail,
        ),
        _kpi(
            "ai_cost",
            "Coût IA",
            ai_cost,
            "€",
            "runs.jsonl",
            detail=f"{len(runs_with_cost)} run(s) avec coût" if runs_with_cost else "aucun coût ingéré",
        ),
        _kpi(
            "lead_time",
            "Délai spec→prod",
            None,
            "jours",
            "features + deploys.jsonl",
            detail="dates spec/prod insuffisantes",
        ),
    ]

    decisions: list[dict[str, Any]] = []
    for feature in blocked_features:
        decisions.append(
            {
                "id": f"feature:{feature.id}",
                "kind": "feature_bloquee",
                "title": f"{feature.key} · {feature.name}",
                "blocking": True,
                "source": "state.json",
                "detail": "feature marquée bloquée",
                "link": None,
            }
        )
    for task in blocked_tasks:
        decisions.append(
            {
                "id": f"task:{task.id}",
                "kind": "tache_bloquee",
                "title": f"{task.feature.key} · {task.key} {task.title}",
                "blocking": True,
                "source": "state.json",
                "detail": task.note or "tâche bloquée",
                "link": None,
            }
        )
    decisions.sort(key=lambda decision: (not bool(decision["blocking"]), str(decision["title"])))

    risks: list[dict[str, Any]] = []
    for task in blocked_tasks:
        risks.append(
            {
                "category": "projet",
                "severity": "haute",
                "title": f"Tâche bloquée {task.key}",
                "detail": task.note or task.title,
                "source": "state.json",
            }
        )
    for feature in blocked_features:
        risks.append(
            {
                "category": "projet",
                "severity": "haute",
                "title": f"Feature bloquée {feature.key}",
                "detail": feature.name,
                "source": "state.json",
            }
        )
    deployment_status, version, deployment_detail = _deployment_status(deployments)
    if deployment_status == "failed":
        risks.append(
            {
                "category": "déploiement",
                "severity": "haute",
                "title": "Dernier déploiement prod en échec ou rollback",
                "detail": f"{version or 'version non mesurée'} — {deployment_detail}",
                "source": "deploys.jsonl",
            }
        )

    risk_categories: dict[str, list[dict[str, Any]]] = {
        "données": [],
        "sécurité": [],
        "performance": [],
        "tests": [],
        "projet": [],
        "déploiement": [],
    }
    for risk in risks:
        risk_categories.setdefault(str(risk["category"]), []).append(risk)

    return {
        "generated_at": _iso(utc_now()),
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "summary": {
            "features": len(features),
            "tasks": total_tasks,
            "done": done_tasks,
            "doing": sum(1 for task in tasks if task.status == "doing"),
            "todo": sum(1 for task in tasks if task.status == "todo"),
            "blocked": len(blocked_tasks),
        },
        "kpis": kpis,
        "pending_decisions": decisions,
        "pending_decisions_source": "state.json",
        "pipeline": _pipeline(features, tasks, deployments),
        "risks": risks,
        "risk_categories": risk_categories,
        "risks_source": "state.json / deploys.jsonl",
    }
