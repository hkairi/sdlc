"""Exports JSON/CSV expurgés des secrets et prompts sensibles."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Feature, IngestionRun, Project, Task
from ..redaction import redact, redact_value
from .gates import latest_gate_runs
from .run_journal import build_run_journal

ExportFormat = Literal["json", "csv"]


@dataclass(frozen=True)
class ExportResult:
    content: str
    media_type: str
    filename: str


def _ingestions(session: Session, project: Project) -> list[dict[str, Any]]:
    rows = list(
        session.scalars(
            select(IngestionRun)
            .where(IngestionRun.project_id == project.id)
            .order_by(IngestionRun.id.desc())
            .limit(500)
        ).all()
    )
    data: list[dict[str, Any]] = []
    for row in rows:
        try:
            stats = json.loads(row.stats_json)
        except json.JSONDecodeError:
            stats = {"raw": row.stats_json}
        data.append(
            {
                "id": row.id,
                "source": row.source,
                "status": row.status,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "stats": redact_value(stats),
                "error": row.error,
            }
        )
    return data


def _export_data(
    session: Session,
    project: Project,
    *,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    features = list(
        session.scalars(
            select(Feature).where(Feature.project_id == project.id).order_by(Feature.key)
        ).all()
    )
    tasks = list(
        session.scalars(
            select(Task)
            .join(Feature, Task.feature_id == Feature.id)
            .where(Feature.project_id == project.id)
            .order_by(Feature.key, Task.key)
        ).all()
    )
    journal = build_run_journal(session, project, limit=2000)
    data = {
        "schema": 1,
        "notice": "Fichier généré, ne pas modifier.",
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "features": [
            {
                "id": feature.id,
                "key": feature.key,
                "name": feature.name,
                "status": feature.status,
                "objective": feature.objective,
                "version": feature.version,
            }
            for feature in features
        ],
        "tasks": [
            {
                "id": task.id,
                "feature_key": task.feature.key,
                "key": task.key,
                "title": task.title,
                "status": task.status,
                "description": task.description,
                "note": task.note,
                "acceptance": task.acceptance,
                "executor": task.executor_label,
                "reviewer": task.reviewer_label,
            }
            for task in tasks
        ],
        "runs": journal["runs"],
        "gates": latest_gate_runs(session, project),
        "ingestions": _ingestions(session, project),
    }
    return redact_value(data)  # type: ignore[return-value]


def _csv(data: dict[str, Any]) -> str:
    buffer = io.StringIO()
    fieldnames = [
        "type",
        "feature_key",
        "key",
        "title",
        "status",
        "executor",
        "reviewer",
        "note",
        "agent_id",
        "role",
        "model",
        "cost_eur",
        "tokens_in",
        "tokens_out",
    ]
    buffer.write("# Fichier généré, ne pas modifier.\n")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for task in data.get("tasks", []):
        writer.writerow(
            {
                "type": "task",
                "feature_key": task.get("feature_key"),
                "key": task.get("key"),
                "title": task.get("title"),
                "status": task.get("status"),
                "executor": task.get("executor"),
                "reviewer": task.get("reviewer"),
                "note": task.get("note"),
            }
        )
    for run in data.get("runs", []):
        writer.writerow(
            {
                "type": "run",
                "key": run.get("task_key"),
                "status": run.get("status"),
                "agent_id": run.get("agent_id"),
                "role": run.get("role"),
                "model": run.get("model"),
                "cost_eur": run.get("cost_eur"),
                "tokens_in": run.get("tokens_in"),
                "tokens_out": run.get("tokens_out"),
            }
        )
    return buffer.getvalue()


def build_export(
    session: Session,
    project: Project,
    *,
    format: ExportFormat = "json",
    config: Mapping[str, Any] | None = None,
) -> ExportResult:
    data = _export_data(session, project, config=config)
    if format == "csv":
        content = _csv(data)
        return ExportResult(
            content=content,
            media_type="text/csv; charset=utf-8",
            filename=f"console-{project.slug}.csv",
        )
    content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    return ExportResult(
        content=redact(content) + "\n",
        media_type="application/json; charset=utf-8",
        filename=f"console-{project.slug}.json",
    )
