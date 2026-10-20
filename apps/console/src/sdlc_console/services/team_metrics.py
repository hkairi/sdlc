"""Métriques d'équipe par personne canonique et par dépôt."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Approval,
    Commit,
    MergeRequest,
    Person,
    Project,
    Review,
    utc_now,
)
from .aggregation import aggregate_commits
from .projects import list_repositories


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _latest(current: datetime | None, candidate: datetime | None) -> datetime | None:
    candidate = _aware(candidate)
    if candidate is None:
        return current
    return candidate if current is None or candidate > current else current


def _person_payload(person: Person) -> dict[str, Any]:
    return {
        "id": person.id,
        "display_name": person.display_name,
        "role": person.role,
        "is_bot": person.is_bot,
    }


def build_team_metrics(
    session: Session,
    project: Project,
    *,
    repository_ids: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Calcule les métriques par personne et dépôt, avec total dédupliqué."""
    repositories = list_repositories(session, project)
    if repository_ids is not None:
        wanted = set(repository_ids)
        available = {repository.id for repository in repositories}
        missing = wanted - available
        if missing:
            raise ValueError(f"dépôts inconnus ou retirés : {sorted(missing)}")
        repositories = [repository for repository in repositories if repository.id in wanted]
    repository_by_id = {repository.id: repository for repository in repositories}
    repo_ids = list(repository_by_id)
    if not repo_ids:
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "repositories": [],
            "persons": [],
            "totals": {
                "commits": 0,
                "merged_requests": 0,
                "reviews": 0,
                "approvals": 0,
                "additions": 0,
                "deletions": 0,
                "persons": 0,
                "ai_percent": None,
            },
            "sources": {"commits": "git", "merge_requests": "github/gitlab"},
        }

    commits = list(
        session.scalars(
            select(Commit).where(Commit.repository_id.in_(repo_ids))
        ).all()
    )
    mrs = list(
        session.scalars(
            select(MergeRequest).where(MergeRequest.repository_id.in_(repo_ids))
        ).all()
    )
    mr_ids = [mr.id for mr in mrs]
    reviews = (
        list(
            session.scalars(
                select(Review).where(Review.mr_id.in_(mr_ids))
            ).all()
        )
        if mr_ids
        else []
    )
    approvals = (
        list(
            session.scalars(
                select(Approval).where(Approval.mr_id.in_(mr_ids))
            ).all()
        )
        if mr_ids
        else []
    )
    mr_by_id = {mr.id: mr for mr in mrs}
    aggregation = aggregate_commits(session, project, repository_ids=repo_ids)
    unique_commits = {
        commit.id: commit
        for commit in session.scalars(
            select(Commit).where(Commit.id.in_(aggregation.unique_commit_ids))
        ).all()
    } if aggregation.unique_commit_ids else {}

    person_stats: dict[int, dict[str, Any]] = {}
    repo_person: dict[tuple[int, int], dict[str, Any]] = {}
    repo_totals: dict[int, dict[str, Any]] = {}
    for repository in repositories:
        repo_totals[repository.id] = {
            "repository_id": repository.id,
            "repository_name": repository.name,
            "commits": 0,
            "merged_requests": 0,
            "reviews": 0,
            "approvals": 0,
            "additions": 0,
            "deletions": 0,
            "persons": set(),
        }

    def stats_for(person: Person) -> dict[str, Any]:
        if person.id not in person_stats:
            person_stats[person.id] = {
                "person": _person_payload(person),
                "commits": 0,
                "merged_requests": 0,
                "reviews": 0,
                "approvals": 0,
                "additions": 0,
                "deletions": 0,
                "last_activity": None,
                "ai_assisted_commits": 0,
                "trailer_data": False,
                "repositories": {},
            }
        return person_stats[person.id]

    def repo_stats(person: Person, repository_id: int) -> dict[str, Any] | None:
        if repository_id not in repository_by_id:
            return None
        key = (repository_id, person.id)
        if key not in repo_person:
            repo_person[key] = {
                "repository_id": repository_id,
                "repository_name": repository_by_id[repository_id].name,
                "commits": 0,
                "merged_requests": 0,
                "reviews": 0,
                "approvals": 0,
                "additions": 0,
                "deletions": 0,
                "last_activity": None,
            }
        return repo_person[key]

    for commit in commits:
        person = commit.person
        if person is None or person.is_bot or commit.is_bot:
            continue
        stats = stats_for(person)
        per_repo = repo_stats(person, commit.repository_id)
        stats["last_activity"] = _latest(stats["last_activity"], commit.committed_at)
        totals = repo_totals[commit.repository_id]
        totals["commits"] += 1
        totals["additions"] += commit.additions
        totals["deletions"] += commit.deletions
        totals["persons"].add(person.id)
        if per_repo is not None:
            per_repo["commits"] += 1
            per_repo["additions"] += commit.additions
            per_repo["deletions"] += commit.deletions
            per_repo["last_activity"] = _latest(per_repo["last_activity"], commit.committed_at)

    for commit in unique_commits.values():
        if commit.is_bot or commit.person is None or commit.person.is_bot:
            continue
        stats = stats_for(commit.person)
        stats["commits"] += 1
        stats["additions"] += commit.additions
        stats["deletions"] += commit.deletions
        stats["ai_assisted_commits"] += 1 if commit.ai_assisted else 0
        stats["trailer_data"] = stats["trailer_data"] or commit.ai_assisted

    for mr in mrs:
        person = mr.author
        if person is None or person.is_bot:
            continue
        stats = stats_for(person)
        per_repo = repo_stats(person, mr.repository_id)
        stats["merged_requests"] += 1
        activity = mr.merged_at or mr.updated_at or mr.created_at
        stats["last_activity"] = _latest(stats["last_activity"], activity)
        totals = repo_totals[mr.repository_id]
        totals["merged_requests"] += 1
        totals["persons"].add(person.id)
        if per_repo is not None:
            per_repo["merged_requests"] += 1
            per_repo["last_activity"] = _latest(per_repo["last_activity"], activity)

    for review in reviews:
        person = review.reviewer
        review_mr = mr_by_id.get(review.mr_id)
        if person is None or person.is_bot or review_mr is None:
            continue
        stats = stats_for(person)
        per_repo = repo_stats(person, review_mr.repository_id)
        stats["reviews"] += 1
        stats["last_activity"] = _latest(stats["last_activity"], review.submitted_at)
        totals = repo_totals[review_mr.repository_id]
        totals["reviews"] += 1
        totals["persons"].add(person.id)
        if per_repo is not None:
            per_repo["reviews"] += 1
            per_repo["last_activity"] = _latest(per_repo["last_activity"], review.submitted_at)

    for approval in approvals:
        person = approval.actor
        approval_mr = mr_by_id.get(approval.mr_id)
        if person is None or person.is_bot or approval_mr is None:
            continue
        stats = stats_for(person)
        per_repo = repo_stats(person, approval_mr.repository_id)
        stats["approvals"] += 1
        stats["last_activity"] = _latest(stats["last_activity"], approval.approved_at)
        totals = repo_totals[approval_mr.repository_id]
        totals["approvals"] += 1
        totals["persons"].add(person.id)
        if per_repo is not None:
            per_repo["approvals"] += 1
            per_repo["last_activity"] = _latest(per_repo["last_activity"], approval.approved_at)

    persons_payload: list[dict[str, Any]] = []
    for stats in person_stats.values():
        repositories_payload = []
        for (_repository_id, person_id), values in sorted(repo_person.items()):
            if person_id != stats["person"]["id"]:
                continue
            repositories_payload.append(
                {
                    **values,
                    "last_activity": _iso(values["last_activity"]),
                }
            )
        ai_percent: float | None = None
        if stats["trailer_data"] and stats["commits"]:
            ai_percent = round(
                stats["ai_assisted_commits"] * 100 / stats["commits"],
                2,
            )
        persons_payload.append(
            {
                "person": stats["person"],
                "commits": stats["commits"],
                "merged_requests": stats["merged_requests"],
                "reviews": stats["reviews"],
                "approvals": stats["approvals"],
                "additions": stats["additions"],
                "deletions": stats["deletions"],
                "last_activity": _iso(stats["last_activity"]),
                "ai": {
                    "assisted_commits": stats["ai_assisted_commits"],
                    "percent": ai_percent,
                    "status": "measured" if ai_percent is not None else "not_measured",
                    "source": "trailers",
                },
                "repositories": repositories_payload,
            }
        )
    persons_payload.sort(key=lambda item: item["person"]["display_name"].casefold())

    repositories_payload = [
        {
            "repository_id": values["repository_id"],
            "repository_name": values["repository_name"],
            "commits": values["commits"],
            "merged_requests": values["merged_requests"],
            "reviews": values["reviews"],
            "approvals": values["approvals"],
            "additions": values["additions"],
            "deletions": values["deletions"],
            "persons": len(values["persons"]),
        }
        for values in sorted(repo_totals.values(), key=lambda item: item["repository_name"])
    ]
    human_unique = [
        commit
        for commit in unique_commits.values()
        if not commit.is_bot
        and commit.person is not None
        and not commit.person.is_bot
    ]
    total_commits = len(human_unique)
    total_ai = sum(1 for commit in human_unique if commit.ai_assisted)
    total_trailer_data = any(commit.ai_assisted for commit in human_unique)
    ai_percent = (
        round(total_ai * 100 / total_commits, 2)
        if total_commits and total_trailer_data
        else None
    )
    return {
        "generated_at": _iso(utc_now()),
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "filters": {"repository_ids": repo_ids},
        "repositories": repositories_payload,
        "persons": persons_payload,
        "totals": {
            "commits": total_commits,
            "merged_requests": sum(item["merged_requests"] for item in repositories_payload),
            "reviews": sum(item["reviews"] for item in repositories_payload),
            "approvals": sum(item["approvals"] for item in repositories_payload),
            "additions": sum(commit.additions for commit in human_unique),
            "deletions": sum(commit.deletions for commit in human_unique),
            "persons": len(persons_payload),
            "ai_percent": ai_percent,
            "ai_status": "measured" if ai_percent is not None else "not_measured",
        },
        "sources": {
            "commits": "git",
            "merge_requests": "github/gitlab",
            "reviews": "github/gitlab",
            "approvals": "github/gitlab",
            "ai": "trailers",
        },
    }
