"""Agrégation multi-dépôts des commits, sans double comptage.

La déduplication est hiérarchique :

1. empreinte de commit identique, quel que soit le dépôt ;
2. même contenu dans des dépôts déclarés miroirs/forks partageant un
   `dedup_group` (auteur, date, message, statistiques), même si le SHA diffère.

Les doublons non déclarés (cherry-pick, fork non déclaré) ne sont pas retirés
des totaux : ils sont signalés comme « doublons potentiels » pour que le total
ne masque pas le double comptage.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Commit, Project, Repository
from .people import normalize_email
from .projects import list_repositories

DEDUP_BADGE = "dédoublonnage appliqué"
POTENTIAL_BADGE = "dédoublonnage non appliqué"
CHERRY_PICK_PREFIX = "(cherry picked from commit"


@dataclass(frozen=True)
class CommitMetrics:
    """Métriques de commits pour un dépôt ou un agrégat."""

    commits: int
    human_commits: int
    merge_commits: int
    bot_commits: int
    ai_assisted_commits: int
    additions: int
    deletions: int
    files_changed: int
    persons: int


@dataclass(frozen=True)
class RepositoryCommitMetrics:
    """Métriques calculées dans le périmètre d'un dépôt."""

    repository_id: int
    repository_name: str
    is_primary: bool
    is_mirror: bool
    is_fork: bool
    dedup_group: str | None
    metrics: CommitMetrics


@dataclass(frozen=True)
class DeduplicatedCommit:
    """Commit conservé une seule fois dans l'agrégat, avec son origine."""

    fingerprint: str
    origin_commit_id: int
    origin_repository_id: int
    origin_repository_name: str
    duplicate_commit_ids: tuple[int, ...]
    duplicate_repository_ids: tuple[int, ...]
    duplicate_repository_names: tuple[str, ...]
    dedup_group: str | None
    reason: str
    badge: str = DEDUP_BADGE


@dataclass(frozen=True)
class PotentialDuplicate:
    """Même contenu probable dans des dépôts non déclarés comme miroirs/forks."""

    commit_ids: tuple[int, ...]
    repository_ids: tuple[int, ...]
    repository_names: tuple[str, ...]
    reason: str
    badge: str = POTENTIAL_BADGE


@dataclass(frozen=True)
class CommitAggregation:
    """Résultat complet de l'agrégation multi-dépôts."""

    project_id: int
    repository_metrics: tuple[RepositoryCommitMetrics, ...]
    totals: CommitMetrics
    raw_commits: int
    unique_commits: int
    duplicate_commits: int
    deduplicated_commits: tuple[DeduplicatedCommit, ...]
    potential_duplicates: tuple[PotentialDuplicate, ...]
    dedup_applied: bool
    dedup_badge: str | None
    potential_badge: str | None
    unique_commit_ids: tuple[int, ...] = ()


def _metrics(commits: Sequence[Commit]) -> CommitMetrics:
    bot_commits = sum(1 for commit in commits if commit.is_bot)
    return CommitMetrics(
        commits=len(commits),
        human_commits=len(commits) - bot_commits,
        merge_commits=sum(1 for commit in commits if commit.is_merge),
        bot_commits=bot_commits,
        ai_assisted_commits=sum(1 for commit in commits if commit.ai_assisted),
        additions=sum(commit.additions for commit in commits),
        deletions=sum(commit.deletions for commit in commits),
        files_changed=sum(commit.files_changed for commit in commits),
        persons=len({commit.person_id for commit in commits if commit.person_id is not None}),
    )


def _origin_key(commit: Commit, repository: Repository) -> tuple[int, int, int, int, int]:
    return (
        0 if repository.is_primary else 1,
        0 if not repository.is_mirror else 1,
        0 if not repository.is_fork else 1,
        repository.id,
        commit.id,
    )


def _normalized_message(message: str) -> str:
    lines = [
        line
        for line in message.splitlines()
        if not line.strip().lower().startswith(CHERRY_PICK_PREFIX)
    ]
    return "\n".join(lines).strip()


def _content_signature(commit: Commit) -> tuple[str, datetime, str, int, int, int]:
    return (
        normalize_email(commit.author_email or ""),
        commit.authored_at,
        _normalized_message(commit.message),
        commit.additions,
        commit.deletions,
        commit.files_changed,
    )


def _common_group(commits: Sequence[Commit], repositories: dict[int, Repository]) -> str | None:
    groups = {repositories[commit.repository_id].dedup_group for commit in commits}
    if len(groups) == 1:
        return next(iter(groups))
    return None


def _deduplicated_commit(
    origin: Commit,
    duplicates: Sequence[Commit],
    repositories: dict[int, Repository],
    *,
    reason: str,
    dedup_group: str | None,
) -> DeduplicatedCommit:
    origin_repository = repositories[origin.repository_id]
    duplicate_repositories = [repositories[commit.repository_id] for commit in duplicates]
    return DeduplicatedCommit(
        fingerprint=origin.commit_fingerprint,
        origin_commit_id=origin.id,
        origin_repository_id=origin.repository_id,
        origin_repository_name=origin_repository.name,
        duplicate_commit_ids=tuple(commit.id for commit in duplicates),
        duplicate_repository_ids=tuple(repository.id for repository in duplicate_repositories),
        duplicate_repository_names=tuple(repository.name for repository in duplicate_repositories),
        dedup_group=dedup_group,
        reason=reason,
    )


