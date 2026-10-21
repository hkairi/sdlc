"""Escalades humaines après rejets répétés ou dépassement de délai."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Decision,
    Feature,
    HumanNotification,
    Project,
    ReviewPackage,
    ReviewReport,
    Task,
    utc_now,
)
from .audit import append_audit

DEFAULT_MAX_ITERATIONS = 3
DEFAULT_TASK_TIMEOUT_MIN = 60


class EscalationError(ValueError):
    """Escalade invalide."""


def _settings(config: Mapping[str, Any] | None) -> tuple[int, int]:
    config = config or {}
    organisation = config.get("organisation")
    organisation = organisation if isinstance(organisation, Mapping) else {}
    review = config.get("review")
    review = review if isinstance(review, Mapping) else {}
    max_iterations = organisation.get("max_review_iterations") or review.get("max_iterations")
    timeout_min = organisation.get("task_timeout_min")
    return (
        max(1, int(max_iterations or DEFAULT_MAX_ITERATIONS)),
        max(1, int(timeout_min or DEFAULT_TASK_TIMEOUT_MIN)),
    )


def notification_data(notification: HumanNotification) -> dict[str, Any]:
    return {
        "id": notification.id,
        "kind": notification.kind,
        "subject_type": notification.subject_type,
        "subject_id": notification.subject_id,
        "message": notification.message,
        "payload": json.loads(notification.payload_json),
        "created_at": notification.created_at.isoformat(),
        "acknowledged_at": (
            notification.acknowledged_at.isoformat()
            if notification.acknowledged_at is not None
            else None
        ),
        "acknowledged_by": notification.acknowledged_by,
        "pending": notification.acknowledged_at is None,
    }


def notify_human(
    session: Session,
    project: Project,
    *,
    kind: str,
    subject_type: str,
    subject_id: str,
    message: str,
    payload: Mapping[str, Any] | None = None,
) -> tuple[HumanNotification, bool]:
    """Crée une notification idempotente tant qu'elle n'est pas acquittée."""
    existing = session.scalar(
        select(HumanNotification)
        .where(
            HumanNotification.project_id == project.id,
            HumanNotification.kind == kind,
            HumanNotification.subject_type == subject_type,
            HumanNotification.subject_id == subject_id,
            HumanNotification.acknowledged_at.is_(None),
        )
        .order_by(HumanNotification.id.desc())
    )
    if existing is not None:
        return existing, False
    notification = HumanNotification(
        project_id=project.id,
        kind=kind,
        subject_type=subject_type,
        subject_id=subject_id,
        message=message,
        payload_json=json.dumps(dict(payload or {}), ensure_ascii=False, sort_keys=True),
    )
    session.add(notification)
    session.flush()
    append_audit(
        session,
        project_id=project.id,
        action="human.notified",
        object_type=subject_type,
        object_id=subject_id,
        payload={"kind": kind, "message": message, "notification_id": notification.id},
    )
    return notification, True


def acknowledge_notification(
    session: Session,
    project: Project,
    notification: HumanNotification,
    *,
    actor_label: str = "décision depuis le poste local, non authentifiée",
) -> HumanNotification:
    if notification.project_id != project.id:
        raise EscalationError("notification hors du projet")
    notification.acknowledged_at = utc_now()
    notification.acknowledged_by = actor_label
    append_audit(
        session,
        project_id=project.id,
        action="notification.acknowledged",
        object_type=notification.subject_type,
        object_id=notification.subject_id,
        actor_label=actor_label,
        payload={"notification_id": notification.id, "kind": notification.kind},
    )
    session.flush()
    return notification


def task_for_review_report(
    session: Session,
    project: Project,
    report: ReviewReport,
) -> Task | None:
    package = session.get(ReviewPackage, report.package_id)
    if package is None:
        return None
    query = (
        select(Task)
        .join(Feature, Task.feature_id == Feature.id)
        .where(Feature.project_id == project.id, Task.key == package.task_key)
    )
    tasks = list(session.scalars(query).all())
    if package.feature_key:
        tasks = [task for task in tasks if task.feature.key == package.feature_key]
    if len(tasks) != 1:
        return None
    return tasks[0]


def _rejections_for_task(
    session: Session,
    project: Project,
    task: Task,
) -> list[dict[str, Any]]:
    decisions = list(
        session.scalars(
            select(Decision)
            .where(
                Decision.project_id == project.id,
                Decision.subject_type == "review_report",
                Decision.decision == "reject",
            )
            .order_by(Decision.id)
        ).all()
    )
    iterations: list[dict[str, Any]] = []
    for decision in decisions:
        try:
            report_id = int(decision.subject_id)
        except (TypeError, ValueError):
            continue
        report = session.get(ReviewReport, report_id)
        if report is None:
            continue
        if task_for_review_report(session, project, report) != task:
            continue
        iterations.append(
            {
                "decision_id": decision.id,
                "report_id": report.id,
                "reason": decision.reason,
                "created_at": decision.created_at.isoformat(),
            }
        )
    return iterations


def escalate_review_rejections(
    session: Session,
    project: Project,
    task: Task,
    *,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Bloque et notifie une tâche ayant atteint le nombre maximal de rejets."""
    max_iterations, _ = _settings(config)
    iterations = _rejections_for_task(session, project, task)
    if len(iterations) < max_iterations or task.status == "blocked":
        return None
    task.status = "blocked"
    task.updated_at = utc_now()
    notification, created = notify_human(
        session,
        project,
        kind="review_escalation",
        subject_type="task",
        subject_id=str(task.id),
        message=(
            f"Tâche {task.feature.key} · {task.key} bloquée après "
            f"{len(iterations)} rejets (maximum {max_iterations})."
        ),
        payload={
            "task_key": task.key,
            "feature_key": task.feature.key,
            "max_iterations": max_iterations,
            "rejections": iterations,
        },
    )
    if created:
        append_audit(
            session,
            project_id=project.id,
            action="task.escalated",
            object_type="task",
            object_id=str(task.id),
            payload={
                "reason": "review_rejections",
                "task_key": task.key,
                "feature_key": task.feature.key,
                "max_iterations": max_iterations,
                "iterations": iterations,
                "notification_id": notification.id,
            },
        )
    session.flush()
    return {
        "task_id": task.id,
        "status": task.status,
        "max_iterations": max_iterations,
        "iterations": iterations,
        "notification": notification_data(notification),
    }


