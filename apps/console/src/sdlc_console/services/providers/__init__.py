"""Collecteurs de fournisseurs GitHub et GitLab."""

from .ingest import (
    collect_merge_requests,
    collect_project,
    collect_repository,
    github_from_file,
    gitlab_from_file,
    store_merge_requests,
)
from .models import ApprovalData, MergeRequestData, ReviewData

__all__ = [
    "ApprovalData",
    "MergeRequestData",
    "ReviewData",
    "collect_merge_requests",
    "collect_project",
    "collect_repository",
    "github_from_file",
    "gitlab_from_file",
    "store_merge_requests",
]
