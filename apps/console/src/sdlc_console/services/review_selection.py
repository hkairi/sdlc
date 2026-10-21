"""Sélection d'un relecteur indépendant par agent, modèle et famille."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

LEVELS = {"degraded": 1, "partial": 2, "complete": 3}


@dataclass(frozen=True)
class ReviewerCandidate:
    agent_id: str
    model: str
    family: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class ReviewerSelection:
    selected: ReviewerCandidate | None
    level: str
    allowed: bool
    waiver_required: bool
    reason: str
    candidates: tuple[dict[str, Any], ...]


def independence_level(
    *,
    author_agent: str,
    author_model: str,
    author_family: str | None,
    candidate: ReviewerCandidate,
) -> str:
    """Calcule le niveau d'indépendance, du plus fort au plus faible."""
    same_agent = author_agent == candidate.agent_id
    same_model = author_model == candidate.model
    same_family = bool(author_family and candidate.family and author_family == candidate.family)
    if not same_agent and not same_model and not same_family:
        return "complete"
    if not same_agent and not same_model:
        return "partial"
    return "degraded"


def candidates_from_config(config: Mapping[str, Any] | None) -> tuple[ReviewerCandidate, ...]:
    """Construit les candidats depuis `agents` de la configuration."""
    agents = (config or {}).get("agents")
    if not isinstance(agents, Mapping):
        return ()
    candidates: list[ReviewerCandidate] = []
    for agent_id, definition in agents.items():
        if not isinstance(definition, Mapping) or not definition.get("enabled", False):
            continue
        models = definition.get("models")
        if not isinstance(models, Mapping):
            continue
        for model_name, raw in models.items():
            family = None
            label = None
            if isinstance(raw, Mapping):
                family = str(raw["family"]) if raw.get("family") else None
                label = str(raw["label"]) if raw.get("label") else None
            candidates.append(
                ReviewerCandidate(
                    agent_id=str(agent_id),
                    model=str(model_name),
                    family=family,
                    label=label,
                )
            )
    return tuple(candidates)


def select_reviewer(
    *,
    author_agent: str,
    author_model: str,
    candidates: Sequence[ReviewerCandidate],
    author_family: str | None = None,
    waiver: bool = False,
) -> ReviewerSelection:
    """Sélectionne le meilleur niveau disponible ; dégradé = dérogation requise."""
    ranked: list[tuple[int, ReviewerCandidate, str]] = []
    for candidate in candidates:
        level = independence_level(
            author_agent=author_agent,
            author_model=author_model,
            author_family=author_family,
            candidate=candidate,
        )
        ranked.append((LEVELS[level], candidate, level))
    ranked.sort(key=lambda item: (-item[0], item[1].agent_id, item[1].model))
    payload = tuple(
        {
            "agent_id": candidate.agent_id,
            "model": candidate.model,
            "family": candidate.family,
            "label": candidate.label,
            "independence": level,
        }
        for _rank, candidate, level in ranked
    )
    if not ranked:
        return ReviewerSelection(
            selected=None,
            level="degraded",
            allowed=False,
            waiver_required=True,
            reason="aucun relecteur configuré",
            candidates=(),
        )
    _rank, selected, level = ranked[0]
    if level == "degraded":
        return ReviewerSelection(
            selected=selected if waiver else None,
            level="degraded",
            allowed=waiver,
            waiver_required=not waiver,
            reason=(
                "relecteur dégradé accepté par dérogation"
                if waiver
                else "aucun relecteur indépendant : dérogation humaine requise"
            ),
            candidates=payload,
        )
    return ReviewerSelection(
        selected=selected,
        level=level,
        allowed=True,
        waiver_required=False,
        reason=f"relecteur sélectionné au niveau {level}",
        candidates=payload,
    )
