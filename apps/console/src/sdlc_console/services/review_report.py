"""Rapport de revue structuré et fiche de décision."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Project, ReviewPackage, ReviewReport, utc_now
from ..paths import resolve_within
from ..redaction import redact_value
from ..security import verify_csp

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "review.schema.json"


class ReviewReportError(ValueError):
    """Rapport de revue invalide."""


@dataclass(frozen=True)
class ReviewReportResult:
    record: ReviewReport
    payload: dict[str, Any]
    report_path: Path
    decision_path: Path


def load_review_schema() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def validate_review_payload(payload: Mapping[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(load_review_schema()).iter_errors(payload),
        key=lambda error: list(error.path),
    )
    if errors:
        messages = [
            f"{'.'.join(str(part) for part in error.path) or '(racine)'}: {error.message}"
            for error in errors[:10]
        ]
        raise ReviewReportError("rapport invalide — " + " ; ".join(messages))


def _decision_markdown(payload: Mapping[str, Any]) -> str:
    sheet = payload["decision_sheet"]
    blockers = "\n".join(f"- {item}" for item in sheet["blockers"]) or "- aucun"
    risks = "\n".join(f"- {item}" for item in sheet["risks"]) or "- aucun"
    unverified = "\n".join(f"- {item}" for item in sheet["unverified"]) or "- aucun"
    questions = "\n".join(f"- {item}" for item in sheet["questions"]) or "- aucune"
    options = "\n".join(f"- {item}" for item in sheet["options"]) or "- aucune"
    return (
        f"# Fiche de décision — {payload['task_key']}\n\n"
        f"**Verdict :** {sheet['verdict']}  \n"
        f"**Confiance :** {sheet['confidence']}  \n"
        f"**Recommandation :** {sheet['recommendation']}\n\n"
        f"## Bloquants (max 3)\n{blockers}\n\n"
        f"## Risques\n{risks}\n\n"
        f"## Non vérifié\n{unverified}\n\n"
        f"## Questions humaines\n{questions}\n\n"
        f"## Options\n{options}\n"
    )


def build_review_report(
    session: Session,
    project: Project,
    package: ReviewPackage,
    *,
    verdict: str,
    confidence: float,
    findings: Sequence[Mapping[str, Any]],
    unverified: Sequence[str] = (),
    options: Sequence[Mapping[str, Any]] = (),
    recommendation: str = "",
    risks: Sequence[str] = (),
    questions: Sequence[str] = (),
    reports_dir: str | Path = "reports/reviews",
    root: str | Path | None = None,
) -> ReviewReportResult:
    """Valide, écrit et persiste un rapport de revue complet."""
    root_path = Path(root or Path.cwd()).resolve()
    blockers = [
        str(item.get("id"))
        for item in findings
        if str(item.get("severity")) == "blocker"
    ][:3]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "task_key": package.task_key,
        "package_fingerprint": package.fingerprint,
        "verdict": verdict,
        "confidence": float(confidence),
        "findings": [dict(item) for item in findings],
        "unverified": list(unverified),
        "options": [dict(item) for item in options],
        "decision_sheet": {
            "verdict": verdict,
            "confidence": float(confidence),
            "blockers": blockers,
            "risks": list(risks),
            "unverified": list(unverified),
            "questions": list(questions),
            "options": [str(item.get("label")) for item in options],
            "recommendation": recommendation or "À décider par l'humain.",
        },
        "generated_at": utc_now().isoformat(),
        "csp": verify_csp(),
    }
    payload = cast(dict[str, Any], redact_value(payload))
    validate_review_payload(payload)
    output_dir = resolve_within(root_path, reports_dir, allow_missing=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_task = "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in package.task_key
    )
    report_path = output_dir / f"{safe_task}-review.json"
    decision_path = output_dir / f"{safe_task}-decision.md"
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    decision_path.write_text(_decision_markdown(payload), encoding="utf-8")
    record = ReviewReport(
        project_id=project.id,
        package_id=package.id,
        task_key=package.task_key,
        verdict=verdict,
        confidence=float(confidence),
        report_path=str(report_path),
        decision_path=str(decision_path),
        payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )
    session.add(record)
    session.flush()
    return ReviewReportResult(
        record=record,
        payload=payload,
        report_path=report_path,
        decision_path=decision_path,
    )


def list_review_reports(session: Session, project: Project) -> list[ReviewReport]:
    return list(
        session.scalars(
            select(ReviewReport)
            .where(ReviewReport.project_id == project.id)
            .order_by(ReviewReport.id.desc())
        ).all()
    )
