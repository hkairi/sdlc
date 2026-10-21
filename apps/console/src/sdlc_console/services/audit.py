"""Journal d'audit chaîné par projet."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditEvent, utc_now
from ..redaction import redact


def canonical_payload(payload: dict[str, Any] | None) -> str:
    """Sérialise un payload de façon déterministe."""
    return json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def append_audit(
    session: Session,
    *,
    project_id: int,
    action: str,
    object_type: str,
    object_id: str | int,
    actor_label: str = "système",
    actor_person_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    """Ajoute un événement et le chaîne au dernier événement du projet."""
    created_at = utc_now()
    last = session.scalar(
        select(AuditEvent)
        .where(AuditEvent.project_id == project_id)
        .order_by(AuditEvent.id.desc())
    )
    if last is not None and last.action == "audit.anchor":
        generation = last.generation + 1
        prev_hash = ""
    else:
        generation = last.generation if last is not None else 1
        prev_hash = last.hash if last is not None else ""
    payload_json = redact(canonical_payload(payload))
    clean_actor = redact(actor_label)
    body = json.dumps(
        {
            "project_id": project_id,
            "actor_person_id": actor_person_id,
            "actor_label": clean_actor,
            "action": action,
            "object_type": object_type,
            "object_id": str(object_id),
            "payload": json.loads(payload_json),
            "created_at": created_at.isoformat(),
            "generation": generation,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256((prev_hash + body).encode("utf-8")).hexdigest()
    event = AuditEvent(
        project_id=project_id,
        actor_person_id=actor_person_id,
        actor_label=clean_actor,
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        payload_json=payload_json,
        created_at=created_at,
        generation=generation,
        prev_hash=prev_hash,
        hash=digest,
    )
    session.add(event)
    session.flush()
    return event


def verify_audit_chain(session: Session, project_id: int) -> dict[str, Any]:
    """Recalcule la chaîne d'audit et signale toute altération."""
    from ..models import Project

    _ = session.get(Project, project_id)
    events = list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.project_id == project_id)
            .order_by(AuditEvent.id)
        ).all()
    )
    issues: list[str] = []
    previous: AuditEvent | None = None
    for event in events:
        if event.prev_hash != (previous.hash if previous is not None else ""):
            new_chain = event.prev_hash == "" and (
                previous is None or previous.action == "audit.anchor"
            )
            if not new_chain:
                issues.append(f"chaîne rompue avant l'événement {event.id}")
        expected = event_hash(event)
        if event.hash != expected:
            issues.append(f"empreinte invalide pour l'événement {event.id}")
        previous = event
    return {
        "valid": not issues,
        "issues": issues,
        "events": len(events),
        "generations": len({event.generation for event in events}),
    }


def anchor_audit(
    session: Session,
    project_id: int,
    *,
    actor_label: str = "système",
    reason: str = "ancrage avant purge",
) -> AuditEvent:
    """Clôt la génération courante ; les événements suivants ouvrent une génération."""
    return append_audit(
        session,
        project_id=project_id,
        action="audit.anchor",
        object_type="audit_chain",
        object_id=project_id,
        actor_label=actor_label,
        payload={"reason": reason},
    )


def event_hash(event: AuditEvent) -> str:
    """Recalcule l'empreinte d'un événement avec ses champs actuels."""
    created_at = (
        event.created_at.replace(tzinfo=UTC)
        if event.created_at.tzinfo is None
        else event.created_at.astimezone(UTC)
    )
    body = json.dumps(
        {
            "project_id": event.project_id,
            "actor_person_id": event.actor_person_id,
            "actor_label": event.actor_label,
            "action": event.action,
            "object_type": event.object_type,
            "object_id": event.object_id,
            "payload": json.loads(event.payload_json),
            "created_at": created_at.isoformat(),
            "generation": event.generation,
            "prev_hash": event.prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256((event.prev_hash + body).encode("utf-8")).hexdigest()


def reseal_audit_event(event: AuditEvent, *, generation: int | None = None) -> AuditEvent:
    """Fait d'un événement conservé le premier maillon d'une nouvelle chaîne."""
    event.prev_hash = ""
    if generation is not None:
        event.generation = generation
    event.hash = event_hash(event)
    return event
