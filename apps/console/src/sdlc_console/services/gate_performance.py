"""Gate de performance : budgets observés, régressions et signaux statiques."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import GateRun, Project
from ..paths import PathSecurityError, resolve_within
from .gate_config import performance_thresholds
from .gates import (
    ControlResult,
    Evidence,
    Finding,
    GateError,
    GateEvaluation,
    evaluate_gate,
    persist_gate_run,
)


@dataclass(frozen=True)
class PerformanceCase:
    """Mesure observée d'un cas de performance."""

    name: str
    p50_ms: float | None = None
    p95_ms: float | None = None
    p99_ms: float | None = None
    budget_ms: float | None = None
    previous_p95_ms: float | None = None
    baseline_p95_ms: float | None = None
    bundle_kb: float | None = None
    bundle_budget_kb: float | None = None
    requests: float | None = None
    request_budget: float | None = None
    memory_mb: float | None = None
    memory_budget_mb: float | None = None
    commit: str | None = None
    window: str | None = None
    tool: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class StaticSignal:
    """Signal statique (N+1, requête non bornée, I/O sync, regex, image)."""

    kind: str
    message: str
    file: str | None = None
    line: int | None = None
    severity: str = "warning"


@dataclass(frozen=True)
class PerformanceGateResult:
    """Résultat du gate de performance."""

    evaluation: GateEvaluation
    run: GateRun
    cases: tuple[PerformanceCase, ...]
    signals: tuple[StaticSignal, ...]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _case(raw: Mapping[str, Any], source: Path) -> PerformanceCase:
    return PerformanceCase(
        name=str(raw.get("case") or raw.get("name") or "cas"),
        p50_ms=_number(raw.get("p50_ms")),
        p95_ms=_number(raw.get("p95_ms")),
        p99_ms=_number(raw.get("p99_ms")),
        budget_ms=_number(raw.get("budget_ms")),
        previous_p95_ms=_number(raw.get("previous_p95_ms")),
        baseline_p95_ms=_number(raw.get("baseline_p95_ms")),
        bundle_kb=_number(raw.get("bundle_kb")),
        bundle_budget_kb=_number(raw.get("bundle_budget_kb")),
        requests=_number(raw.get("requests")),
        request_budget=_number(raw.get("request_budget")),
        memory_mb=_number(raw.get("memory_mb")),
        memory_budget_mb=_number(raw.get("memory_budget_mb")),
        commit=str(raw["commit"]) if raw.get("commit") else None,
        window=str(raw["window"]) if raw.get("window") else None,
        tool=str(raw["tool"]) if raw.get("tool") else None,
        source=str(source),
    )


def _signal(raw: Mapping[str, Any]) -> StaticSignal:
    line = raw.get("line")
    try:
        line_number = int(line) if line is not None else None
    except (TypeError, ValueError):
        line_number = None
    return StaticSignal(
        kind=str(raw.get("kind") or raw.get("rule") or "static"),
        message=str(raw.get("message") or raw.get("description") or "signal statique"),
        file=str(raw["file"]) if raw.get("file") else None,
        line=line_number,
        severity=str(raw.get("severity") or "warning"),
    )


