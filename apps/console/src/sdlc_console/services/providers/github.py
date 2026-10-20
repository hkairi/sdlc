"""Collecteur GitHub : PR, revues, approbations, pagination et ETag."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib.parse import quote, urlencode

from .common import as_int, as_mapping, parse_datetime
from .http import HttpClient, JsonETagCache, cached_json_get, default_cache_path, header_value
from .models import ApprovalData, MergeRequestData, ReviewData

GITHUB_API_URL = "https://api.github.com"


def _github_state(raw: Mapping[str, Any]) -> str:
    if bool(raw.get("merged")) or raw.get("merged_at"):
        return "merged"
    if str(raw.get("state", "")).lower() == "open":
        return "draft" if bool(raw.get("draft")) else "open"
    return "closed"


def _review_state(raw: Mapping[str, Any]) -> str:
    state = str(raw.get("state", "COMMENTED")).lower()
    return {
        "approved": "approved",
        "changes_requested": "changes_requested",
        "commented": "commented",
        "dismissed": "dismissed",
        "pending": "pending",
    }.get(state, state)


def normalize_github_pull_request(
    raw: Mapping[str, Any],
    reviews: Sequence[Mapping[str, Any]],
) -> MergeRequestData | None:
    """Normalise une PR GitHub et ses revues."""
    number = as_int(raw.get("number"))
    if number is None:
        return None
    user = as_mapping(raw.get("user"))
    base = as_mapping(raw.get("base"))
    head = as_mapping(raw.get("head"))
    login = str(user.get("login")) if user.get("login") else None
    email = str(user.get("email")) if user.get("email") else None

    normalized_reviews: list[ReviewData] = []
    approvals: list[ApprovalData] = []
    for review in reviews:
        review_user = as_mapping(review.get("user"))
        reviewer_login = str(review_user.get("login")) if review_user.get("login") else None
        submitted_at = parse_datetime(review.get("submitted_at"))
        state = _review_state(review)
        review_id = review.get("id")
        if review_id is not None:
            external_id = f"review:{review_id}"
        else:
            external_id = f"review:{reviewer_login}:{state}:{submitted_at.isoformat() if submitted_at else ''}"
        normalized_reviews.append(
            ReviewData(
                external_id=external_id,
                reviewer_login=reviewer_login,
                reviewer_name=str(review_user.get("name")) if review_user.get("name") else reviewer_login,
                state=state,
                submitted_at=submitted_at,
            )
        )
        if state == "approved":
            approvals.append(
                ApprovalData(
                    external_id=f"approval:{review_id}" if review_id is not None else external_id,
                    actor_login=reviewer_login,
                    actor_name=str(review_user.get("name")) if review_user.get("name") else reviewer_login,
                    approved_at=submitted_at,
                    actor_type="bot" if str(review_user.get("type", "")).lower() == "bot" else "human",
                )
            )

    return MergeRequestData(
        number=number,
        title=str(raw.get("title") or ""),
        author_login=login,
        author_name=login,
        author_email=email,
        state=_github_state(raw),
        created_at=parse_datetime(raw.get("created_at")),
        updated_at=parse_datetime(raw.get("updated_at")),
        merged_at=parse_datetime(raw.get("merged_at")),
        target_branch=str(base.get("ref")) if base.get("ref") else None,
        source_branch=str(head.get("ref")) if head.get("ref") else None,
        merge_strategy=None,
        additions=as_int(raw.get("additions")),
        deletions=as_int(raw.get("deletions")),
        url=str(raw.get("html_url")) if raw.get("html_url") else None,
        reviews=tuple(normalized_reviews),
        approvals=tuple(approvals),
    )


class GitHubCollector:
    """Collecte les PR d'un dépôt GitHub via l'API REST."""

    def __init__(
        self,
        client: HttpClient,
        *,
        token: str | None = None,
        api_base: str = GITHUB_API_URL,
        cache: JsonETagCache | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
        attempts: int = 3,
    ) -> None:
        self.client = client
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.cache = cache or JsonETagCache(default_cache_path())
        self.sleep = sleep
        self.now = now
        self.attempts = attempts

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get(self, url: str) -> Any | None:
        return cached_json_get(
            self.client,
            url,
            self._headers(),
            self.cache,
            attempts=self.attempts,
            sleep=self.sleep,
            now=self.now,
        )

    def _paginate(self, url: str, params: Mapping[str, str]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while page <= 100:
            query = urlencode({**params, "per_page": "100", "page": str(page)})
            payload = self._get(f"{url}?{query}")
            if not isinstance(payload, list):
                break
            page_items = [item for item in payload if isinstance(item, dict)]
            items.extend(page_items)
            if len(payload) < 100:
                break
            page += 1
        return items

    def collect(self, owner: str, repository: str) -> list[MergeRequestData]:
        """Collecte les PR et leurs revues pour un dépôt."""
        safe_owner = quote(owner, safe="")
        safe_repository = quote(repository, safe="")
        pulls_url = f"{self.api_base}/repos/{safe_owner}/{safe_repository}/pulls"
        pulls = self._paginate(
            pulls_url,
            {"state": "all", "sort": "updated", "direction": "desc"},
        )
        result: list[MergeRequestData] = []
        for pull in pulls:
            number = as_int(pull.get("number"))
            if number is None:
                continue
            detail = pull
            if "additions" not in detail or "deletions" not in detail:
                fetched = self._get(f"{pulls_url}/{number}")
                if isinstance(fetched, dict):
                    detail = {**pull, **fetched}
            reviews = self._paginate(f"{pulls_url}/{number}/reviews", {})
            normalized = normalize_github_pull_request(detail, reviews)
            if normalized is not None:
                result.append(normalized)
        return result


def next_link(headers: Mapping[str, str]) -> str | None:
    """Lit le prochain lien de pagination GitHub, si présent."""
    link = header_value(headers, "link")
    if not link:
        return None
    for part in link.split(","):
        if 'rel="next"' in part:
            start = part.find("<")
            end = part.find(">")
            if start >= 0 and end > start:
                return part[start + 1 : end]
    return None
