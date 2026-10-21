"""Budget et coût réel des runs d'agents."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from ..models import TaskRun, utc_now
from .agent_runner import cancel_run


def estimate_from_tokens(
    run: TaskRun,
    *,
    config: Mapping[str, Any] | None = None,
) -> float | None:
    """Estime le coût depuis les tokens et les tarifs éventuels du modèle."""
    if run.tokens_in is None and run.tokens_out is None:
        return None
    agents = (config or {}).get("agents")
    agent = agents.get(run.agent_id) if isinstance(agents, Mapping) else None
    models = agent.get("models") if isinstance(agent, Mapping) else None
    model = models.get(run.model) if isinstance(models, Mapping) else None
    rates = model if isinstance(model, Mapping) else {}
    input_rate = rates.get("input_cost_per_mtok")
    output_rate = rates.get("output_cost_per_mtok")
    if not isinstance(input_rate, (int, float)) or not isinstance(output_rate, (int, float)):
        return None
    cost = (
        (run.tokens_in or 0) * float(input_rate)
        + (run.tokens_out or 0) * float(output_rate)
    ) / 1_000_000
    return round(cost, 4)


def budget_summary(run: TaskRun, *, estimated: float | None = None, actual: float | None = None) -> dict[str, Any]:
    estimated_value = estimated if estimated is not None else run.estimated_cost_eur
    actual_value = actual if actual is not None else run.cost_eur
    budget = run.budget_eur
    overrun = bool(budget is not None and actual_value is not None and actual_value > budget)
    remaining = round(budget - (actual_value or 0), 4) if budget is not None else None
    return {
        "budget_eur": budget,
        "estimated_eur": estimated_value,
        "actual_eur": actual_value,
        "remaining_eur": remaining,
        "overrun": overrun,
        "status": "overrun" if overrun else "within_budget" if budget is not None else "not_measured",
        "source": "tokens + tarifs" if estimated_value is not None else "coût déclaré",
    }


def apply_budget(
    session: Session,
    run: TaskRun,
    *,
    estimated_cost_eur: float | None = None,
    cost_eur: float | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    budget_eur: float | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Met à jour le budget et arrête le run si l'estimation atteint le plafond."""
    if budget_eur is not None:
        run.budget_eur = budget_eur
    if estimated_cost_eur is not None:
        run.estimated_cost_eur = estimated_cost_eur
    if cost_eur is not None:
        run.cost_eur = cost_eur
    if tokens_in is not None:
        run.tokens_in = tokens_in
    if tokens_out is not None:
        run.tokens_out = tokens_out
    if run.estimated_cost_eur is None:
        run.estimated_cost_eur = estimate_from_tokens(run, config=config)
    summary = budget_summary(run)
    budget = run.budget_eur
    if (
        budget is not None
        and run.estimated_cost_eur is not None
        and run.estimated_cost_eur >= budget
        and run.status in {"queued", "running"}
    ):
        cancel_run(session, run)
        run.status = "failed"
        run.failure_reason = "budget_exceeded"
        run.ended_at = utc_now()
        summary = budget_summary(run)
        summary["status"] = "budget_exceeded"
    elif budget is not None and run.cost_eur is not None and run.cost_eur > budget:
        run.failure_reason = "budget_exceeded"
        summary["status"] = "overrun"
    session.flush()
    return summary