def _empty(project: Project) -> CommitAggregation:
    return CommitAggregation(
        project_id=project.id,
        repository_metrics=(),
        totals=CommitMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0),
        raw_commits=0,
        unique_commits=0,
        duplicate_commits=0,
        deduplicated_commits=(),
        potential_duplicates=(),
        dedup_applied=False,
        dedup_badge=None,
        potential_badge=None,
    )


def aggregate_commits(
    session: Session,
    project: Project,
    *,
    repository_ids: Sequence[int] | None = None,
) -> CommitAggregation:
    """Calcule les métriques par dépôt puis l'agrégat dédupliqué.

    `repository_ids` restreint le calcul à un ou plusieurs dépôts actifs. Sans
    filtre, tous les dépôts actifs du projet sont agrégés.
    """
    repositories = list_repositories(session, project)
    by_id = {repository.id: repository for repository in repositories}
    if repository_ids is not None:
        requested = set(repository_ids)
        missing = requested - set(by_id)
        if missing:
            raise ValueError(f"dépôts inconnus ou retirés : {sorted(missing)}")
        repositories = [by_id[repository_id] for repository_id in repository_ids]
    if not repositories:
        return _empty(project)

    commits = list(
        session.scalars(
            select(Commit).where(Commit.repository_id.in_([repository.id for repository in repositories]))
        ).all()
    )
    if not commits:
        return _empty(project)

    commits_by_repository: dict[int, list[Commit]] = defaultdict(list)
    for commit in commits:
        commits_by_repository[commit.repository_id].append(commit)
    repository_metrics = tuple(
        RepositoryCommitMetrics(
            repository_id=repository.id,
            repository_name=repository.name,
            is_primary=repository.is_primary,
            is_mirror=repository.is_mirror,
            is_fork=repository.is_fork,
            dedup_group=repository.dedup_group,
            metrics=_metrics(commits_by_repository[repository.id]),
        )
        for repository in repositories
    )

    fingerprint_groups: dict[str, list[Commit]] = defaultdict(list)
    for commit in commits:
        fingerprint_groups[commit.commit_fingerprint].append(commit)

    winners: list[Commit] = []
    deduplicated: list[DeduplicatedCommit] = []
    for group in fingerprint_groups.values():
        origin = min(group, key=lambda commit: _origin_key(commit, by_id[commit.repository_id]))
        duplicates = [commit for commit in group if commit.id != origin.id]
        if duplicates:
            deduplicated.append(
                _deduplicated_commit(
                    origin,
                    duplicates,
                    by_id,
                    reason="empreinte",
                    dedup_group=_common_group(group, by_id),
                )
            )
        winners.append(origin)

    grouped_winners: dict[tuple[str, tuple[str, datetime, str, int, int, int]], list[Commit]] = defaultdict(list)
    ungrouped: list[Commit] = []
    for commit in winners:
        dedup_group = by_id[commit.repository_id].dedup_group
        if dedup_group:
            grouped_winners[(dedup_group, _content_signature(commit))].append(commit)
        else:
            ungrouped.append(commit)

    final_winners = list(ungrouped)
    for (dedup_group, _signature), group in grouped_winners.items():
        if len({commit.repository_id for commit in group}) <= 1:
            final_winners.extend(group)
            continue
        origin = min(group, key=lambda commit: _origin_key(commit, by_id[commit.repository_id]))
        duplicates = [commit for commit in group if commit.id != origin.id]
        if duplicates:
            deduplicated.append(
                _deduplicated_commit(
                    origin,
                    duplicates,
                    by_id,
                    reason="dedup_group",
                    dedup_group=dedup_group,
                )
            )
        final_winners.append(origin)

    signature_groups: dict[tuple[str, datetime, str, int, int, int], list[Commit]] = defaultdict(list)
    for commit in final_winners:
        signature_groups[_content_signature(commit)].append(commit)
    potential: list[PotentialDuplicate] = []
    for group in signature_groups.values():
        repository_set = {commit.repository_id for commit in group}
        if len(repository_set) <= 1:
            continue
        repositories_in_group = [by_id[repository_id] for repository_id in sorted(repository_set)]
        potential.append(
            PotentialDuplicate(
                commit_ids=tuple(commit.id for commit in group),
                repository_ids=tuple(repository.id for repository in repositories_in_group),
                repository_names=tuple(repository.name for repository in repositories_in_group),
                reason=(
                    "même contenu (auteur, date, message, statistiques) mais empreintes "
                    "différentes : cherry-pick ou fork non déclaré"
                ),
            )
        )

    raw_commits = len(commits)
    unique_commits = len(final_winners)
    duplicate_commits = raw_commits - unique_commits
    return CommitAggregation(
        project_id=project.id,
        repository_metrics=repository_metrics,
        totals=_metrics(final_winners),
        raw_commits=raw_commits,
        unique_commits=unique_commits,
        duplicate_commits=duplicate_commits,
        deduplicated_commits=tuple(deduplicated),
        potential_duplicates=tuple(potential),
        dedup_applied=bool(deduplicated),
        dedup_badge=DEDUP_BADGE if deduplicated else None,
        potential_badge=POTENTIAL_BADGE if potential else None,
        unique_commit_ids=tuple(commit.id for commit in final_winners),
    )
