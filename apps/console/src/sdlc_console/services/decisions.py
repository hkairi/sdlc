"""Décisions humaines : approbation, conditions, rejet et demande d'information."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Decision, Person, Project, ReviewReport
from ..redaction import redact
from .audit import append_audit

DECISION_TYPES = frozenset(
    {"approve", "approve_with_conditions", "reject", "info"}
)


class DecisionError(ValueError):
    """Décision humaine invalide."""


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def decision_data(record: Decision) -> dict[str, Any]:
    return {
        "id": record.id,
        "subject_type": record.subject_type,
        "subject_id": record.subject_id,
        "decision": record.decision,
        "actor_person_id": record.actor_person_id,
        "actor_label": record.actor_label,
        "reason": record.reason,
        "conditions": json.loads(record.conditions_json),
        "scope": record.scope,
        "created_at": record.created_at.isoformat(),
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "unauthenticated": "non authentifiée" in record.actor_label.casefold(),
    }


def create_decision(
    session: Session,
    project: Project,
    *,
    subject_type: str,
    subject_id: str,
    decision: str,
    reason: str,
    conditions: Sequence[str] = (),
    actor_label: str = "décision depuis le poste local, non authentifiée",
    actor_person_id: int | None = None,
    scope: str | None = None,
    expires_at: datetime | None = None,
    config: Mapping[str, Any] | None = None,
) -> Decision:
    """Enregistre une décision motivée et l'audite."""
    if decision not in DECISION_TYPES:
        raise DecisionError(f"décision invalide : {decision}")
    if not subject_type.strip() or not subject_id.strip():
        raise DecisionError("sujet de décision requis")
    if not reason.strip():
        raise DecisionError("motif de décision requis")
    if decision == "approve_with_conditions" and not conditions:
        raise DecisionError("conditions requises pour une approbation conditionnelle")
    if actor_person_id is not None:
        person = session.get(Person, actor_person_id)
        if person is None or person.project_id != project.id:
            raise DecisionError(f"acteur hors du projet : {actor_person_id}")
    record = Decision(
        project_id=project.id,
        subject_type=subject_type.strip(),
        subject_id=subject_id.strip(),
        decision=decision,
        actor_person_id=actor_person_id,
        actor_label=redact(actor_label.strip() or "orchestrateur local"),
        reason=redact(reason.strip()),
        conditions_json=redact(json.dumps(list(conditions), ensure_ascii=False)),
        scope=redact(scope) if scope else None,
        expires_at=_utc(expires_at),
    )
    session.add(record)
    session.flush()
    append_audit(
        session,
        project_id=project.id,
        action="decision.recorded",
        object_type=subject_type.strip(),
        object_id=subject_id.strip(),
        actor_label=record.actor_label,
        actor_person_id=actor_person_id,
        payload={
            "decision": decision,
            "reason": record.reason,
            "conditions": list(conditions),
            "scope": scope,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "unauthenticated": "non authentifiée" in record.actor_label.casefold(),
        },
    )
    if decision == "reject" and subject_type.strip() == "review_report":
        from .escalations import escalate_review_rejections, task_for_review_report

        try:
            report_id = int(subject_id)
        except (TypeError, ValueError):
            report_id = None
        report = session.get(ReviewReport, report_id) if report_id is not None else None
        if report is not None:
            task = task_for_review_report(session, project, report)
            if task is not None:
                escalate_review_rejections(session, project, task, config=config)
    return record


def list_decisions(
    session: Session,
    project: Project,
    *,
    subject_type: str | None = None,
    subject_id: str | None = None,
) -> list[Decision]:
    query = select(Decision).where(Decision.project_id == project.id)
    if subject_type:
        query = query.where(Decision.subject_type == subject_type)
    if subject_id:
        query = query.where(Decision.subject_id == subject_id)
    return list(session.scalars(query.order_by(Decision.id.desc())).all())


def project_for_review(
    session: Session,
    review_id: int,
) -> tuple[Project, ReviewReport] | None:
    report = session.get(ReviewReport, review_id)
    if report is None:
        return None
    project = session.get(Project, report.project_id)
    if project is None:
        return None
    return project, report
