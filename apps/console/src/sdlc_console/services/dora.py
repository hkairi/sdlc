"""Métriques DORA calculées depuis les déploiements et les incidents."""

from __future__ import annotations

import re
import statistics
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Deployment, Feature, Project, utc_now
from .providers.common import parse_datetime

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?")


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


def _metric(
    key: str,
    label: str,
    value: float | int | None,
    unit: str,
    *,
    window_days: int,
    source: str,
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "unit": unit,
        "window_days": window_days,
        "source": source,
        "status": "measured" if value is not None else "not_measured",
        "detail": detail or ("mesuré" if value is not None else "non mesuré"),
    }


def parse_incident_file(path: str | Path) -> tuple[datetime, datetime] | None:
    """Lit les dates de début et de retour à la normale d'un incident Markdown."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    start = None
    end = None
    for line in text.splitlines():
        lowered = line.casefold()
        dates = DATE_RE.findall(line)
        if not dates:
            continue
        if any(token in lowered for token in ("début", "started", "start at", "start:")):
            start = parse_datetime(dates[0])
        elif any(token in lowered for token in ("retour", "resolved", "resolution", "fin:", "end:")):
            end = parse_datetime(dates[-1])
    if start is None or end is None or end < start:
        return None
    return start, end


def _incidents_from_files(paths: Sequence[str | Path]) -> list[tuple[datetime, datetime]]:
    values: list[tuple[datetime, datetime]] = []
    for path in paths:
        parsed = parse_incident_file(path)
        if parsed is not None:
            values.append(parsed)
    return values


def _incidents_from_data(items: Sequence[Mapping[str, Any]] | None) -> list[tuple[datetime, datetime]]:
    values: list[tuple[datetime, datetime]] = []
    for item in items or []:
        start = parse_datetime(item.get("started_at") or item.get("start"))
        end = parse_datetime(item.get("resolved_at") or item.get("end"))
        if start is not None and end is not None and end >= start:
            values.append((start, end))
    return values


def build_dora(
    session: Session,
    project: Project,
    *,
    window_days: int = 30,
    incident_paths: Sequence[str | Path] | None = None,
    incidents: Sequence[Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calcule les quatre métriques DORA, sans inventer de valeur absente."""
    moment = _aware(now) or utc_now()
    start = moment - timedelta(days=window_days)
    deployments = list(
        session.scalars(
            select(Deployment).where(Deployment.project_id == project.id)
        ).all()
    )
    def _in_window(deployment: Deployment) -> bool:
        if deployment.env.strip().lower() not in {"prod", "production"}:
            return False
        started = _aware(deployment.started_at)
        return started is None or started >= start

    prod = [deployment for deployment in deployments if _in_window(deployment)]
    successful = [
        deployment
        for deployment in prod
        if deployment.status.lower() == "success" and not deployment.is_rollback
    ]
    failed = [
        deployment
        for deployment in prod
        if deployment.status.lower() in {"failed", "rollback"} or deployment.is_rollback
    ]
    frequency = round(len(successful) / (window_days / 7), 2) if prod else None
    cfr = round(len(failed) * 100 / len(prod), 2) if prod else None

    features = {
        feature.id: feature
        for feature in session.scalars(
            select(Feature).where(Feature.project_id == project.id)
        ).all()
    }
    lead_times: list[float] = []
    for deployment in prod:
        feature = features.get(deployment.feature_id) if deployment.feature_id else None
        if feature is None and deployment.feature_key:
            feature = next(
                (item for item in features.values() if item.key == deployment.feature_key),
                None,
            )
        started = _aware(deployment.started_at)
        frozen = _aware(feature.updated_at) if feature is not None else None
        if started is not None and frozen is not None and started >= frozen:
            lead_times.append((started - frozen).total_seconds() / 3600)
    lead_time = round(statistics.median(lead_times), 2) if lead_times else None

    incident_values = _incidents_from_data(incidents)
    if incident_paths is None:
        incident_values.extend(_incidents_from_files(sorted(Path("docs/incidents").glob("*.md"))))
    else:
        incident_values.extend(_incidents_from_files(incident_paths))
    durations = [
        (end - begin).total_seconds() / 3600
        for begin, end in incident_values
        if end >= begin
    ]
    mttr = round(statistics.mean(durations), 2) if durations else None

    return {
        "generated_at": _iso(utc_now()),
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "window_days": window_days,
        "window_start": _iso(start),
        "deployments": {
            "prod": len(prod),
            "successful": len(successful),
            "failed": len(failed),
        },
        "metrics": [
            _metric(
                "deployment_frequency",
                "Fréquence de déploiement",
                frequency,
                "/semaine",
                window_days=window_days,
                source="deploys.jsonl",
                detail=f"{len(successful)} déploiement(s) réussi(s) sur {window_days} jours",
            ),
            _metric(
                "change_failure_rate",
                "Change failure rate",
                cfr,
                "%",
                window_days=window_days,
                source="deploys.jsonl",
                detail=f"{len(failed)} échec(s)/rollback(s) sur {len(prod)} déploiement(s)",
            ),
            _metric(
                "lead_time",
                "Lead time",
                lead_time,
                "h",
                window_days=window_days,
                source="features.updated_at + deploys.jsonl",
                detail=(
                    "médiane des écarts feature → déploiement prod"
                    if lead_time is not None
                    else "dates spec/feature ou déploiement absentes"
                ),
            ),
            _metric(
                "mttr",
                "MTTR",
                mttr,
                "h",
                window_days=window_days,
                source="docs/incidents/*.md",
                detail=(
                    f"{len(durations)} incident(s) exploitable(s)"
                    if durations
                    else "aucun incident avec dates début/résolution"
                ),
            ),
        ],
        "incidents": [
            {"started_at": _iso(begin), "resolved_at": _iso(end)}
            for begin, end in incident_values
        ],
        "sources": {
            "deployments": "deploys.jsonl",
            "incidents": "docs/incidents/*.md",
            "features": "state.json",
        },
    }
