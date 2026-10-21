"""Chaîne de validation auteur → relecteur agent → humain."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Approval, MergeRequest, Project, Review, utc_now
from .projects import list_repositories


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _rate(count: int, total: int) -> float | None:
    return round(count * 100 / total, 2) if total else None


def build_validation_chain(
    session: Session,
    project: Project,
    *,
    repository_ids: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Calcule la chaîne de validation et les taux par dépôt."""
    repositories = list_repositories(session, project)
    if repository_ids is not None:
        wanted = set(repository_ids)
        available = {repository.id for repository in repositories}
        missing = wanted - available
        if missing:
            raise ValueError(f"dépôts inconnus ou retirés : {sorted(missing)}")
        repositories = [repository for repository in repositories if repository.id in wanted]
    by_id = {repository.id: repository for repository in repositories}
    mrs = list(
        session.scalars(
            select(MergeRequest).where(
                MergeRequest.repository_id.in_(list(by_id))
            )
        ).all()
    ) if by_id else []
    mr_ids = [mr.id for mr in mrs]
    reviews = (
        list(session.scalars(select(Review).where(Review.mr_id.in_(mr_ids))).all())
        if mr_ids
        else []
    )
    approvals = (
        list(session.scalars(select(Approval).where(Approval.mr_id.in_(mr_ids))).all())
        if mr_ids
        else []
    )
    reviews_by_mr: dict[int, list[Review]] = {}
    for review in reviews:
        reviews_by_mr.setdefault(review.mr_id, []).append(review)
    approvals_by_mr: dict[int, list[Approval]] = {}
    for approval in approvals:
        approvals_by_mr.setdefault(approval.mr_id, []).append(approval)

    chains: list[dict[str, Any]] = []
    repo_counts: dict[int, dict[str, Any]] = {
        repository.id: {
            "repository_id": repository.id,
            "repository_name": repository.name,
            "total": 0,
            "agent_reviewed": 0,
            "human_approved": 0,
            "complete": 0,
        }
        for repository in repositories
    }
    for mr in mrs:
        author = mr.author
        if author is not None and author.is_bot:
            continue
        mr_reviews = reviews_by_mr.get(mr.id, [])
        agent_reviews = [
            review
            for review in mr_reviews
            if review.is_agent or review.reviewer_agent_id
        ]
        human_approvals = [
            approval
            for approval in approvals_by_mr.get(mr.id, [])
            if approval.actor_type.lower() == "human"
            and (approval.actor is None or not approval.actor.is_bot)
        ]
        author_name = author.display_name if author is not None else "non mesuré"
        agent_names = [
            (
                review.reviewer.display_name
                if review.reviewer is not None
                else review.reviewer_agent_id or "agent non identifié"
            )
            for review in agent_reviews
        ]
        approval_names = [
            approval.actor.display_name
            if approval.actor is not None
            else "humain non identifié"
            for approval in human_approvals
        ]
        agent_done = bool(agent_reviews)
        human_done = bool(human_approvals)
        complete = agent_done and human_done
        chain = [
            {
                "step": "author",
                "label": "Auteur",
                "status": "done" if author is not None else "pending",
                "actors": [author_name],
            },
            {
                "step": "agent_review",
                "label": "Relecteur agent",
                "status": "done" if agent_done else "pending",
                "actors": agent_names,
            },
            {
                "step": "human_approval",
                "label": "Approbation humaine",
                "status": "done" if human_done else "pending",
                "actors": approval_names,
            },
        ]
        chains.append(
            {
                "mr_id": mr.id,
                "number": mr.number,
                "title": mr.title,
                "state": mr.state,
                "repository_id": mr.repository_id,
                "repository_name": by_id[mr.repository_id].name,
                "author": author_name,
                "agent_reviewers": agent_names,
                "human_approvers": approval_names,
                "agent_review_done": agent_done,
                "human_approval_done": human_done,
                "complete": complete,
                "status": "complete" if complete else "pending",
                "chain": chain,
                "merged_at": _iso(mr.merged_at),
            }
        )
        counts = repo_counts.get(mr.repository_id)
        if counts is not None:
            counts["total"] += 1
            counts["agent_reviewed"] += 1 if agent_done else 0
            counts["human_approved"] += 1 if human_done else 0
            counts["complete"] += 1 if complete else 0

    repository_payload = []
    for counts in sorted(repo_counts.values(), key=lambda item: item["repository_name"]):
        total = counts["total"]
        repository_payload.append(
            {
                **counts,
                "agent_review_rate": _rate(counts["agent_reviewed"], total),
                "human_approval_rate": _rate(counts["human_approved"], total),
                "complete_rate": _rate(counts["complete"], total),
            }
        )
    total = len(chains)
    agent_count = sum(1 for chain in chains if chain["agent_review_done"])
    human_count = sum(1 for chain in chains if chain["human_approval_done"])
    complete_count = sum(1 for chain in chains if chain["complete"])
    return {
        "generated_at": _iso(utc_now()),
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "total": total,
        "agent_reviewed": agent_count,
        "human_approved": human_count,
        "complete": complete_count,
        "agent_review_rate": _rate(agent_count, total),
        "human_approval_rate": _rate(human_count, total),
        "complete_rate": _rate(complete_count, total),
        "status": "measured" if total else "not_measured",
        "repositories": repository_payload,
        "chains": chains,
        "sources": {
            "merge_requests": "github/gitlab",
            "reviews": "github/gitlab",
            "approvals": "github/gitlab",
        },
    }
