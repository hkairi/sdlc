"""Modèles normalisés indépendants du fournisseur GitHub/GitLab."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ReviewData:
    """Revue normalisée d'une MR."""

    external_id: str
    reviewer_login: str | None
    reviewer_name: str | None
    state: str
    submitted_at: datetime | None
    is_agent: bool = False
    model: str | None = None
    independence: str | None = None


@dataclass(frozen=True)
class ApprovalData:
    """Approbation normalisée d'une MR."""

    external_id: str
    actor_login: str | None
    actor_name: str | None
    approved_at: datetime | None
    actor_type: str = "human"


@dataclass(frozen=True)
class MergeRequestData:
    """Pull request ou merge request normalisée."""

    number: int
    title: str
    author_login: str | None
    author_name: str | None
    state: str
    created_at: datetime | None
    updated_at: datetime | None
    merged_at: datetime | None
    target_branch: str | None
    source_branch: str | None
    merge_strategy: str | None
    additions: int | None
    deletions: int | None
    url: str | None
    author_email: str | None = None
    reviews: tuple[ReviewData, ...] = field(default_factory=tuple)
    approvals: tuple[ApprovalData, ...] = field(default_factory=tuple)
