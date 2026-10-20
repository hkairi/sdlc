"""Services personnes : identités, rapprochement, fusion et dé-fusion."""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Person, PersonIdentity, PersonMerge, Project, utc_now
from .audit import append_audit

EMAIL_PROVIDER = "email"
ACCOUNT_PROVIDERS = frozenset({"github", "gitlab"})

_BOT_LOCAL_PARTS = frozenset({"bot", "dependabot", "renovate", "github-actions", "gitlab-ci", "jenkins"})
_BOT_SEGMENT = re.compile(r"(^|[._-])(bot|dependabot|renovate|github-actions|gitlab-ci|jenkins)([._-]|$)")


class PersonError(ValueError):
    """Erreur métier sur une personne."""


class IdentityConflictError(PersonError):
    """Identité déjà rattachée à une autre personne du même projet."""


def normalize_email(email: str) -> str:
    """Normalise un email pour la comparaison et le stockage."""
    return email.strip().lower()


def is_bot_identity(email: str | None, name: str | None = None) -> bool:
    """Détecte les identités de robots à partir du nom et de l'email."""
    label = f"{name or ''} {email or ''}".lower()
    if "[bot]" in label:
        return True
    local_part = (email or "").split("@", 1)[0].strip().lower()
    if local_part in _BOT_LOCAL_PARTS:
        return True
    return bool(_BOT_SEGMENT.search(local_part))


def create_person(
    session: Session,
    project: Project,
    *,
    display_name: str,
    role: str | None = None,
    is_bot: bool = False,
) -> Person:
    """Crée une personne canonique sans identité."""
    person = Person(
        project_id=project.id,
        display_name=display_name.strip(),
        role=role,
        is_bot=is_bot,
    )
    session.add(person)
    session.flush()
    return person


def find_person_by_email(session: Session, project: Project, email: str) -> Person | None:
    """Trouve la personne portant un email normalisé dans le projet."""
    normalized = normalize_email(email)
    return session.scalar(
        select(Person)
        .join(PersonIdentity, PersonIdentity.person_id == Person.id)
        .where(
            Person.project_id == project.id,
            PersonIdentity.email == normalized,
        )
    )


def find_person_by_external_id(
    session: Session,
    project: Project,
    provider: str,
    external_id: str,
) -> Person | None:
    """Trouve la personne portant un compte fournisseur dans le projet."""
    return session.scalar(
        select(Person)
        .join(PersonIdentity, PersonIdentity.person_id == Person.id)
        .where(
            Person.project_id == project.id,
            PersonIdentity.provider == provider,
            PersonIdentity.external_id == external_id,
        )
    )


def _find_identity_by_email(session: Session, person: Person, email: str) -> PersonIdentity | None:
    return session.scalar(
        select(PersonIdentity).where(
            PersonIdentity.project_id == person.project_id,
            PersonIdentity.email == email,
        )
    )


def _find_identity_by_external(
    session: Session,
    person: Person,
    provider: str,
    external_id: str,
) -> PersonIdentity | None:
    return session.scalar(
        select(PersonIdentity).where(
            PersonIdentity.project_id == person.project_id,
            PersonIdentity.provider == provider,
            PersonIdentity.external_id == external_id,
        )
    )


def add_identity(
    session: Session,
    person: Person,
    *,
    email: str | None = None,
    provider: str | None = None,
    external_id: str | None = None,
) -> PersonIdentity:
    """Ajoute ou complète une identité pour une personne.

    Un email déjà porté par une identité de la même personne est complété avec
    le compte fournisseur plutôt que dupliqué (contrainte d'unicité par projet).
    """
    normalized = normalize_email(email) if email else None
    if provider is not None and provider not in ACCOUNT_PROVIDERS:
        raise PersonError(f"fournisseur de compte inconnu : {provider}")
    if provider is not None and not external_id:
        raise PersonError("external_id requis avec un fournisseur de compte")
    if not normalized and not (provider and external_id):
        raise PersonError("email ou (provider, external_id) requis")

    if normalized:
        owner = find_person_by_email(session, person.project, normalized)
        if owner is not None and owner.id != person.id:
            raise IdentityConflictError(f"email déjà rattaché à une autre personne : {normalized}")
    if provider and external_id:
        owner = find_person_by_external_id(session, person.project, provider, external_id)
        if owner is not None and owner.id != person.id:
            raise IdentityConflictError(
                f"compte {provider}:{external_id} déjà rattaché à une autre personne"
            )

    same_email = _find_identity_by_email(session, person, normalized) if normalized else None
    same_external = (
        _find_identity_by_external(session, person, provider, external_id)
        if provider and external_id
        else None
    )
    if same_email is not None and same_external is not None and same_email.id != same_external.id:
        return same_email
    if same_email is not None:
        if provider and external_id:
            if same_email.external_id is None:
                same_email.provider = provider
                same_email.external_id = external_id
                session.flush()
                return same_email
            if same_email.provider != provider or same_email.external_id != external_id:
                identity = PersonIdentity(
                    project_id=person.project_id,
                    person_id=person.id,
                    provider=provider,
                    external_id=external_id,
                    email=None,
                )
                session.add(identity)
                session.flush()
                return identity
        return same_email
    if same_external is not None:
        if normalized:
            if same_external.email is None:
                same_external.email = normalized
                session.flush()
                return same_external
            if same_external.email != normalized:
                identity = PersonIdentity(
                    project_id=person.project_id,
                    person_id=person.id,
                    provider=EMAIL_PROVIDER,
                    external_id=None,
                    email=normalized,
                )
                session.add(identity)
                session.flush()
                return identity
        return same_external

    identity = PersonIdentity(
        project_id=person.project_id,
        person_id=person.id,
        provider=provider or EMAIL_PROVIDER,
        external_id=external_id,
        email=normalized,
    )
    session.add(identity)
    session.flush()
    return identity


