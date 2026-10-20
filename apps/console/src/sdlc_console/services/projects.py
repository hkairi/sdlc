"""Services projet et dépôts : création, dépôt principal, retrait."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Project, Repository, utc_now
from .audit import append_audit

PROVIDERS = frozenset({"github", "gitlab"})


class ProjectError(ValueError):
    """Erreur métier sur un projet."""


class RepositoryError(ValueError):
    """Erreur métier sur un dépôt."""


def create_project(
    session: Session,
    *,
    name: str,
    slug: str,
    timezone: str = "Europe/Paris",
) -> Project:
    """Crée un projet et le flushe pour obtenir son identifiant."""
    project = Project(name=name, slug=slug, timezone=timezone)
    session.add(project)
    session.flush()
    return project


def validate_git_repository(path: str | Path) -> Path:
    """Vérifie que le chemin est un dossier Git et renvoie le chemin absolu."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise RepositoryError(f"dépôt introuvable ou non dossier : {resolved}")
    if not (resolved / ".git").exists():
        raise RepositoryError(f"dépôt Git invalide (pas de .git) : {resolved}")
    return resolved


def list_repositories(session: Session, project: Project, *, include_retired: bool = False) -> list[Repository]:
    """Liste les dépôts d'un projet, actifs par défaut."""
    query = select(Repository).where(Repository.project_id == project.id)
    if not include_retired:
        query = query.where(Repository.retired_at.is_(None))
    return list(session.scalars(query.order_by(Repository.name)).all())


def get_primary_repository(session: Session, project: Project) -> Repository | None:
    """Renvoie le dépôt principal actif, s'il existe."""
    return session.scalar(
        select(Repository).where(
            Repository.project_id == project.id,
            Repository.is_primary.is_(True),
            Repository.retired_at.is_(None),
        )
    )


def _promote(session: Session, repository: Repository) -> None:
    """Désigne un dépôt comme principal en désactivant les autres."""
    session.execute(
        update(Repository)
        .where(Repository.project_id == repository.project_id)
        .values(is_primary=False)
        .execution_options(synchronize_session=False)
    )
    session.expire_all()
    repository.is_primary = True
    session.flush()


def add_repository(
    session: Session,
    project: Project,
    *,
    name: str,
    provider: str,
    url: str,
    local_path: str | Path,
    default_branch: str = "main",
    is_primary: bool = False,
    dedup_group: str | None = None,
    is_mirror: bool = False,
    is_fork: bool = False,
) -> Repository:
    """Ajoute un dépôt. Le premier dépôt devient principal automatiquement."""
    if provider not in PROVIDERS:
        raise RepositoryError(f"fournisseur inconnu : {provider}")
    resolved = validate_git_repository(local_path)
    existing = list_repositories(session, project, include_retired=True)
    if not existing:
        is_primary = True
    if is_primary:
        session.execute(
            update(Repository)
            .where(Repository.project_id == project.id)
            .values(is_primary=False)
            .execution_options(synchronize_session=False)
        )
        session.expire_all()
    repository = Repository(
        project_id=project.id,
        name=name,
        provider=provider,
        url=url,
        local_path=str(resolved),
        default_branch=default_branch,
        is_primary=is_primary,
        dedup_group=dedup_group,
        is_mirror=is_mirror,
        is_fork=is_fork,
    )
    session.add(repository)
    session.flush()
    return repository


def set_primary_repository(session: Session, repository: Repository) -> Repository:
    """Désigne un dépôt actif comme principal."""
    if repository.retired_at is not None:
        raise RepositoryError("un dépôt retiré ne peut pas être principal")
    _promote(session, repository)
    return repository


def retire_repository(
    session: Session,
    repository: Repository,
    *,
    actor_label: str = "système",
    reason: str | None = None,
) -> Repository:
    """Archive un dépôt, réélit un principal si nécessaire et l'audite.

    Le dernier dépôt actif ne peut pas être retiré : un projet conserve toujours
    un dépôt principal.
    """
    if repository.retired_at is not None:
        return repository
    project_id = repository.project_id
    repository_id = repository.id
    repository_name = repository.name
    was_primary = repository.is_primary
    active = [
        item
        for item in list_repositories(session, repository.project)
        if item.id != repository_id
    ]
    new_primary_id: int | None = None
    if was_primary:
        if not active:
            raise RepositoryError("impossible de retirer le dernier dépôt du projet")
        _promote(session, active[0])
        new_primary_id = active[0].id
    repository.is_primary = False
    repository.retired_at = utc_now()
    session.flush()
    append_audit(
        session,
        project_id=project_id,
        action="repository.retire",
        object_type="repository",
        object_id=repository_id,
        actor_label=actor_label,
        payload={
            "repository_id": repository_id,
            "name": repository_name,
            "was_primary": was_primary,
            "new_primary_repository_id": new_primary_id,
            "reason": reason,
        },
    )
    return repository


def delete_repository(
    session: Session,
    repository: Repository,
    *,
    confirm: bool = False,
    actor_label: str = "système",
    reason: str | None = None,
) -> None:
    """Supprime définitivement un dépôt, après confirmation explicite.

    La suppression est cascadée et auditée. Un dépôt principal est remplacé
    automatiquement ; le dernier dépôt actif ne peut pas être supprimé.
    """
    if not confirm:
        raise RepositoryError("suppression définitive non confirmée")
    project_id = repository.project_id
    repository_id = repository.id
    repository_name = repository.name
    was_primary = repository.is_primary
    active = [
        item
        for item in list_repositories(session, repository.project)
        if item.id != repository_id
    ]
    new_primary_id: int | None = None
    if was_primary:
        if not active:
            raise RepositoryError("impossible de supprimer le dernier dépôt du projet")
        _promote(session, active[0])
        new_primary_id = active[0].id
    session.delete(repository)
    session.flush()
    append_audit(
        session,
        project_id=project_id,
        action="repository.delete",
        object_type="repository",
        object_id=repository_id,
        actor_label=actor_label,
        payload={
            "repository_id": repository_id,
            "name": repository_name,
            "was_primary": was_primary,
            "new_primary_repository_id": new_primary_id,
            "reason": reason,
        },
    )
