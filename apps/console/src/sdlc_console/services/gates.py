"""Moteur de gates : verdicts fondés sur des preuves et rapports JSON."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Gate, GateFinding, GateRun, Project, utc_now
from ..paths import PathSecurityError, resolve_within
from .waivers import effective_for_run

GATE_VERDICTS = frozenset(
    {"pass", "warn", "fail", "waived", "not_applicable", "not_run"}
)
FINDING_SEVERITIES = frozenset({"info", "warning", "error", "critical"})


class GateError(ValueError):
    """Erreur de définition ou d'évaluation d'un gate."""


@dataclass(frozen=True)
class Evidence:
    """Artefact de preuve lié à un contrôle."""

    path: str
    kind: str
    description: str | None = None


@dataclass(frozen=True)
class Finding:
    """Constat rattaché à un contrôle."""

    key: str
    severity: str
    message: str
    file: str | None = None
    line: int | None = None
    evidence: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in FINDING_SEVERITIES:
            raise GateError(f"sévérité de finding invalide : {self.severity}")


@dataclass(frozen=True)
class ControlResult:
    """Résultat d'un contrôle attendu ou non pour un gate."""

    key: str
    verdict: str
    expected: bool = True
    reason: str = ""
    evidence: tuple[Evidence, ...] = ()
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.verdict not in GATE_VERDICTS:
            raise GateError(f"verdict de contrôle invalide : {self.verdict}")


@dataclass(frozen=True)
class GateWaiver:
    """Dérogation motivée et datée."""

    reason: str
    approver: str
    expires_at: datetime
    owner: str | None = None


@dataclass(frozen=True)
class GateEvaluation:
    """Évaluation complète d'un gate, avant persistance."""

    gate_key: str
    gate_name: str
    blocking: bool
    verdict: str
    blocks: bool
    reason: str
    controls: tuple[dict[str, Any], ...]
    evidence: tuple[dict[str, Any], ...]
    findings: tuple[dict[str, Any], ...]
    waiver: dict[str, Any] | None
    config_fingerprint: str | None
    generated_at: datetime


