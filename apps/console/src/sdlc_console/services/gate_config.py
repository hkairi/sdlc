"""Lecture centralisée des seuils de gates depuis la configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_COVERAGE = {"global": 80.0, "changed": 90.0, "file": 80.0}
DEFAULT_PERFORMANCE = {
    "regression_percent": 10.0,
    "warning_percent": 5.0,
    "budget_warning_ratio": 0.9,
}
DEFAULT_PERFORMANCE_BUDGETS = {
    "default_p95_ms": None,
    "default_bundle_kb": None,
}
DEFAULT_DATA = {"retention_days": None, "encrypted": None}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def quality(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return _mapping((config or {}).get("quality"))


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def coverage_thresholds(
    config: Mapping[str, Any] | None,
    overrides: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Seuils de couverture `quality.coverage` avec compatibilité `coverage`."""
    values = dict(DEFAULT_COVERAGE)
    raw = quality(config).get("coverage")
    if not isinstance(raw, Mapping):
        raw = _mapping((config or {}).get("coverage"))
    aliases = {
        "global": ("global_min", "global"),
        "changed": ("changed_lines_min", "changed"),
        "file": ("per_file_min", "file"),
    }
    for key, candidates in aliases.items():
        for candidate in candidates:
            value = _number(raw.get(candidate))
            if value is not None:
                values[key] = value
                break
    if overrides:
        for key, value in overrides.items():
            if key in values:
                values[key] = float(value)
    for key, value in values.items():
        if not 0 <= value <= 100:
            raise ValueError(f"seuil de couverture invalide : {key}={value}")
    return values


def performance_thresholds(
    config: Mapping[str, Any] | None,
    overrides: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        **DEFAULT_PERFORMANCE,
        **DEFAULT_PERFORMANCE_BUDGETS,
    }
    raw = quality(config).get("performance")
    if not isinstance(raw, Mapping):
        raw = _mapping((config or {}).get("performance"))
    for key in values:
        value = _number(raw.get(key))
        if value is not None:
            values[key] = value
    for source, target in (
        ("p95_ms", "default_p95_ms"),
        ("bundle_kb", "default_bundle_kb"),
    ):
        value = _number(raw.get(source))
        if value is not None:
            values[target] = value
    if overrides:
        for key, value in overrides.items():
            if key in values:
                values[key] = float(value)
    return values


def security_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = quality(config).get("security")
    raw = raw if isinstance(raw, Mapping) else {}
    block_on_raw = raw.get("block_on")
    block_on = (
        tuple(str(item).lower() for item in block_on_raw)
        if isinstance(block_on_raw, (list, tuple))
        else ("critical", "high")
    )
    return {
        "block_on": block_on,
        "reachability": bool(raw.get("reachability", True)),
    }


def data_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = quality(config).get("data")
    raw = raw if isinstance(raw, Mapping) else {}
    retention = _mapping((config or {}).get("retention")).get("default_days")
    if retention is None:
        retention = raw.get("retention_days")
    encrypted = raw.get("encrypted", raw.get("encryption"))
    return {
        "retention_days": int(retention) if isinstance(retention, int) else None,
        "encrypted": encrypted if isinstance(encrypted, bool) else None,
    }