def parse_perf_file(
    path: str | Path,
    *,
    root: str | Path | None = None,
) -> tuple[tuple[PerformanceCase, ...], tuple[StaticSignal, ...]]:
    """Lit un JSON de performance, ses cas et ses signaux statiques."""
    root_path = Path(root or Path.cwd()).resolve()
    try:
        source = resolve_within(root_path, path)
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (PathSecurityError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise GateError(f"preuve de performance illisible : {path} : {exc}") from exc
    cases_raw: list[Mapping[str, Any]] = []
    signals_raw: list[Mapping[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                if "p95_ms" in item or "p99_ms" in item or "budget_ms" in item:
                    cases_raw.append(item)
                elif "message" in item:
                    signals_raw.append(item)
    elif isinstance(payload, dict):
        raw_cases = payload.get("cases")
        if isinstance(raw_cases, list):
            cases_raw.extend(item for item in raw_cases if isinstance(item, dict))
        elif any(key in payload for key in ("p95_ms", "p99_ms", "budget_ms")):
            cases_raw.append(payload)
        raw_signals = payload.get("signals")
        if isinstance(raw_signals, list):
            signals_raw.extend(item for item in raw_signals if isinstance(item, dict))
    return (
        tuple(_case(item, source) for item in cases_raw),
        tuple(_signal(item) for item in signals_raw),
    )


def collect_perf_paths(
    *,
    root: str | Path | None = None,
    evidence_paths: Sequence[str | Path] | None = None,
    evidence_root: str | Path | None = None,
) -> list[Path]:
    root_path = Path(root or Path.cwd()).resolve()
    base = Path(evidence_root or root_path)
    candidates = (
        [Path(item) for item in evidence_paths]
        if evidence_paths is not None
        else sorted((base / "reports" / "perf").glob("*.json"))
    )
    paths: list[Path] = []
    for candidate in candidates:
        try:
            path = resolve_within(root_path, candidate)
        except (PathSecurityError, FileNotFoundError, OSError):
            continue
        if path.is_file() and path not in paths:
            paths.append(path)
    return paths


def _thresholds(
    config: Mapping[str, Any] | None,
    overrides: Mapping[str, float] | None,
) -> dict[str, Any]:
    return performance_thresholds(config, overrides)


def _metric_check(
    value: float | None,
    budget: float | None,
    *,
    warning_ratio: float,
) -> str | None:
    if value is None or budget is None:
        return None
    if value > budget:
        return "fail"
    if value >= budget * warning_ratio:
        return "warn"
    return "pass"


def _regression(
    value: float,
    reference: float | None,
    *,
    fail_percent: float,
    warn_percent: float,
) -> str | None:
    if reference is None or reference <= 0:
        return None
    regression = (value - reference) * 100 / reference
    if regression > fail_percent:
        return "fail"
    if regression > warn_percent:
        return "warn"
    return None


def run_performance_gate(
    session: Session,
    project: Project,
    *,
    evidence_paths: Sequence[str | Path] | None = None,
    evidence_root: str | Path | None = None,
    static_signals: Sequence[StaticSignal] = (),
    thresholds: Mapping[str, float] | None = None,
    reports_dir: str | Path = "reports/gates",
    root: str | Path | None = None,
    config: Mapping[str, Any] | None = None,
) -> PerformanceGateResult:
    """Évalue le gate performance et persiste le rapport."""
    root_path = Path(root or Path.cwd()).resolve()
    paths = collect_perf_paths(
        root=root_path,
        evidence_paths=evidence_paths,
        evidence_root=evidence_root,
    )
    values = _thresholds(config, thresholds)
    cases: list[PerformanceCase] = []
    signals: list[StaticSignal] = list(static_signals)
    for path in paths:
        parsed_cases, parsed_signals = parse_perf_file(path, root=root_path)
        cases.extend(parsed_cases)
        signals.extend(parsed_signals)
    evidence = tuple(
        Evidence(
            path=_relative(path, root_path),
            kind="performance",
            description=path.name,
        )
        for path in paths
    )
    if not paths:
        if not static_signals:
            control = ControlResult(
                key="observed",
                verdict="not_run",
                reason="aucune preuve de performance dans reports/perf/*.json",
                details={"thresholds": values},
            )
            evaluation = evaluate_gate(
                "performance",
                [control],
                gate_name="Performance",
                config=config,
                root=root_path,
            )
            run = persist_gate_run(
                session,
                project,
                evaluation,
                reports_dir=reports_dir,
                config=config,
                root=root_path,
            )
            return PerformanceGateResult(evaluation, run, (), ())
        early_static_findings = [
            Finding(
                key=f"perf:static:{signal.kind}",
                severity="warning",
                message=signal.message,
                file=signal.file,
                line=signal.line,
            )
            for signal in static_signals
        ]
        controls = [
            ControlResult(
                key="observed",
                verdict="not_applicable",
                expected=False,
                reason="aucune preuve de performance observée",
                details={"thresholds": values},
            ),
            ControlResult(
                key="static",
                verdict="warn",
                expected=False,
                reason=f"{len(static_signals)} signal(aux) statique(s)",
                findings=tuple(early_static_findings),
            ),
        ]
        evaluation = evaluate_gate(
            "performance",
            controls,
            gate_name="Performance",
            config=config,
            root=root_path,
        )
        run = persist_gate_run(
            session,
            project,
            evaluation,
            reports_dir=reports_dir,
            config=config,
            root=root_path,
        )
        return PerformanceGateResult(
            evaluation,
            run,
            (),
            tuple(static_signals),
        )

    observed_findings: list[Finding] = []
    static_findings: list[Finding] = []
    observations: list[dict[str, Any]] = []
    observed_verdict = "pass"
    for case in cases:
        statuses: list[str] = []
        previous = case.previous_p95_ms or case.baseline_p95_ms
        default_budget = (
            float(values["default_p95_ms"])
            if values.get("default_p95_ms") is not None
            else None
        )
        default_bundle = (
            float(values["default_bundle_kb"])
            if values.get("default_bundle_kb") is not None
            else None
        )
        for metric_name, value, budget in (
            ("p95", case.p95_ms, case.budget_ms or default_budget),
            ("p99", case.p99_ms, case.budget_ms or default_budget),
            ("bundle", case.bundle_kb, case.bundle_budget_kb or default_bundle),
            ("requests", case.requests, case.request_budget),
            ("memory", case.memory_mb, case.memory_budget_mb),
        ):
            status = _metric_check(
                value,
                budget,
                warning_ratio=float(values["budget_warning_ratio"]),
            )
            if status is not None:
                statuses.append(status)
                if status == "fail":
                    observed_findings.append(
                        Finding(
                            key=f"perf:{case.name}:{metric_name}",
                            severity="error",
                            message=(
                                f"{metric_name}={value} dépasse le budget {budget}"
                            ),
                            evidence=case.source,
                        )
                    )
                elif status == "warn":
                    observed_findings.append(
                        Finding(
                            key=f"perf:{case.name}:{metric_name}",
                            severity="warning",
                            message=(
                                f"{metric_name}={value} proche du budget {budget}"
                            ),
                            evidence=case.source,
                        )
                    )
        if case.p95_ms is not None and previous is not None:
            regression = _regression(
                case.p95_ms,
                previous,
                fail_percent=float(values["regression_percent"]),
                warn_percent=float(values["warning_percent"]),
            )
            if regression is not None:
                statuses.append(regression)
                observed_findings.append(
                    Finding(
                        key=f"perf:{case.name}:regression",
                        severity=("error" if regression == "fail" else "warning"),
                        message=(
                            f"p95 {case.p95_ms} ms contre {previous} ms de référence"
                        ),
                        evidence=case.source,
                    )
                )
        if not statuses:
            observed_findings.append(
                Finding(
                    key=f"perf:{case.name}:mesure",
                    severity="warning",
                    message="mesure de performance incomplète ou sans budget",
                    evidence=case.source,
                )
            )
            statuses.append("warn")
        if "fail" in statuses:
            observed_verdict = "fail"
        elif "warn" in statuses and observed_verdict != "fail":
            observed_verdict = "warn"
        observations.append(
            {
                "case": case.name,
                "p50_ms": case.p50_ms,
                "p95_ms": case.p95_ms,
                "p99_ms": case.p99_ms,
                "budget_ms": case.budget_ms,
                "bundle_kb": case.bundle_kb,
                "requests": case.requests,
                "memory_mb": case.memory_mb,
                "status": "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "pass"),
            }
        )

    for signal in signals:
        static_findings.append(
            Finding(
                key=f"perf:static:{signal.kind}",
                severity="warning",
                message=signal.message,
                file=signal.file,
                line=signal.line,
            )
        )
    static_verdict = "warn" if signals else "pass"
    if not cases:
        observed_verdict = "not_applicable" if signals else "not_run"
    controls = [
        ControlResult(
            key="observed",
            verdict=observed_verdict,
            expected=bool(cases) or not signals,
            reason=(
                f"{len(cases)} cas observé(s)"
                if cases
                else "aucun cas observé"
            ),
            evidence=evidence,
            findings=tuple(observed_findings),
            details={"cases": observations, "thresholds": values},
        ),
        ControlResult(
            key="static",
            verdict=static_verdict,
            expected=False,
            reason=f"{len(signals)} signal(aux) statique(s)",
            evidence=evidence,
            findings=tuple(static_findings),
        ),
    ]
    evaluation = evaluate_gate(
        "performance",
        controls,
        gate_name="Performance",
        config=config,
        root=root_path,
    )
    run = persist_gate_run(
        session,
        project,
        evaluation,
        reports_dir=reports_dir,
        config=config,
        root=root_path,
    )
    return PerformanceGateResult(
        evaluation=evaluation,
        run=run,
        cases=tuple(cases),
        signals=tuple(signals),
    )
