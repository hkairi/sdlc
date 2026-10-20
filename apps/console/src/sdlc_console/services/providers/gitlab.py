"""Collecteur GitLab : MR, approbations, pagination et ETag."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import quote, urlencode

from .common import as_int, as_mapping, parse_datetime
from .http import HttpClient, JsonETagCache, cached_json_get, default_cache_path
from .models import ApprovalData, MergeRequestData, ReviewData

GITLAB_API_URL = "https://gitlab.com/api/v4"


def _gitlab_state(raw: Mapping[str, Any]) -> str:
    state = str(raw.get("state", "")).lower()
    if state == "merged" or raw.get("merged_at"):
        return "merged"
    if state == "opened":
        return "draft" if bool(raw.get("draft") or raw.get("work_in_progress")) else "open"
    return "closed"


def _approval_entries(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, Mapping)]
    if isinstance(payload, Mapping):
        approved_by = payload.get("approved_by")
        if isinstance(approved_by, list):
            return [entry for entry in approved_by if isinstance(entry, Mapping)]
    return []


def normalize_gitlab_merge_request(
    raw: Mapping[str, Any],
    approvals_payload: Any,
) -> MergeRequestData | None:
    """Normalise une MR GitLab et ses approbations."""
    number = as_int(raw.get("iid"))
    if number is None:
        return None
    author = as_mapping(raw.get("author"))
    login = str(author.get("username")) if author.get("username") else None
    name = str(author.get("name")) if author.get("name") else login
    email = str(author.get("email")) if author.get("email") else None

    reviews: list[ReviewData] = []
    approvals: list[ApprovalData] = []
    for entry in _approval_entries(approvals_payload):
        nested_user = entry.get("user")
        user: Mapping[str, Any] = nested_user if isinstance(nested_user, Mapping) else entry
        user_login = str(user.get("username")) if user.get("username") else None
        user_name = str(user.get("name")) if user.get("name") else user_login
        user_id = user.get("id")
        approved_at = parse_datetime(entry.get("approved_at") or entry.get("created_at"))
        external_id = (
            f"approval:{user_id}" if user_id is not None else f"approval:{user_login}"
        )
        is_bot = bool(user.get("bot")) or str(user.get("user_type", "")).lower() == "bot"
        reviews.append(
            ReviewData(
                external_id=f"review:{external_id}",
                reviewer_login=user_login,
                reviewer_name=user_name,
                state="approved",
                submitted_at=approved_at,
            )
        )
        approvals.append(
            ApprovalData(
                external_id=external_id,
                actor_login=user_login,
                actor_name=user_name,
                approved_at=approved_at,
                actor_type="bot" if is_bot else "human",
            )
        )

    return MergeRequestData(
        number=number,
        title=str(raw.get("title") or ""),
        author_login=login,
        author_name=name,
        author_email=email,
        state=_gitlab_state(raw),
        created_at=parse_datetime(raw.get("created_at")),
        updated_at=parse_datetime(raw.get("updated_at")),
        merged_at=parse_datetime(raw.get("merged_at")),
        target_branch=str(raw.get("target_branch")) if raw.get("target_branch") else None,
        source_branch=str(raw.get("source_branch")) if raw.get("source_branch") else None,
        merge_strategy="squash" if bool(raw.get("squash")) else None,
        additions=None,
        deletions=None,
        url=str(raw.get("web_url")) if raw.get("web_url") else None,
        reviews=tuple(reviews),
        approvals=tuple(approvals),
    )


class GitLabCollector:
    """Collecte les MR d'un projet GitLab via l'API REST v4."""

    def __init__(
        self,
        client: HttpClient,
        *,
        token: str | None = None,
        api_base: str = GITLAB_API_URL,
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
        headers = {"Accept": "application/json"}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token
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

    def collect(self, project_path: str) -> list[MergeRequestData]:
        """Collecte les MR et approbations d'un projet GitLab."""
        encoded = quote(project_path.strip("/"), safe="")
        base = f"{self.api_base}/projects/{encoded}/merge_requests"
        merge_requests = self._paginate(
            base,
            {"state": "all", "order_by": "updated_at", "sort": "desc"},
        )
        result: list[MergeRequestData] = []
        for merge_request in merge_requests:
            number = as_int(merge_request.get("iid"))
            if number is None:
                continue
            approvals = self._get(f"{base}/{number}/approvals")
            normalized = normalize_gitlab_merge_request(merge_request, approvals)
            if normalized is not None:
                result.append(normalized)
        return result
