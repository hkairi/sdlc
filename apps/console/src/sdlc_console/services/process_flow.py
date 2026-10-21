"""Flux de processus avec gates et liens vers leurs preuves."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import Project
from .gates import latest_gate_runs


def _gate_step(gates: dict[str, dict[str, Any]], key: str, label: str) -> dict[str, Any]:
    gate = gates.get(key)
    return {
        "id": key,
        "label": label,
        "type": "gate",
        "gate_key": key,
        "status": gate.get("verdict") if gate else "not_measured",
        "blocks": bool(gate.get("blocks")) if gate else False,
        "evidence": gate.get("report_path") if gate else None,
        "waiver": gate.get("waiver") if gate else None,
    }


def _step(identifier: str, label: str) -> dict[str, Any]:
    return {"id": identifier, "label": label, "type": "step", "status": "info"}


def build_process_flow(session: Session, project: Project) -> dict[str, Any]:
    """Expose le flux feature/release/hotfix et positionne les gates."""
    gates = {
        str(item["gate_key"]): item
        for item in latest_gate_runs(session, project)
    }
    flows = [
        {
            "id": "feature",
            "label": "Feature",
            "steps": [
                _step("feature", "Feature"),
                _step("mr", "Merge request"),
                _gate_step(gates, "review", "Revue indépendante"),
                _step("main", "main"),
            ],
        },
        {
            "id": "release",
            "label": "Release",
            "steps": [
                _step("release", "Release"),
                _step("tag", "Tag"),
                _step("preprod", "Préproduction"),
                _gate_step(gates, "recette", "Recette"),
                _gate_step(gates, "go_no_go", "Go / no-go"),
                _step("prod", "Production"),
            ],
        },
        {
            "id": "hotfix",
            "label": "Hotfix",
            "steps": [
                _step("hotfix", "Hotfix"),
                _gate_step(gates, "tests", "Tests"),
                _gate_step(gates, "security", "Sécurité"),
                _step("prod", "Production"),
            ],
        },
    ]
    return {
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "flows": flows,
        "gates": gates,
        "sources": {"gates": "reports/gates/*.json", "process": "state.json"},
    }
