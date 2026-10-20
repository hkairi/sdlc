"""Vues Features & tâches : listes filtrées, détail et incohérences."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Feature, Project, SuiviInconsistency, Task, utc_now

STATUS_LABELS = {
    "todo": "À faire",
    "doing": "En cours",
    "done": "Terminé",
    "blocked": "Bloqué",
    "cancelled": "Annulé",
}

NOT_MEASURED = {
    "status": "not_measured",
    "value": None,
    "label": "non mesuré",
}


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


def _json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _person_label(person: Any, fallback: str | None) -> str | None:
    if person is not None:
        return str(person.display_name)
    return fallback


def _task_executor(task: Task) -> str | None:
    return _person_label(task.owner, task.executor_label)


def _task_reviewer(task: Task) -> str | None:
    return _person_label(task.reviewer, task.reviewer_label)


def _phase_status(statuses: list[str]) -> str:
    if any(status in {"failed", "blocked"} for status in statuses):
        return "failed"
    if statuses and all(status == "done" for status in statuses):
        return "done"
    if any(status in {"doing", "done", "in_progress"} for status in statuses):
        return "doing"
    return "todo"


def _phase_for_feature(feature: Feature) -> dict[str, Any]:
    phases = [
        phase
        for phase in _json_list(feature.phases_json)
        if isinstance(phase, dict)
    ]
    if not phases:
        return {
            "id": "non_mesure",
            "name": "Non mesuré",
            "status": "not_measured",
            "source": "state.json",
        }
    phases.sort(key=lambda phase: int(phase.get("order", 0) or 0))
    task_statuses = [task.status for task in feature.tasks]
    for phase in phases:
        phase_id = str(phase.get("id") or phase.get("name") or "phase")
        phase_name = str(phase.get("name") or phase_id)
        items = phase.get("items")
        statuses = [
            str(item.get("status", "todo")).lower()
            for item in (items if isinstance(items, list) else [])
            if isinstance(item, dict)
        ]
        implementation = phase_id in {"impl", "implementation"}
        if not statuses:
            if implementation:
                if task_statuses and all(status == "done" for status in task_statuses):
                    continue
                if any(status in {"doing", "done"} for status in task_statuses):
                    status = "doing"
                elif task_statuses:
                    status = "todo"
                else:
                    status = "not_measured"
                return {
                    "id": phase_id,
                    "name": phase_name,
                    "status": status,
                    "source": "state.json + tasks",
                }
            continue
        if all(status == "done" for status in statuses):
            continue
        return {
            "id": phase_id,
            "name": phase_name,
            "status": _phase_status(statuses),
            "source": "state.json",
        }
    last = phases[-1]
    last_id = str(last.get("id") or last.get("name") or "phase")
    return {
        "id": last_id,
        "name": str(last.get("name") or last_id),
        "status": "done",
        "source": "state.json",
    }


def _task_summary(task: Task, project: Project) -> dict[str, Any]:
    return {
        "id": task.id,
        "key": task.key,
        "title": task.title,
        "status": task.status,
        "status_label": STATUS_LABELS.get(task.status, task.status),
        "lot": task.lot,
        "executor": _task_executor(task),
        "reviewer": _task_reviewer(task),
        "updated_at": _iso(task.updated_at),
        "report_url": f"/api/projects/{project.id}/tasks/{task.id}/report",
    }


def _inconsistency_data(item: SuiviInconsistency) -> dict[str, Any]:
    return {
        "id": item.id,
        "feature_key": item.feature_key,
        "task_key": item.task_key,
        "kind": item.kind,
        "message": item.message,
        "state_status": item.state_status,
        "tasks_md_checked": item.tasks_md_checked,
        "created_at": _iso(item.created_at),
    }


def _inconsistencies_by_feature(
    session: Session,
    project: Project,
) -> dict[str, list[dict[str, Any]]]:
    rows = session.scalars(
        select(SuiviInconsistency)
        .where(SuiviInconsistency.project_id == project.id)
        .order_by(SuiviInconsistency.feature_key, SuiviInconsistency.task_key)
    ).all()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.feature_key, []).append(_inconsistency_data(row))
    return grouped


def _feature_data(
    feature: Feature,
    project: Project,
    inconsistencies: list[dict[str, Any]],
) -> dict[str, Any]:
    tasks = sorted(feature.tasks, key=lambda task: task.key)
    executors = sorted(
        {
            label
            for task in tasks
            if (label := _task_executor(task)) is not None
        }
    )
    reviewers = sorted(
        {
            label
            for task in tasks
            if (label := _task_reviewer(task)) is not None
        }
    )
    counts = {
        status: sum(1 for task in tasks if task.status == status)
        for status in STATUS_LABELS
    }
    done = counts["done"]
    phase = _phase_for_feature(feature)
    return {
        "id": feature.id,
        "key": feature.key,
        "name": feature.name,
        "status": feature.status,
        "status_label": STATUS_LABELS.get(feature.status, feature.status),
        "phase": phase,
        "phase_id": phase["id"],
        "phase_name": phase["name"],
        "phase_status": phase["status"],
        "objective": feature.objective,
        "change": feature.change,
        "spec_path": feature.spec_path,
        "tasks_file": feature.tasks_file,
        "sources": _json_object(feature.sources_json),
        "version": feature.version,
        "delivered": feature.delivered,
        "blocked": feature.blocked,
        "repositories": [
            {"id": link.repository.id, "name": link.repository.name}
            for link in sorted(
                feature.repository_links,
                key=lambda link: link.repository.name,
            )
        ],
        "tasks": [_task_summary(task, project) for task in tasks],
        "task_summary": {
            "total": len(tasks),
            "done": done,
            "doing": counts["doing"],
            "todo": counts["todo"],
            "blocked": counts["blocked"],
            "progress_percent": round(done * 100 / len(tasks)) if tasks else 0,
        },
        "coverage": {
            **NOT_MEASURED,
            "source": "reports/coverage",
            "detail": "aucune preuve de couverture ingérée",
        },
        "gate": {
            **NOT_MEASURED,
            "source": "reports/gates",
            "detail": "aucun gate ingéré",
        },
        "executors": executors,
        "reviewers": reviewers,
        "updated_at": _iso(feature.updated_at),
        "inconsistencies": inconsistencies,
    }


def _phase_matches(phase_filter: str, phase: dict[str, Any]) -> bool:
    wanted = phase_filter.strip().casefold()
    return wanted in {
        str(phase.get("id", "")).casefold(),
        str(phase.get("name", "")).casefold(),
    }


def _gate_matches(gate_filter: str) -> bool:
    return gate_filter.strip().casefold() in {
        "non_mesure",
        "non mesuré",
        "none",
    }


def build_features_view(
    session: Session,
    project: Project,
    *,
    phase: str | None = None,
    gate: str | None = None,
) -> dict[str, Any]:
    """Liste les features avec filtres phase/gate et incohérences."""
    features = list(
        session.scalars(
            select(Feature).where(Feature.project_id == project.id).order_by(Feature.key)
        ).all()
    )
    inconsistencies = _inconsistencies_by_feature(session, project)
    all_data = [
        _feature_data(feature, project, inconsistencies.get(feature.key, []))
        for feature in features
    ]
    available_phases: list[dict[str, str]] = []
    seen_phases: set[str] = set()
    for feature in all_data:
        phase_id = str(feature["phase"]["id"])
        if phase_id not in seen_phases:
            seen_phases.add(phase_id)
            available_phases.append(
                {"id": phase_id, "name": str(feature["phase"]["name"])}
            )
    available_gates = [
        {"id": "non_mesure", "name": "Non mesuré", "source": "reports/gates"}
    ]

    filtered = all_data
    if phase:
        filtered = [
            feature for feature in filtered if _phase_matches(phase, feature["phase"])
        ]
    if gate:
        filtered = [] if not _gate_matches(gate) else filtered

    return {
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "filters": {"phase": phase, "gate": gate},
        "available_phases": available_phases,
        "available_gates": available_gates,
        "features": filtered,
        "total": len(filtered),
        "inconsistencies": [
            item
            for feature in all_data
            for item in feature["inconsistencies"]
        ],
        "sources": {
            "phase": "state.json",
            "coverage": "reports/coverage",
            "gate": "reports/gates",
            "inconsistencies": "tasks.md + state.json",
        },
    }


def build_feature_detail(
    session: Session,
    project: Project,
    feature_key: str,
) -> dict[str, Any] | None:
    feature = session.scalar(
        select(Feature).where(
            Feature.project_id == project.id,
            Feature.key == feature_key,
        )
    )
    if feature is None:
        return None
    grouped = _inconsistencies_by_feature(session, project)
    return {
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "feature": _feature_data(feature, project, grouped.get(feature.key, [])),
    }


def _task_base(task: Task, project: Project) -> dict[str, Any]:
    files = _json_list(task.files_json)
    return {
        "id": task.id,
        "key": task.key,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "status_label": STATUS_LABELS.get(task.status, task.status),
        "lot": task.lot,
        "files": files,
        "acceptance": task.acceptance,
        "note": task.note,
        "executor": _task_executor(task),
        "reviewer": _task_reviewer(task),
        "updated_at": _iso(task.updated_at),
        "feature": {
            "id": task.feature.id,
            "key": task.feature.key,
            "name": task.feature.name,
            "phase": _phase_for_feature(task.feature),
        },
        "repositories": [
            {"id": link.repository.id, "name": link.repository.name}
            for link in sorted(
                task.repository_links,
                key=lambda link: link.repository.name,
            )
        ],
        "report_url": f"/api/projects/{project.id}/tasks/{task.id}/report",
        "report_available": task.status == "done" or bool(task.note),
        "source": "state.json",
    }


def list_tasks_view(
    session: Session,
    project: Project,
    *,
    feature_key: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    query = (
        select(Task)
        .join(Feature, Task.feature_id == Feature.id)
        .where(Feature.project_id == project.id)
    )
    if feature_key:
        query = query.where(Feature.key == feature_key)
    if status:
        query = query.where(Task.status == status)
    tasks = list(
        session.scalars(
            query.order_by(Feature.key, Task.key)
        ).all()
    )
    data = []
    for task in tasks:
        item = _task_summary(task, project)
        item["feature_key"] = task.feature.key
        item["feature_name"] = task.feature.name
        item["phase"] = _phase_for_feature(task.feature)
        data.append(item)
    return {
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "filters": {"feature_key": feature_key, "status": status},
        "tasks": data,
        "total": len(data),
    }


def get_task_view(
    session: Session,
    project: Project,
    task_id: int,
) -> dict[str, Any] | None:
    task = session.scalar(
        select(Task)
        .join(Feature, Task.feature_id == Feature.id)
        .where(Feature.project_id == project.id, Task.id == task_id)
    )
    if task is None:
        return None
    return _task_base(task, project)


def build_task_report(
    session: Session,
    project: Project,
    task_id: int,
) -> dict[str, Any] | None:
    task = get_task_view(session, project, task_id)
    if task is None:
        return None
    return {
        "schema": 1,
        "generated_at": _iso(utc_now()),
        "source": "state.json",
        "task": task,
    }
