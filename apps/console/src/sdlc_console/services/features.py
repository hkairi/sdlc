"""Services features, tâches et liaisons multi-dépôts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Feature,
    FeatureRepository,
    Person,
    Project,
    Repository,
    Task,
    TaskRepository,
    utc_now,
)

FEATURE_STATUSES = frozenset({"todo", "doing", "done", "blocked", "cancelled"})
TASK_STATUSES = frozenset({"todo", "doing", "done", "blocked", "cancelled"})


class FeatureError(ValueError):
    """Erreur métier sur une feature ou une tâche."""


def _status(value: str, allowed: frozenset[str], label: str) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise FeatureError(f"statut de {label} invalide : {value}")
    return normalized


def _validate_person(person: Person | None, project: Project, label: str) -> None:
    if person is not None and person.project_id != project.id:
        raise FeatureError(f"{label} hors du projet")


def _validate_repository(
    session: Session,
    project: Project,
    repository_id: int,
) -> Repository:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.project_id != project.id:
        raise FeatureError(f"dépôt inconnu dans le projet : {repository_id}")
    if repository.retired_at is not None:
        raise FeatureError(f"dépôt retiré : {repository_id}")
    return repository


def _validated_ids(
    session: Session,
    project: Project,
    repository_ids: Sequence[int] | None,
    primary_repository_id: int | None,
) -> list[int]:
    ids = list(dict.fromkeys(repository_ids or []))
    if primary_repository_id is not None and primary_repository_id not in ids:
        ids.append(primary_repository_id)
    for repository_id in ids:
        _validate_repository(session, project, repository_id)
    return ids


def _sync_feature_repositories(
    session: Session,
    feature: Feature,
    repository_ids: Sequence[int],
    primary_repository_id: int | None,
) -> None:
    wanted = set(repository_ids)
    existing = {link.repository_id: link for link in feature.repository_links}
    for repository_id, link in list(existing.items()):
        if repository_id not in wanted:
            session.delete(link)
            feature.repository_links.remove(link)
    for repository_id in repository_ids:
        if repository_id not in existing:
            feature.repository_links.append(
                FeatureRepository(feature_id=feature.id, repository_id=repository_id)
            )
    feature.primary_repository_id = primary_repository_id
    feature.updated_at = utc_now()
    session.flush()


def _sync_task_repositories(
    session: Session,
    task: Task,
    repository_ids: Sequence[int],
    primary_repository_id: int | None,
) -> None:
    wanted = set(repository_ids)
    existing = {link.repository_id: link for link in task.repository_links}
    for link in existing.values():
        link.is_primary = False
    session.flush()
    for repository_id, link in list(existing.items()):
        if repository_id not in wanted:
            session.delete(link)
            task.repository_links.remove(link)
    for repository_id in repository_ids:
        existing_link = existing.get(repository_id)
        if existing_link is None:
            existing_link = TaskRepository(task_id=task.id, repository_id=repository_id)
            task.repository_links.append(existing_link)
        existing_link.is_primary = repository_id == primary_repository_id
    task.primary_repository_id = primary_repository_id
    task.updated_at = utc_now()
    session.flush()


def create_feature(
    session: Session,
    project: Project,
    *,
    key: str,
    name: str,
    status: str = "todo",
    primary_repository: Repository | None = None,
    repository_ids: Sequence[int] | None = None,
    owner_person: Person | None = None,
    spec_path: str | None = None,
    change: str | None = None,
    objective: str | None = None,
    tasks_file: str | None = None,
    sources: Mapping[str, Any] | None = None,
    delivered: bool = False,
    blocked: bool = False,
    version: str | None = None,
) -> Feature:
    """Crée une feature et ses dépôts couverts."""
    normalized_key = key.strip()
    normalized_name = name.strip()
    if not normalized_key or not normalized_name:
        raise FeatureError("clé et nom de feature requis")
    _validate_person(owner_person, project, "propriétaire")
    primary_id = primary_repository.id if primary_repository is not None else None
    if primary_repository is not None:
        _validate_repository(session, project, primary_repository.id)
    ids = _validated_ids(session, project, repository_ids, primary_id)
    feature = Feature(
        project_id=project.id,
        primary_repository_id=primary_id,
        key=normalized_key,
        name=normalized_name,
        status=_status(status, FEATURE_STATUSES, "feature"),
        owner_person_id=owner_person.id if owner_person is not None else None,
        spec_path=spec_path,
        change=change,
        objective=objective,
        tasks_file=tasks_file,
        sources_json=json.dumps(dict(sources or {}), sort_keys=True, ensure_ascii=False),
        delivered=delivered,
        blocked=blocked,
        version=version,
        updated_at=utc_now(),
    )
    session.add(feature)
    session.flush()
    _sync_feature_repositories(session, feature, ids, primary_id)
    return feature


def set_feature_repositories(
    session: Session,
    feature: Feature,
    repository_ids: Sequence[int],
    *,
    primary_repository_id: int | None = None,
) -> Feature:
    """Remplace les dépôts couverts par une feature."""
    ids = _validated_ids(session, feature.project, repository_ids, primary_repository_id)
    _sync_feature_repositories(session, feature, ids, primary_repository_id)
    return feature


def create_task(
    session: Session,
    feature: Feature,
    *,
    key: str,
    title: str,
    status: str = "todo",
    primary_repository: Repository | None = None,
    repository_ids: Sequence[int] | None = None,
    owner_person: Person | None = None,
    reviewer_person: Person | None = None,
    executor_label: str | None = None,
    reviewer_label: str | None = None,
    files: Sequence[str] | None = None,
    acceptance: str | None = None,
    description: str | None = None,
    lot: str | None = None,
    note: str | None = None,
    updated_at: datetime | None = None,
) -> Task:
    """Crée une tâche rattachée à une feature et à ses dépôts."""
    normalized_key = key.strip()
    normalized_title = title.strip()
    if not normalized_key or not normalized_title:
        raise FeatureError("clé et titre de tâche requis")
    project = feature.project
    _validate_person(owner_person, project, "exécutant")
    _validate_person(reviewer_person, project, "relecteur")
    primary_id = primary_repository.id if primary_repository is not None else None
    if primary_repository is not None:
        _validate_repository(session, project, primary_repository.id)
    ids = _validated_ids(session, project, repository_ids, primary_id)
    task = Task(
        feature_id=feature.id,
        primary_repository_id=primary_id,
        key=normalized_key,
        title=normalized_title,
        description=description,
        lot=lot,
        status=_status(status, TASK_STATUSES, "tâche"),
        owner_person_id=owner_person.id if owner_person is not None else None,
        reviewer_person_id=reviewer_person.id if reviewer_person is not None else None,
        executor_label=executor_label,
        reviewer_label=reviewer_label,
        files_json=json.dumps(list(files or []), ensure_ascii=False),
        acceptance=acceptance,
        note=note,
        updated_at=updated_at or utc_now(),
    )
    session.add(task)
    session.flush()
    _sync_task_repositories(session, task, ids, primary_id)
    return task


def set_task_repositories(
    session: Session,
    task: Task,
    repository_ids: Sequence[int],
    *,
    primary_repository_id: int | None = None,
) -> Task:
    """Remplace les dépôts touchés par une tâche."""
    ids = _validated_ids(session, task.feature.project, repository_ids, primary_repository_id)
    _sync_task_repositories(session, task, ids, primary_repository_id)
    return task


def list_features(
    session: Session,
    project: Project,
    *,
    statuses: Sequence[str] | None = None,
) -> list[Feature]:
    """Liste les features d'un projet, filtrées par statut au besoin."""
    query = select(Feature).where(Feature.project_id == project.id)
    if statuses:
        query = query.where(Feature.status.in_(list(statuses)))
    return list(session.scalars(query.order_by(Feature.key)).all())


def list_tasks(
    session: Session,
    feature: Feature,
    *,
    statuses: Sequence[str] | None = None,
) -> list[Task]:
    """Liste les tâches d'une feature, filtrées par statut au besoin."""
    query = select(Task).where(Task.feature_id == feature.id)
    if statuses:
        query = query.where(Task.status.in_(list(statuses)))
    return list(session.scalars(query.order_by(Task.key)).all())


def get_feature_by_key(session: Session, project: Project, key: str) -> Feature | None:
    return session.scalar(
        select(Feature).where(Feature.project_id == project.id, Feature.key == key)
    )


def get_task_by_key(session: Session, feature: Feature, key: str) -> Task | None:
    return session.scalar(
        select(Task).where(Task.feature_id == feature.id, Task.key == key)
    )
