"""Collecte et persistance normalisée des PR/MR GitHub et GitLab."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Approval, IngestionRun, MergeRequest, Project, Repository, Review, utc_now
from ...paths import is_secret_path
from ...redaction import redact
from ..people import resolve_person
from ..projects import list_repositories
from .common import as_int, repository_owner_and_name, repository_path_from_url
from .github import GITHUB_API_URL, GitHubCollector, normalize_github_pull_request
from .gitlab import GITLAB_API_URL, GitLabCollector, normalize_gitlab_merge_request
from .http import HttpClient, JsonETagCache, ProviderError, UrllibHttpClient, default_cache_path
from .models import ApprovalData, MergeRequestData, ReviewData


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise ProviderError(f"fichier fournisseur introuvable : {path}")
    if is_secret_path(path):
        raise ProviderError(f"lecture de secret refusée : {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderError(f"fichier fournisseur invalide : {path} : {exc}") from exc


def github_from_file(path: Path) -> list[MergeRequestData]:
    """Charge des PR GitHub brutes depuis un fichier de fixture."""
    data = _load_json(path)
    reviews_map: Mapping[Any, Any] = {}
    if isinstance(data, list):
        pulls: Any = data
    elif isinstance(data, dict):
        pulls = data.get("pull_requests") or data.get("pulls") or []
        maybe_reviews = data.get("reviews")
        if isinstance(maybe_reviews, dict):
            reviews_map = maybe_reviews
    else:
        raise ProviderError("format de fichier GitHub invalide")
    if not isinstance(pulls, list):
        raise ProviderError("liste de pull requests absente")
    result: list[MergeRequestData] = []
    for pull in pulls:
        if not isinstance(pull, dict):
            continue
        number = as_int(pull.get("number"))
        if number is None:
            continue
        raw_reviews: list[Any]
        if isinstance(pull.get("reviews"), list):
            raw_reviews = list(pull["reviews"])
        else:
            mapped = reviews_map.get(str(number)) or reviews_map.get(number) or []
            raw_reviews = list(mapped) if isinstance(mapped, list) else []
        explicit = pull.get("approvals")
        if isinstance(explicit, list):
            for approval in explicit:
                if isinstance(approval, dict):
                    raw_reviews.append(
                        {
                            **approval,
                            "state": "APPROVED",
                            "submitted_at": approval.get("submitted_at")
                            or approval.get("approved_at"),
                        }
                    )
        reviews = [review for review in raw_reviews if isinstance(review, dict)]
        normalized = normalize_github_pull_request(pull, reviews)
        if normalized is not None:
            result.append(normalized)
    return result


def gitlab_from_file(path: Path) -> list[MergeRequestData]:
    """Charge des MR GitLab brutes depuis un fichier de fixture."""
    data = _load_json(path)
    approvals_map: Mapping[Any, Any] = {}
    if isinstance(data, list):
        merge_requests: Any = data
    elif isinstance(data, dict):
        merge_requests = data.get("merge_requests") or data.get("mrs") or []
        maybe_approvals = data.get("approvals")
        if isinstance(maybe_approvals, dict):
            approvals_map = maybe_approvals
    else:
        raise ProviderError("format de fichier GitLab invalide")
    if not isinstance(merge_requests, list):
        raise ProviderError("liste de merge requests absente")
    result: list[MergeRequestData] = []
    for merge_request in merge_requests:
        if not isinstance(merge_request, dict):
            continue
        number = as_int(merge_request.get("iid"))
        if number is None:
            continue
        approvals = merge_request.get("approvals")
        if approvals is None:
            approvals = approvals_map.get(str(number)) or approvals_map.get(number)
        normalized = normalize_gitlab_merge_request(merge_request, approvals)
        if normalized is not None:
            result.append(normalized)
    return result


def _gitlab_api_base(repository_url: str) -> str:
    host = urlparse(repository_url).hostname
    if host and host != "gitlab.com":
        return f"https://{host}/api/v4"
    return GITLAB_API_URL


def collect_merge_requests(
    repository: Repository,
    *,
    mode: str = "http",
    file_path: str | Path | None = None,
    client: HttpClient | None = None,
    token: str | None = None,
    cache: JsonETagCache | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> list[MergeRequestData]:
    """Collecte les PR/MR selon le fournisseur et le mode demandé."""
    if repository.provider not in {"github", "gitlab"}:
        raise ProviderError(f"fournisseur non pris en charge : {repository.provider}")
    if mode == "file":
        if file_path is None:
            raise ProviderError("mode fichier sans chemin fourni")
        path = Path(file_path).expanduser().resolve()
        if repository.provider == "github":
            return github_from_file(path)
        return gitlab_from_file(path)
    if mode != "http":
        raise ProviderError(f"mode de collecte inconnu : {mode}")

    http_client = client or UrllibHttpClient()
    etag_cache = cache or JsonETagCache(default_cache_path())
    if repository.provider == "github":
        owner, name = repository_owner_and_name(repository.url)
        if not owner or not name:
            raise ProviderError(f"URL GitHub invalide : {repository.url}")
        return GitHubCollector(
            http_client,
            token=token if token is not None else os.environ.get("GITHUB_TOKEN"),
            api_base=os.environ.get("GITHUB_API_URL", GITHUB_API_URL),
            cache=etag_cache,
            sleep=sleep,
            now=now,
        ).collect(owner, name)

    project_path = repository_path_from_url(repository.url)
    if not project_path:
        raise ProviderError(f"URL GitLab invalide : {repository.url}")
    return GitLabCollector(
        http_client,
        token=token if token is not None else os.environ.get("GITLAB_TOKEN"),
        api_base=os.environ.get("GITLAB_API_URL", _gitlab_api_base(repository.url)),
        cache=etag_cache,
        sleep=sleep,
        now=now,
    ).collect(project_path)


def _resolve_actor(
    session: Session,
    repository: Repository,
    *,
    login: str | None,
    name: str | None,
    email: str | None,
) -> int | None:
    if not login and not email:
        return None
    if login:
        person = resolve_person(
            session,
            repository.project,
            provider=repository.provider,
            external_id=login,
            email=email,
            display_name=name or login,
        )
    else:
        person = resolve_person(
            session,
            repository.project,
            email=email,
            display_name=name or email or "inconnu",
        )
    return person.id


def _upsert_merge_request(
    session: Session,
    repository: Repository,
    data: MergeRequestData,
) -> tuple[MergeRequest, bool]:
    mr = session.scalar(
        select(MergeRequest).where(
            MergeRequest.repository_id == repository.id,
            MergeRequest.number == data.number,
        )
    )
    created = mr is None
    if mr is None:
        mr = MergeRequest(
            repository_id=repository.id,
            number=data.number,
            state=data.state,
            title=data.title,
        )
        session.add(mr)
        session.flush()
    mr.title = data.title
    mr.state = data.state
    mr.author_person_id = _resolve_actor(
        session,
        repository,
        login=data.author_login,
        name=data.author_name,
        email=data.author_email,
    )
    mr.created_at = data.created_at
    mr.updated_at = data.updated_at
    mr.merged_at = data.merged_at
    mr.target_branch = data.target_branch
    mr.source_branch = data.source_branch
    mr.merge_strategy = data.merge_strategy
    mr.additions = data.additions
    mr.deletions = data.deletions
    mr.url = data.url
    mr.imported_at = utc_now()
    session.flush()
    return mr, created


def _sync_reviews(session: Session, repository: Repository, mr: MergeRequest, reviews: tuple[ReviewData, ...]) -> None:
    existing = {
        review.external_id: review
        for review in session.scalars(select(Review).where(Review.mr_id == mr.id)).all()
        if review.external_id
    }
    keep: set[str] = set()
    for data in reviews:
        keep.add(data.external_id)
        review = existing.get(data.external_id)
        if review is None:
            review = Review(mr_id=mr.id, external_id=data.external_id, state=data.state)
            session.add(review)
        review.reviewer_person_id = _resolve_actor(
            session,
            repository,
            login=data.reviewer_login,
            name=data.reviewer_name,
            email=None,
        )
        review.state = data.state
        review.submitted_at = data.submitted_at
        review.is_agent = data.is_agent
        review.model = data.model
        review.independence = data.independence
        review.imported_at = utc_now()
    for external_id, review in existing.items():
        if external_id not in keep:
            session.delete(review)
    session.flush()


def _sync_approvals(
    session: Session,
    repository: Repository,
    mr: MergeRequest,
    approvals: tuple[ApprovalData, ...],
) -> None:
    existing = {
        approval.external_id: approval
        for approval in session.scalars(select(Approval).where(Approval.mr_id == mr.id)).all()
        if approval.external_id
    }
    keep: set[str] = set()
    for data in approvals:
        keep.add(data.external_id)
        approval = existing.get(data.external_id)
        if approval is None:
            approval = Approval(mr_id=mr.id, external_id=data.external_id)
            session.add(approval)
        approval.actor_person_id = _resolve_actor(
            session,
            repository,
            login=data.actor_login,
            name=data.actor_name,
            email=None,
        )
        approval.actor_type = data.actor_type
        approval.approved_at = data.approved_at
        approval.imported_at = utc_now()
    for external_id, approval in existing.items():
        if external_id not in keep:
            session.delete(approval)
    session.flush()


def store_merge_requests(
    session: Session,
    repository: Repository,
    items: list[MergeRequestData],
) -> dict[str, int]:
    """Insère ou met à jour les MR, revues et approbations, sans doublon."""
    inserted = 0
    updated = 0
    review_count = 0
    approval_count = 0
    for data in items:
        mr, created = _upsert_merge_request(session, repository, data)
        inserted += 1 if created else 0
        updated += 0 if created else 1
        _sync_reviews(session, repository, mr, data.reviews)
        _sync_approvals(session, repository, mr, data.approvals)
        review_count += len(data.reviews)
        approval_count += len(data.approvals)
    session.flush()
    return {
        "merge_requests": len(items),
        "inserted": inserted,
        "updated": updated,
        "reviews": review_count,
        "approvals": approval_count,
    }


def collect_repository(
    session: Session,
    repository: Repository,
    *,
    mode: str = "http",
    file_path: str | Path | None = None,
    client: HttpClient | None = None,
    token: str | None = None,
    cache: JsonETagCache | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> IngestionRun:
    """Collecte un dépôt et journalise l'exécution."""
    if repository.retired_at is not None:
        raise ProviderError("un dépôt retiré ne peut pas être ingéré")
    run = IngestionRun(
        project_id=repository.project_id,
        repository_id=repository.id,
        source=repository.provider,
        started_at=utc_now(),
        status="running",
    )
    session.add(run)
    session.flush()
    try:
        with session.begin_nested():
            items = collect_merge_requests(
                repository,
                mode=mode,
                file_path=file_path,
                client=client,
                token=token,
                cache=cache,
                sleep=sleep,
                now=now,
            )
            stats = store_merge_requests(session, repository, items)
        run.status = "done"
        run.finished_at = utc_now()
        run.stats_json = redact(json.dumps({"mode": mode, **stats}, sort_keys=True))
        session.flush()
        return run
    except Exception as exc:  # noqa: BLE001 - l'échec est journalisé puis propagé
        run.status = "failed"
        run.finished_at = utc_now()
        run.error = redact(str(exc))[:2000]
        run.stats_json = redact(
            json.dumps({"mode": mode, "error": str(exc)[:500]}, ensure_ascii=False)
        )
        session.flush()
        if isinstance(exc, ProviderError):
            raise
        raise ProviderError(str(exc)) from exc


def collect_project(
    session: Session,
    project: Project,
    *,
    mode: str = "http",
    file_paths: Mapping[int, str | Path] | None = None,
    client: HttpClient | None = None,
    tokens: Mapping[str, str] | None = None,
    cache: JsonETagCache | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> list[IngestionRun]:
    """Collecte tous les dépôts actifs d'un projet."""
    runs: list[IngestionRun] = []
    for repository in list_repositories(session, project):
        path = file_paths.get(repository.id) if file_paths else None
        token = tokens.get(repository.provider) if tokens else None
        runs.append(
            collect_repository(
                session,
                repository,
                mode=mode,
                file_path=path,
                client=client,
                token=token,
                cache=cache,
                sleep=sleep,
                now=now,
            )
        )
    return runs
