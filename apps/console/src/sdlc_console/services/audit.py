"""Journal d'audit chaîné par projet."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditEvent, utc_now


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
    generation = last.generation if last is not None else 1
    prev_hash = last.hash if last is not None else ""
    payload_json = canonical_payload(payload)
    body = json.dumps(
        {
            "project_id": project_id,
            "actor_person_id": actor_person_id,
            "actor_label": actor_label,
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
        actor_label=actor_label,
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