def resolve_person(
    session: Session,
    project: Project,
    *,
    email: str | None = None,
    provider: str | None = None,
    external_id: str | None = None,
    display_name: str | None = None,
) -> Person:
    """Trouve ou crée la personne correspondant aux identités fournies.

    Un email et un compte fournisseur qui désignent deux personnes différentes
    déclenchent une conflit explicite, à arbitrer manuellement.
    """
    normalized = normalize_email(email) if email else None
    by_email = find_person_by_email(session, project, normalized) if normalized else None
    by_external = (
        find_person_by_external_id(session, project, provider, external_id)
        if provider and external_id
        else None
    )
    if by_email is not None and by_external is not None and by_email.id != by_external.id:
        raise IdentityConflictError(
            f"email {normalized} et compte {provider}:{external_id} désignent deux personnes"
        )

    person = by_email or by_external
    if person is None:
        fallback = f"{provider}:{external_id}" if provider and external_id else "inconnu"
        name = (display_name or normalized or fallback).strip()
        person = create_person(
            session,
            project,
            display_name=name,
            is_bot=is_bot_identity(normalized, name),
        )

    if normalized or (provider and external_id):
        add_identity(
            session,
            person,
            email=normalized,
            provider=provider,
            external_id=external_id,
        )
    return person


def list_persons(
    session: Session,
    project: Project,
    *,
    include_merged: bool = False,
    include_bots: bool = True,
) -> list[Person]:
    """Liste les personnes du projet, hors personnes fusionnées par défaut."""
    query = select(Person).where(Person.project_id == project.id)
    if not include_merged:
        query = query.where(Person.superseded_by_person_id.is_(None))
    if not include_bots:
        query = query.where(Person.is_bot.is_(False))
    return list(session.scalars(query.order_by(Person.display_name, Person.id)).all())


def list_team_persons(session: Session, project: Project) -> list[Person]:
    """Liste les personnes humaines actives, base des métriques d'équipe."""
    return list_persons(session, project, include_bots=False)


def merge_persons(
    session: Session,
    source: Person,
    target: Person,
    *,
    reason: str | None = None,
) -> PersonMerge:
    """Fusionne `source` dans `target`, déplace les identités et journalise."""
    if source.id == target.id:
        raise PersonError("une personne ne peut pas être fusionnée avec elle-même")
    if source.project_id != target.project_id:
        raise PersonError("les personnes doivent appartenir au même projet")
    if source.superseded_by_person_id is not None:
        raise PersonError("cette personne est déjà fusionnée")
    if target.superseded_by_person_id is not None:
        raise PersonError("la cible de fusion est elle-même fusionnée")

    moved_ids: list[int] = []
    for identity in list(source.identities):
        identity.person_id = target.id
        moved_ids.append(identity.id)
    source.superseded_by_person_id = target.id
    merge = PersonMerge(
        project_id=source.project_id,
        source_person_id=source.id,
        target_person_id=target.id,
        reason=reason,
        identity_ids_json=json.dumps(moved_ids),
    )
    session.add(merge)
    session.flush()
    append_audit(
        session,
        project_id=source.project_id,
        action="person.merge",
        object_type="person",
        object_id=source.id,
        payload={
            "merge_id": merge.id,
            "source_person_id": source.id,
            "target_person_id": target.id,
            "identity_ids": moved_ids,
            "reason": reason,
        },
    )
    return merge


def unmerge_person(session: Session, source: Person) -> PersonMerge:
    """Annule la dernière fusion active de `source` et restaure ses identités."""
    merge = session.scalar(
        select(PersonMerge)
        .where(
            PersonMerge.source_person_id == source.id,
            PersonMerge.undone_at.is_(None),
        )
        .order_by(PersonMerge.created_at.desc(), PersonMerge.id.desc())
    )
    if merge is None:
        raise PersonError("aucune fusion active à annuler")
    identity_ids = json.loads(merge.identity_ids_json)
    if identity_ids:
        identities = session.scalars(
            select(PersonIdentity).where(PersonIdentity.id.in_(identity_ids))
        ).all()
        for identity in identities:
            identity.person_id = source.id
    source.superseded_by_person_id = None
    merge.undone_at = utc_now()
    session.flush()
    append_audit(
        session,
        project_id=merge.project_id,
        action="person.unmerge",
        object_type="person",
        object_id=source.id,
        payload={
            "merge_id": merge.id,
            "source_person_id": source.id,
            "target_person_id": merge.target_person_id,
            "identity_ids": identity_ids,
        },
    )
    return merge
