"""Profils de processus par dépôt, agrégation et surcharges auditées."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ProcessOverride, Project, Repository, utc_now
from .audit import append_audit
from .process_detection import (
    PROFILE_LABELS,
    ProcessDetection,
    detect_repository_process,
)
from .projects import list_repositories

OVERRIDABLE_KEYS = frozenset(
    key for key in PROFILE_LABELS if key != "unknown"
)


class ProcessError(ValueError):
    """Surcharge ou agrégation de processus invalide."""


def _override_data(record: ProcessOverride) -> dict[str, Any]:
    return {
        "id": record.id,
        "repository_id": record.repository_id,
        "profile_key": record.profile_key,
        "label": PROFILE_LABELS.get(record.profile_key, record.profile_key),
        "reason": record.reason,
        "actor_label": record.actor_label,
        "created_at": record.created_at.isoformat(),
    }


def latest_overrides(
    session: Session,
    project: Project,
) -> tuple[dict[int, ProcessOverride], ProcessOverride | None]:
    """Dernière surcharge par dépôt et surcharge projet éventuelle."""
    records = list(
        session.scalars(
            select(ProcessOverride)
            .where(ProcessOverride.project_id == project.id)
            .order_by(ProcessOverride.id.desc())
        ).all()
    )
    by_repository: dict[int, ProcessOverride] = {}
    project_override = None
    for record in records:
        if record.repository_id is None:
            if project_override is None:
                project_override = record
        elif record.repository_id not in by_repository:
            by_repository[record.repository_id] = record
    return by_repository, project_override


def create_override(
    session: Session,
    project: Project,
    *,
    repository_id: int | None,
    profile_key: str,
    reason: str,
    actor_label: str = "orchestrateur local",
) -> ProcessOverride:
    """Enregistre une surcharge datée, motivée et auditée."""
    if profile_key not in OVERRIDABLE_KEYS:
        raise ProcessError(f"profil de processus invalide : {profile_key}")
    if not reason.strip():
        raise ProcessError("motif de surcharge requis")
    if repository_id is not None:
        repository = session.get(Repository, repository_id)
        if repository is None or repository.project_id != project.id:
            raise ProcessError(f"dépôt introuvable : {repository_id}")
    record = ProcessOverride(
        project_id=project.id,
        repository_id=repository_id,
        profile_key=profile_key,
        reason=reason.strip(),
        actor_label=actor_label.strip() or "orchestrateur local",
        created_at=utc_now(),
    )
    session.add(record)
    session.flush()
    append_audit(
        session,
        project_id=project.id,
        action="process.override",
        object_type="process_override",
        object_id=record.id,
        actor_label=record.actor_label,
        payload={
            "repository_id": repository_id,
            "profile_key": profile_key,
            "label": PROFILE_LABELS.get(profile_key, profile_key),
            "reason": record.reason,
        },
    )
    return record


def _profile_payload(
    repository: Repository,
    detection: ProcessDetection | Mapping[str, Any],
    *,
    override: ProcessOverride | None,
) -> dict[str, Any]:
    if isinstance(detection, Mapping):
        detected = {
            "key": str(detection.get("key") or detection.get("profile") or "unknown"),
            "label": str(detection.get("label") or PROFILE_LABELS.get(str(detection.get("key")), "non identifiable")),
            "confidence": detection.get("confidence"),
            "detected": bool(detection.get("detected", False)),
            "signals": list(detection.get("signals") or []),
            "reasons": list(detection.get("reasons") or []),
            "scores": dict(detection.get("scores") or {}),
        }
    else:
        detected = {
            "key": detection.key,
            "label": detection.label,
            "confidence": detection.confidence,
            "detected": detection.detected,
            "signals": list(detection.signals),
            "reasons": list(detection.reasons),
            "scores": dict(detection.scores),
        }
    effective_key = override.profile_key if override is not None else detected["key"]
    effective_label = (
        PROFILE_LABELS.get(override.profile_key, override.profile_key)
        if override is not None
        else detected["label"]
    )
    return {
        "repository_id": repository.id,
        "repository_name": repository.name,
        "profile": effective_key,
        "label": effective_label,
        "confidence": None if override is not None else detected["confidence"],
        "detected": True,
        "source": "override" if override is not None else "detected",
        "detected_profile": detected,
        "override": _override_data(override) if override is not None else None,
        "signals": detected["signals"],
        "reasons": detected["reasons"],
        "scores": detected["scores"],
    }


def build_process_inventory(
    session: Session,
    project: Project,
    *,
    repository_ids: Sequence[int] | None = None,
    detections: Mapping[int, ProcessDetection | Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Agrège les profils détectés sans moyenne pondérée inventée."""
    repositories = list_repositories(session, project)
    if repository_ids is not None:
        wanted = set(repository_ids)
        available = {repository.id for repository in repositories}
        missing = wanted - available
        if missing:
            raise ValueError(f"dépôts inconnus ou retirés : {sorted(missing)}")
        repositories = [repository for repository in repositories if repository.id in wanted]
    if not repositories:
        return {
            "generated_at": utc_now().isoformat(),
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "repositories": [],
            "dominant_profile": None,
            "project_profile": None,
            "divergent": False,
            "divergences": [],
            "status": "not_measured",
        }
    overrides, project_override = latest_overrides(session, project)
    profiles = []
    for repository in repositories:
        detection = (
            detections.get(repository.id)
            if detections is not None and repository.id in detections
            else None
        ) or detect_repository_process(repository.local_path)
        profiles.append(
            _profile_payload(
                repository,
                detection,
                override=overrides.get(repository.id),
            )
        )
    counts: dict[str, int] = {}
    for profile in profiles:
        counts[profile["profile"]] = counts.get(profile["profile"], 0) + 1
    max_count = max(counts.values()) if counts else 0
    winners = [key for key, count in counts.items() if count == max_count]
    dominant = None
    if len(winners) == 1 and winners[0] != "unknown":
        dominant = {
            "key": winners[0],
            "label": PROFILE_LABELS.get(winners[0], winners[0]),
            "count": max_count,
            "total": len(profiles),
        }
    divergences = []
    if len(counts) > 1:
        for key, count in sorted(counts.items()):
            divergences.append(
                {
                    "key": key,
                    "label": PROFILE_LABELS.get(key, key),
                    "count": count,
                    "repositories": [
                        profile["repository_name"]
                        for profile in profiles
                        if profile["profile"] == key
                    ],
                }
            )
    effective_project = (
        {
            "key": project_override.profile_key,
            "label": PROFILE_LABELS.get(project_override.profile_key, project_override.profile_key),
            "source": "override",
            "override": _override_data(project_override),
        }
        if project_override is not None
        else (
            {**dominant, "source": "detected"}
            if dominant is not None
            else None
        )
    )
    return {
        "generated_at": utc_now().isoformat(),
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "repositories": profiles,
        "profiles": [
            {
                "key": key,
                "label": PROFILE_LABELS.get(key, key),
                "count": count,
            }
            for key, count in sorted(counts.items())
        ],
        "dominant_profile": dominant,
        "project_profile": effective_project,
        "divergent": len(counts) > 1,
        "divergences": divergences,
        "overrides": [
            _override_data(record)
            for record in [*overrides.values(), *([project_override] if project_override else [])]
        ],
        "status": "measured" if profiles else "not_measured",
    }
