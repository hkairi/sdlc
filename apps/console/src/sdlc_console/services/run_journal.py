"""Journal unifié des runs et taux d'indépendance des revues."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import MergeRequest, Project, Repository, Review, TaskRun, utc_now
from .audit import append_audit
from .escalations import notify_human

DEFAULT_INDEPENDENCE_THRESHOLD = 10.0


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    converted = _aware(value)
    return converted.isoformat() if converted is not None else None


def _duration(run: TaskRun, now: datetime) -> float | None:
    started = _aware(run.started_at)
    if started is None:
        return None
    ended = _aware(run.ended_at)
    return round(((ended or now) - started).total_seconds(), 2)


def _origin(origin: str) -> str:
    return "lancée" if origin == "lancée" else "ingérée"


def deduplicate_runs(runs: Sequence[TaskRun]) -> list[TaskRun]:
    """Union par `run_id`, avec priorité au run lancé localement."""
    selected: dict[str, TaskRun] = {}
    for run in runs:
        current = selected.get(run.run_id)
        if current is None or (run.origin == "lancée" and current.origin != "lancée"):
            selected[run.run_id] = run
    return sorted(
        selected.values(),
        key=lambda run: (_aware(run.started_at) or _aware(run.imported_at) or datetime.min.replace(tzinfo=UTC), run.id),
        reverse=True,
    )


def _run_data(run: TaskRun, now: datetime) -> dict[str, Any]:
    return {
        "id": run.id,
        "run_id": run.run_id,
        "task_key": run.task_key,
        "agent_id": run.agent_id,
        "role": run.role,
        "model": run.model,
        "status": run.status,
        "origin": _origin(run.origin),
        "started_at": _iso(run.started_at),
        "ended_at": _iso(run.ended_at),
        "duration_seconds": _duration(run, now),
        "cost_eur": run.cost_eur,
        "estimated_cost_eur": run.estimated_cost_eur,
        "budget_eur": run.budget_eur,
        "tokens_in": run.tokens_in,
        "tokens_out": run.tokens_out,
        "log_path": run.log_path,
        "report_path": run.report_path,
        "failure_reason": run.failure_reason,
        "events_url": f"/api/runs/{run.run_id}/events",
    }


def build_run_journal(
    session: Session,
    project: Project,
    *,
    agent_id: str | None = None,
    role: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Liste les runs ingérés et lancés, dédupliqués par `run_id`."""
    moment = _aware(now) or utc_now()
    query = select(TaskRun).where(TaskRun.project_id == project.id)
    if agent_id:
        query = query.where(TaskRun.agent_id == agent_id)
    if role:
        query = query.where(TaskRun.role == role)
    if status:
        query = query.where(TaskRun.status == status)
    rows = list(session.scalars(query).all())
    journal = deduplicate_runs(rows)
    total = len(journal)
    size = max(1, min(int(limit), 200))
    start = max(0, int(offset))
    page = journal[start : start + size]
    return {
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "filters": {"agent_id": agent_id, "role": role, "status": status},
        "runs": [_run_data(run, moment) for run in page],
        "total": total,
        "limit": size,
        "offset": start,
        "has_more": start + len(page) < total,
        "sources": {"runs": "runs.jsonl + API locale", "origin": "ingérée | lancée"},
    }


def _threshold(config: Mapping[str, Any] | None) -> float:
    review = (config or {}).get("review")
    review = review if isinstance(review, Mapping) else {}
    raw = review.get("independence_threshold_percent", DEFAULT_INDEPENDENCE_THRESHOLD)
    try:
        return max(0.0, min(100.0, float(raw)))
    except (TypeError, ValueError):
        return DEFAULT_INDEPENDENCE_THRESHOLD


def _review_pairs(
    session: Session,
    project: Project,
    start: datetime,
) -> tuple[list[dict[str, Any]], int]:
    """Associe les runs relecteur aux runs auteur par `task_key`."""
    runs = list(
        session.scalars(
            select(TaskRun)
            .where(
                TaskRun.project_id == project.id,
                TaskRun.role.in_(("executor", "author", "reviewer")),
            )
            .order_by(TaskRun.id)
        ).all()
    )
    by_task: dict[str, list[TaskRun]] = {}
    for run in runs:
        if not run.task_key:
            continue
        when = _aware(run.started_at) or _aware(run.imported_at)
        if when is None or when < start:
            continue
        by_task.setdefault(run.task_key, []).append(run)
    pairs: list[dict[str, Any]] = []
    unmeasured = 0
    for task_key, task_runs in by_task.items():
        authors = [run for run in task_runs if run.role in {"executor", "author"} and run.model]
        reviewers = [run for run in task_runs if run.role == "reviewer"]
        for reviewer in reviewers:
            author_models = {run.model for run in authors if run.model}
            if not author_models or not reviewer.model:
                unmeasured += 1
                continue
            independent = reviewer.model not in author_models
            pairs.append(
                {
                    "task_key": task_key,
                    "review_run_id": reviewer.run_id,
                    "author_models": sorted(author_models),
                    "reviewer_model": reviewer.model,
                    "independent": independent,
                    "degraded": not independent,
                }
            )
    return pairs, unmeasured