def escalate_timed_out_tasks(
    session: Session,
    project: Project,
    *,
    config: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Bloque les tâches `doing` au-delà de `task_timeout_min`."""
    _, timeout_min = _settings(config)
    moment = now or utc_now()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    limit = timedelta(minutes=timeout_min)
    tasks = list(
        session.scalars(
            select(Task)
            .join(Feature, Task.feature_id == Feature.id)
            .where(
                Feature.project_id == project.id,
                Task.status == "doing",
            )
        ).all()
    )
    escalated: list[dict[str, Any]] = []
    for task in tasks:
        updated = task.updated_at
        if updated is None:
            continue
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=UTC)
        elapsed = moment - updated
        if elapsed <= limit:
            continue
        task.status = "blocked"
        task.updated_at = moment
        notification, created = notify_human(
            session,
            project,
            kind="task_timeout",
            subject_type="task",
            subject_id=str(task.id),
            message=(
                f"Tâche {task.feature.key} · {task.key} bloquée : "
                f"{elapsed.total_seconds() / 60:.0f} min > {timeout_min} min."
            ),
            payload={
                "task_key": task.key,
                "feature_key": task.feature.key,
                "elapsed_minutes": round(elapsed.total_seconds() / 60, 1),
                "task_timeout_min": timeout_min,
            },
        )
        if created:
            append_audit(
                session,
                project_id=project.id,
                action="task.escalated",
                object_type="task",
                object_id=str(task.id),
                payload={
                    "reason": "task_timeout",
                    "task_key": task.key,
                    "feature_key": task.feature.key,
                    "elapsed_minutes": round(elapsed.total_seconds() / 60, 1),
                    "task_timeout_min": timeout_min,
                    "notification_id": notification.id,
                },
            )
        escalated.append(
            {
                "task_id": task.id,
                "status": task.status,
                "elapsed_minutes": round(elapsed.total_seconds() / 60, 1),
                "notification": notification_data(notification),
            }
        )
    session.flush()
    return escalated