def config_fingerprint(config: Mapping[str, Any] | None) -> str | None:
    """Empreinte canonique d'une configuration de gate."""
    if config is None:
        return None
    payload = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _evidence_data(evidence: Evidence, root: Path) -> dict[str, Any]:
    data: dict[str, Any] = {
        "path": evidence.path,
        "kind": evidence.kind,
        "description": evidence.description,
        "exists": False,
        "sha256": None,
        "resolved_path": None,
    }
    try:
        target = resolve_within(root, evidence.path)
    except (PathSecurityError, FileNotFoundError, OSError):
        return data
    if not target.is_file():
        return data
    data["exists"] = True
    data["resolved_path"] = str(target)
    data["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    return data


def _waiver_data(waiver: GateWaiver | None, now: datetime) -> dict[str, Any] | None:
    if waiver is None:
        return None
    expires = _as_utc(waiver.expires_at)
    return {
        "reason": waiver.reason,
        "approver": waiver.approver,
        "owner": waiver.owner,
        "expires_at": _iso(expires),
        "valid": bool(waiver.reason.strip() and waiver.approver.strip() and expires > now),
    }


def _control_data(
    control: ControlResult,
    root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    evidence = [_evidence_data(item, root) for item in control.evidence]
    findings = []
    for finding in control.findings:
        findings.append(
            {
                "key": finding.key,
                "severity": finding.severity,
                "message": finding.message,
                "file": finding.file,
                "line": finding.line,
                "evidence": finding.evidence,
                "control": control.key,
            }
        )
    verdict = control.verdict
    reason = control.reason
    if verdict == "pass" and not any(item["exists"] for item in evidence):
        verdict = "not_run"
        missing = "preuve absente : un gate vert exige un artefact lié"
        reason = f"{missing} — {reason}" if reason else missing
    if verdict == "waived":
        verdict = "fail"
        reason = reason or "dérogation de contrôle non supportée sans dérogation de gate"
    if verdict == "not_run" and not control.expected:
        verdict = "not_applicable"
        reason = reason or "contrôle hors tier"
    return (
        {
            "key": control.key,
            "verdict": verdict,
            "expected": control.expected,
            "reason": reason,
            "evidence": evidence,
            "findings": findings,
            "details": dict(control.details),
        },
        findings,
    )


def evaluate_gate(
    gate_key: str,
    controls: list[ControlResult] | tuple[ControlResult, ...],
    *,
    gate_name: str | None = None,
    blocking: bool = True,
    waiver: GateWaiver | None = None,
    config: Mapping[str, Any] | None = None,
    fingerprint: str | None = None,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
) -> GateEvaluation:
    """Calcule un verdict de gate ; un verdict vert sans preuve devient `not_run`."""
    key = gate_key.strip()
    if not key:
        raise GateError("clé de gate requise")
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", key):
        raise GateError(f"clé de gate invalide : {gate_key}")
    if not controls:
        raise GateError("un gate exige au moins un contrôle")
    root_path = Path(root or Path.cwd()).resolve()
    now = _as_utc(generated_at or utc_now())
    resolved_controls: list[dict[str, Any]] = []
    all_findings: list[dict[str, Any]] = []
    for control in controls:
        data, findings = _control_data(control, root_path)
        resolved_controls.append(data)
        all_findings.extend(findings)

    verdicts = [str(control["verdict"]) for control in resolved_controls]
    if "fail" in verdicts:
        verdict = "fail"
        reason = "au moins un contrôle a échoué"
    elif "not_run" in verdicts:
        verdict = "not_run"
        reason = "au moins un contrôle attendu n'a produit aucune preuve"
    elif "warn" in verdicts:
        verdict = "warn"
        reason = "au moins un contrôle est en avertissement"
    elif all(item == "waived" for item in verdicts):
        verdict = "waived"
        reason = "tous les contrôles sont couverts par une dérogation"
    elif all(item == "not_applicable" for item in verdicts):
        verdict = "not_applicable"
        reason = "aucun contrôle applicable au tier"
    else:
        verdict = "pass"
        reason = "tous les contrôles attendus passent avec preuve"

    waiver_payload = _waiver_data(waiver, now)
    if waiver_payload is not None and waiver_payload["valid"] and verdict in {
        "fail",
        "warn",
        "not_run",
    }:
        verdict = "waived"
        reason = f"dérogation valide : {waiver_payload['reason']}"

    blocks = blocking and verdict in {"fail", "not_run"}
    return GateEvaluation(
        gate_key=key,
        gate_name=gate_name or key,
        blocking=blocking,
        verdict=verdict,
        blocks=blocks,
        reason=reason,
        controls=tuple(resolved_controls),
        evidence=tuple(
            evidence
            for control in resolved_controls
            for evidence in control.get("evidence", [])
        ),
        findings=tuple(all_findings),
        waiver=waiver_payload,
        config_fingerprint=fingerprint if fingerprint is not None else config_fingerprint(config),
        generated_at=now,
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _report_payload(
    project: Project,
    evaluation: GateEvaluation,
    *,
    run_id: int,
    archive_path: Path,
) -> dict[str, Any]:
    return {
        "schema": 1,
        "notice": "Fichier généré, ne pas modifier.",
        "run_id": run_id,
        "generated_at": _iso(evaluation.generated_at),
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "gate": {
            "key": evaluation.gate_key,
            "name": evaluation.gate_name,
            "blocking": evaluation.blocking,
        },
        "verdict": evaluation.verdict,
        "blocks": evaluation.blocks,
        "reason": evaluation.reason,
        "config_fingerprint": evaluation.config_fingerprint,
        "controls": list(evaluation.controls),
        "evidence": list(evaluation.evidence),
        "findings": list(evaluation.findings),
        "waiver": evaluation.waiver,
        "archive_path": str(archive_path),
    }


def persist_gate_run(
    session: Session,
    project: Project,
    evaluation: GateEvaluation,
    *,
    reports_dir: str | Path = "reports/gates",
    repository_id: int | None = None,
    feature_id: int | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    config: Mapping[str, Any] | None = None,
    root: str | Path | None = None,
) -> GateRun:
    """Persiste le run et écrit le rapport JSON stable et archivé."""
    if evaluation.verdict not in GATE_VERDICTS:
        raise GateError(f"verdict de gate invalide : {evaluation.verdict}")
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", evaluation.gate_key):
        raise GateError(f"clé de gate invalide : {evaluation.gate_key}")
    root = Path(root or Path.cwd()).resolve()
    output_dir = resolve_within(root, reports_dir, allow_missing=True)
    gate = session.scalar(
        select(Gate).where(
            Gate.project_id == project.id,
            Gate.key == evaluation.gate_key,
        )
    )
    if gate is None:
        gate = Gate(
            project_id=project.id,
            key=evaluation.gate_key,
            name=evaluation.gate_name,
            blocking=evaluation.blocking,
            config_json=json.dumps(dict(config or {}), ensure_ascii=False, sort_keys=True),
            config_fingerprint=evaluation.config_fingerprint,
        )
        session.add(gate)
        session.flush()
    gate.name = evaluation.gate_name
    gate.blocking = evaluation.blocking
    gate.config_fingerprint = evaluation.config_fingerprint
    gate.config_json = json.dumps(dict(config or {}), ensure_ascii=False, sort_keys=True)
    gate.updated_at = utc_now()

    run = GateRun(
        project_id=project.id,
        gate_id=gate.id,
        gate_key=evaluation.gate_key,
        repository_id=repository_id,
        feature_id=feature_id,
        verdict=evaluation.verdict,
        blocks=evaluation.blocks,
        reason=evaluation.reason,
        report_path="",
        config_fingerprint=evaluation.config_fingerprint,
        controls_json=json.dumps(list(evaluation.controls), ensure_ascii=False, sort_keys=True),
        evidence_json=json.dumps(list(evaluation.evidence), ensure_ascii=False, sort_keys=True),
        findings_count=len(evaluation.findings),
        started_at=started_at or evaluation.generated_at,
        finished_at=finished_at or evaluation.generated_at,
        created_at=evaluation.generated_at,
    )
    session.add(run)
    session.flush()

    latest_path = output_dir / f"{evaluation.gate_key}.json"
    archive_path = output_dir / f"{evaluation.gate_key}-{run.id}.json"
    payload = _report_payload(
        project,
        evaluation,
        run_id=run.id,
        archive_path=archive_path,
    )
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        _atomic_write(latest_path, text)
        _atomic_write(archive_path, text)
        run.report_path = str(latest_path)
        for finding in evaluation.findings:
            session.add(
                GateFinding(
                    gate_run_id=run.id,
                    control_key=str(finding.get("control") or "gate"),
                    key=str(finding.get("key") or "finding"),
                    severity=str(finding.get("severity") or "info"),
                    message=str(finding.get("message") or ""),
                    file_path=finding.get("file"),
                    line=finding.get("line"),
                    evidence_path=finding.get("evidence"),
                )
            )
        session.commit()
    except Exception:
        latest_path.unlink(missing_ok=True)
        archive_path.unlink(missing_ok=True)
        session.rollback()
        raise
    return run


def run_gate(
    session: Session,
    project: Project,
    gate_key: str,
    controls: list[ControlResult] | tuple[ControlResult, ...],
    *,
    gate_name: str | None = None,
    blocking: bool = True,
    waiver: GateWaiver | None = None,
    config: Mapping[str, Any] | None = None,
    fingerprint: str | None = None,
    root: str | Path | None = None,
    reports_dir: str | Path = "reports/gates",
    repository_id: int | None = None,
    feature_id: int | None = None,
) -> tuple[GateEvaluation, GateRun]:
    """Évalue puis persiste un gate en une seule opération."""
    evaluation = evaluate_gate(
        gate_key,
        controls,
        gate_name=gate_name,
        blocking=blocking,
        waiver=waiver,
        config=config,
        fingerprint=fingerprint,
        root=root,
    )
    run = persist_gate_run(
        session,
        project,
        evaluation,
        reports_dir=reports_dir,
        repository_id=repository_id,
        feature_id=feature_id,
        config=config,
        root=root,
    )
    return evaluation, run


def latest_gate_runs(
    session: Session,
    project: Project,
    *,
    current_fingerprint: str | None = None,
) -> list[dict[str, Any]]:
    """Dernier run par gate, avec invalidation du cache de configuration."""
    runs = list(
        session.scalars(
            select(GateRun)
            .where(GateRun.project_id == project.id)
            .order_by(GateRun.id.desc())
        ).all()
    )
    latest: dict[str, GateRun] = {}
    for run in runs:
        latest.setdefault(run.gate_key, run)
    payload: list[dict[str, Any]] = []
    for run in latest.values():
        effective = effective_for_run(session, run)
        payload.append(
            {
                "gate_key": run.gate_key,
                "name": run.gate.name,
                "verdict": effective["verdict"],
                "base_verdict": run.verdict,
                "blocks": effective["blocks"],
                "reason": run.reason,
                "report_path": run.report_path,
                "config_fingerprint": run.config_fingerprint,
                "created_at": _iso(run.created_at),
                "findings_count": run.findings_count,
                "controls": json.loads(run.controls_json),
                "waiver": effective["waiver"],
                "waivers": effective["waivers"],
                "config_fingerprint_current": current_fingerprint,
                "recalculate_required": bool(
                    current_fingerprint
                    and run.config_fingerprint != current_fingerprint
                ),
            }
        )
    return payload


def gate_run_history(
    session: Session,
    project: Project,
    gate_key: str,
    *,
    current_fingerprint: str | None = None,
) -> list[dict[str, Any]]:
    """Historique des runs d'un gate, du plus récent au plus ancien."""
    runs = list(
        session.scalars(
            select(GateRun)
            .where(
                GateRun.project_id == project.id,
                GateRun.gate_key == gate_key,
            )
            .order_by(GateRun.id.desc())
        ).all()
    )
    payload: list[dict[str, Any]] = []
    for run in runs:
        effective = effective_for_run(session, run)
        payload.append(
            {
                "id": run.id,
                "gate_key": run.gate_key,
                "verdict": effective["verdict"],
                "base_verdict": run.verdict,
                "blocks": effective["blocks"],
                "reason": run.reason,
                "report_path": run.report_path,
                "config_fingerprint": run.config_fingerprint,
                "created_at": _iso(run.created_at),
                "findings_count": run.findings_count,
                "waiver": effective["waiver"],
                "waivers": effective["waivers"],
                "config_fingerprint_current": current_fingerprint,
                "recalculate_required": bool(
                    current_fingerprint
                    and run.config_fingerprint != current_fingerprint
                ),
            }
        )
    return payload