def _provider_review_pairs(
    session: Session,
    project: Project,
    start: datetime,
) -> tuple[list[dict[str, Any]], int]:
    reviews = list(
        session.scalars(
            select(Review)
            .join(MergeRequest, Review.mr_id == MergeRequest.id)
            .join(Repository, MergeRequest.repository_id == Repository.id)
            .where(Repository.project_id == project.id)
        ).all()
    )
    pairs: list[dict[str, Any]] = []
    unmeasured = 0
    for review in reviews:
        submitted = _aware(review.submitted_at) or _aware(review.imported_at)
        if submitted is None or submitted < start:
            continue
        if not review.is_agent and review.independence is None:
            continue
        if review.independence == "degraded":
            independent = False
        elif review.independence in {"complete", "partial"}:
            independent = True
        else:
            unmeasured += 1
            continue
        pairs.append(
            {
                "task_key": None,
                "review_id": review.id,
                "reviewer_model": review.model,
                "independence": review.independence,
                "independent": independent,
                "degraded": not independent,
            }
        )
    return pairs, unmeasured


def build_independence(
    session: Session,
    project: Project,
    *,
    window_days: int = 30,
    config: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calcule le taux de revues dégradées sur une fenêtre glissante."""
    moment = _aware(now) or utc_now()
    start = moment - timedelta(days=max(1, window_days))
    run_pairs, unmeasured_runs = _review_pairs(session, project, start)
    provider_pairs, unmeasured_provider = _provider_review_pairs(session, project, start)
    pairs = run_pairs + provider_pairs
    total = len(pairs)
    degraded = sum(1 for pair in pairs if pair["degraded"])
    independent = total - degraded
    rate = round(degraded * 100 / total, 2) if total else None
    threshold = _threshold(config)
    measured = total > 0
    return {
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "window_days": max(1, window_days),
        "window_start": start.isoformat(),
        "total_reviews": total,
        "independent_reviews": independent,
        "degraded_reviews": degraded,
        "degraded_rate_percent": rate,
        "threshold_percent": threshold,
        "decision_required": bool(measured and rate is not None and rate >= threshold),
        "status": "measured" if measured else "not_measured",
        "unmeasured_reviews": unmeasured_runs + unmeasured_provider,
        "reviews": pairs,
        "sources": {
            "runs": "task_runs (30 j)",
            "provider_reviews": "reviews GitHub/GitLab (30 j)",
        },
        "detail": (
            f"{degraded}/{total} revue(s) dégradée(s)"
            if measured
            else "aucune revue avec modèle auteur et relecteur"
        ),
    }


def record_independence_alert(
    session: Session,
    project: Project,
    summary: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Crée une notification et un audit si le seuil est atteint."""
    if not summary.get("decision_required"):
        return None
    notification, created = notify_human(
        session,
        project,
        kind="independence_threshold",
        subject_type="project",
        subject_id=str(project.id),
        message=(
            f"Seuil d'indépendance atteint : {summary.get('degraded_rate_percent')} % "
            f"de revues dégradées (seuil {summary.get('threshold_percent')} %)."
        ),
        payload={
            "degraded_rate_percent": summary.get("degraded_rate_percent"),
            "threshold_percent": summary.get("threshold_percent"),
            "total_reviews": summary.get("total_reviews"),
            "degraded_reviews": summary.get("degraded_reviews"),
            "window_days": summary.get("window_days"),
        },
    )
    if created:
        append_audit(
            session,
            project_id=project.id,
            action="review.independence_threshold",
            object_type="project",
            object_id=str(project.id),
            payload={
                "degraded_rate_percent": summary.get("degraded_rate_percent"),
                "threshold_percent": summary.get("threshold_percent"),
                "total_reviews": summary.get("total_reviews"),
                "degraded_reviews": summary.get("degraded_reviews"),
                "notification_id": notification.id,
                "decision_required": True,
            },
        )
    return {
        "decision_required": True,
        "notification_id": notification.id,
        "created": created,
        "message": notification.message,
    }
