"""Vue Configuration : validation du schéma, config effective et origines."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import load_schema
from ..models import Feature, GateRun, Project, Repository, TaskRun
from ..redaction import redact_value

ORIGIN_DECLARED = "déclarée"
ORIGIN_DETECTED = "détectée"
ORIGIN_MEASURED = "mesurée"


def _validation_errors(config: Mapping[str, Any], schema: Mapping[str, Any]) -> list[dict[str, str]]:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(config),
        key=lambda error: (list(error.path), error.message),
    )
    payload: list[dict[str, str]] = []
    for error in errors:
        path = ".".join(str(part) for part in error.path) or "(racine)"
        if error.validator == "required":
            match = re.search(r"'(.+)' is a required property", error.message)
            if match:
                prefix = ".".join(str(part) for part in error.path)
                path = f"{prefix}.{match.group(1)}" if prefix else match.group(1)
        payload.append({"path": path, "message": error.message})
    return payload


def _count(session: Session, model: type[Any], project: Project) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(model).where(model.project_id == project.id)
        )
        or 0
    )


def _flatten(value: Any, prefix: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(item, Mapping):
                rows.extend(_flatten(item, path))
            else:
                rows.append({"key": path, "value": item})
    else:
        rows.append({"key": prefix or "(racine)", "value": value})
    return rows


def build_configuration_view(
    session: Session,
    project: Project,
    *,
    config: Mapping[str, Any] | None = None,
    config_path: str | Path | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Affiche la configuration validée et l'origine de chaque donnée."""
    data = dict(config or {})
    schema = load_schema()
    errors = _validation_errors(data, schema)
    source = str(config_path or "sdlc.config.yaml")
    declared = [
        {
            **row,
            "origin": ORIGIN_DECLARED,
            "source": source,
        }
        for row in _flatten(redact_value(data))
    ]
    detected = [
        {
            "key": "repositories.count",
            "value": _count(session, Repository, project),
            "origin": ORIGIN_DETECTED,
            "source": "base SQLite — repositories",
        },
        {
            "key": "features.count",
            "value": _count(session, Feature, project),
            "origin": ORIGIN_DETECTED,
            "source": "base SQLite — features",
        },
    ]
    measured = [
        {
            "key": "runs.count",
            "value": _count(session, TaskRun, project),
            "origin": ORIGIN_MEASURED,
            "source": "base SQLite — task_runs",
        },
        {
            "key": "gates.count",
            "value": _count(session, GateRun, project),
            "origin": ORIGIN_MEASURED,
            "source": "base SQLite — gate_runs",
        },
    ]
    path = Path(config_path) if config_path is not None else Path("sdlc.config.yaml")
    return {
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "config_file": {
            "path": str(path),
            "exists": path.exists(),
            "readable": path.is_file(),
        },
        "validation": {
            "valid": not errors,
            "errors": errors,
            "schema_id": schema.get("$id"),
            "schema_title": schema.get("title"),
        },
        "effective": redact_value(data),
        "origins": declared + detected + measured,
        "sources": {
            "declared": source,
            "detected": "base SQLite",
            "measured": "base SQLite",
        },
        "notice": "Configuration en lecture seule. Modifiez sdlc.config.yaml puis redémarrez.",
    }
