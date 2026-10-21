"""Gate de sécurité : SARIF, secrets, conteneurs, IaC et SBOM."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import GateRun, Project
from ..paths import PathSecurityError, resolve_within
from .gate_config import security_config
from .gates import (
    ControlResult,
    Evidence,
    Finding,
    GateError,
    GateEvaluation,
    evaluate_gate,
    persist_gate_run,
)

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}
SECURITY_SUFFIXES = {".sarif", ".json"}


@dataclass(frozen=True)
class SecurityFinding:
    """Finding de sécurité normalisé depuis SARIF ou rapport de secrets."""

    key: str
    severity: str
    message: str
    category: str = "sast"
    reachable: bool = True
    file: str | None = None
    line: int | None = None
    rule_id: str | None = None
    fixed_version: str | None = None
    evidence: str | None = None


@dataclass(frozen=True)
class SbomInfo:
    """SBOM chargé, ses composants et ses licences."""

    path: str
    format: str
    components: int
    licenses: tuple[str, ...] = ()
    packages: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class SecurityGateResult:
    """Résultat du gate de sécurité."""

    evaluation: GateEvaluation
    run: GateRun
    findings: tuple[SecurityFinding, ...]
    sbom: SbomInfo | None


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _severity(value: Any, level: str | None = None) -> str:
    if isinstance(value, (int, float)):
        numeric_score = float(value)
        if numeric_score >= 9.0:
            return "critical"
        if numeric_score >= 7.0:
            return "high"
        if numeric_score >= 4.0:
            return "medium"
        return "low"
    text = str(value or "").strip().lower()
    text_score: float | None
    try:
        text_score = float(text)
    except ValueError:
        text_score = None
    if text_score is not None:
        if text_score >= 9.0:
            return "critical"
        if text_score >= 7.0:
            return "high"
        if text_score >= 4.0:
            return "medium"
        return "low"
    aliases = {
        "error": "high",
        "warning": "medium",
        "warn": "medium",
        "note": "low",
        "info": "low",
        "moderate": "medium",
        "important": "high",
        "blocker": "critical",
    }
    if text in SEVERITY_ORDER:
        return text
    if text in aliases:
        return aliases[text]
    if level:
        return aliases.get(level.lower(), "medium")
    return "medium"


def _reachable(result: dict[str, Any], properties: dict[str, Any]) -> bool:
    value = properties.get("reachable")
    if isinstance(value, bool):
        return value
    if properties.get("call_path") or result.get("codeFlows"):
        return True
    # Une vulnérabilité sans preuve d'inatteignabilité reste traitée comme
    # atteignable : on ne rend pas un gate vert par absence de donnée.
    return True


def _category(properties: dict[str, Any], rule: dict[str, Any]) -> str:
    raw = properties.get("category") or rule.get("properties", {}).get("category")
    if raw:
        return str(raw).lower()
    tags = properties.get("tags") or rule.get("properties", {}).get("tags") or []
    normalized = {str(tag).lower() for tag in tags}
    if "secret" in normalized or "secrets" in normalized:
        return "secret"
    if "container" in normalized or "image" in normalized:
        return "container"
    if normalized & {"iac", "infrastructure", "terraform", "kubernetes"}:
        return "iac"
    return "sast"


def _location(result: dict[str, Any]) -> tuple[str | None, int | None]:
    locations = result.get("locations")
    if not isinstance(locations, list) or not locations:
        return None, None
    physical = locations[0].get("physicalLocation") if isinstance(locations[0], dict) else None
    if not isinstance(physical, dict):
        return None, None
    artifact = physical.get("artifactLocation")
    region = physical.get("region")
    path = artifact.get("uri") if isinstance(artifact, dict) else None
    line = region.get("startLine") if isinstance(region, dict) else None
    try:
        line_number = int(line) if line is not None else None
    except (TypeError, ValueError):
        line_number = None
    return str(path) if path else None, line_number


def parse_sarif(path: str | Path, *, root: str | Path | None = None) -> tuple[SecurityFinding, ...]:
    """Lit un rapport SARIF et normalise les résultats."""
    root_path = Path(root or Path.cwd()).resolve()
    try:
        source = resolve_within(root_path, path)
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (PathSecurityError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise GateError(f"SARIF illisible : {path} : {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("runs"), list):
        raise GateError(f"SARIF sans liste `runs` : {path}")
    findings: list[SecurityFinding] = []
    for run in payload["runs"]:
        if not isinstance(run, dict):
            continue
        rules: dict[str, dict[str, Any]] = {}
        for rule in run.get("tool", {}).get("driver", {}).get("rules", []) or []:
            if isinstance(rule, dict) and rule.get("id"):
                rules[str(rule["id"])] = rule
        for result in run.get("results", []) or []:
            if not isinstance(result, dict):
                continue
            rule_id = str(result.get("ruleId") or result.get("rule", {}).get("id") or "unknown")
            rule = rules.get(rule_id, {})
            raw_properties = result.get("properties")
            result_props: dict[str, Any] = (
                raw_properties if isinstance(raw_properties, dict) else {}
            )
            properties: dict[str, Any] = {
                "category": result_props.get("category"),
                "reachable": result_props.get("reachable"),
                "severity": result_props.get("severity"),
                "tags": result_props.get("tags"),
                "fixed_version": result_props.get("fixed_version"),
                "call_path": result_props.get("call_path"),
            }
            raw_rule_props = rule.get("properties")
            rule_props: dict[str, Any] = (
                raw_rule_props if isinstance(raw_rule_props, dict) else {}
            )
            for key in ("category", "severity", "tags", "fixed_version"):
                if properties.get(key) is None:
                    properties[key] = rule_props.get(key)
            if properties.get("severity") is None:
                properties["severity"] = (
                    result_props.get("security-severity")
                    or result_props.get("securitySeverity")
                    or rule_props.get("security-severity")
                    or rule_props.get("securitySeverity")
                )
            level = result.get("level") or rule_props.get("level")
            severity = _severity(properties.get("severity"), level)
            category = _category(properties, rule)
            file_name, line = _location(result)
            message = ""
            raw_message = result.get("message")
            if isinstance(raw_message, dict):
                message = str(raw_message.get("text") or raw_message.get("markdown") or "")
            elif raw_message:
                message = str(raw_message)
            findings.append(
                SecurityFinding(
                    key=rule_id,
                    severity=severity,
                    message=message or rule_id,
                    category=category,
                    reachable=_reachable(result, properties),
                    file=file_name,
                    line=line,
                    rule_id=rule_id,
                    fixed_version=(
                        str(properties["fixed_version"])
                        if properties.get("fixed_version")
                        else None
                    ),
                    evidence=_relative(source, root_path),
                )
            )
    return tuple(findings)


def parse_secret_report(
    path: str | Path,
    *,
    root: str | Path | None = None,
) -> tuple[SecurityFinding, ...]:
    """Lit un rapport JSON de secrets (`findings` ou `secrets`)."""
    root_path = Path(root or Path.cwd()).resolve()
    try:
        source = resolve_within(root_path, path)
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (PathSecurityError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise GateError(f"rapport de secrets illisible : {path} : {exc}") from exc
    if isinstance(payload, dict):
        items = payload.get("findings") or payload.get("secrets") or payload.get("results") or []
    else:
        items = payload
    if not isinstance(items, list):
        raise GateError(f"rapport de secrets sans liste : {path}")
    findings: list[SecurityFinding] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or item.get("ruleId") or f"secret-{index + 1}")
        file_name = item.get("file") or item.get("path")
        line = item.get("line")
        try:
            line_number = int(line) if line is not None else None
        except (TypeError, ValueError):
            line_number = None
        findings.append(
            SecurityFinding(
                key=key,
                severity=_severity(item.get("severity"), "error"),
                message=str(item.get("message") or item.get("description") or "secret détecté"),
                category="secret",
                reachable=True,
                file=str(file_name) if file_name else None,
                line=line_number,
                evidence=_relative(source, root_path),
            )
        )
    return tuple(findings)


def parse_sbom(path: str | Path, *, root: str | Path | None = None) -> SbomInfo:
    """Lit un SBOM CycloneDX, SPDX ou générique."""
    root_path = Path(root or Path.cwd()).resolve()
    try:
        source = resolve_within(root_path, path)
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (PathSecurityError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise GateError(f"SBOM illisible : {path} : {exc}") from exc
    if not isinstance(payload, dict):
        raise GateError(f"SBOM invalide : {path}")
    if payload.get("bomFormat") == "CycloneDX" or isinstance(payload.get("components"), list):
        components = payload.get("components") or []
        licenses: set[str] = set()
        packages: list[dict[str, Any]] = []
        for component in components:
            if not isinstance(component, dict):
                continue
            package_licenses: list[str] = []
            raw_licenses = component.get("licenses")
            if isinstance(raw_licenses, list):
                for item in raw_licenses:
                    if not isinstance(item, dict):
                        continue
                    license_data = item.get("license")
                    if isinstance(license_data, dict):
                        value = license_data.get("id") or license_data.get("name")
                    else:
                        value = item.get("expression") or item.get("id") or item.get("name")
                    if value and str(value).upper() not in {"NOASSERTION", "NONE"}:
                        package_licenses.append(str(value))
                        licenses.add(str(value))
            packages.append(
                {
                    "name": str(component.get("name") or "inconnu"),
                    "version": str(component.get("version") or ""),
                    "licenses": package_licenses,
                }
            )
        return SbomInfo(
            path=_relative(source, root_path),
            format="cyclonedx",
            components=len(components),
            licenses=tuple(sorted(licenses)),
            packages=tuple(packages),
        )
    if payload.get("spdxVersion") or isinstance(payload.get("packages"), list):
        packages_raw = payload.get("packages") or []
        spdx_licenses: set[str] = set()
        spdx_packages: list[dict[str, Any]] = []
        for package in packages_raw:
            if not isinstance(package, dict):
                continue
            values = [
                str(package.get("licenseConcluded") or ""),
                str(package.get("licenseDeclared") or ""),
            ]
            package_licenses = [
                value
                for value in values
                if value and value.upper() not in {"NOASSERTION", "NONE"}
            ]
            spdx_licenses.update(package_licenses)
            spdx_packages.append(
                {
                    "name": str(package.get("name") or "inconnu"),
                    "version": str(package.get("versionInfo") or ""),
                    "licenses": package_licenses,
                }
            )
        return SbomInfo(
            path=_relative(source, root_path),
            format="spdx",
            components=len(packages_raw),
            licenses=tuple(sorted(spdx_licenses)),
            packages=tuple(spdx_packages),
        )
    return SbomInfo(path=_relative(source, root_path), format="unknown", components=0)


def collect_security_paths(
    *,
    root: str | Path | None = None,
    evidence_root: str | Path | None = None,
    sarif_paths: Sequence[str | Path] | None = None,
    secret_paths: Sequence[str | Path] | None = None,
    sbom_paths: Sequence[str | Path] | None = None,
) -> tuple[list[Path], list[Path], list[Path]]:
    root_path = Path(root or Path.cwd()).resolve()
    base = Path(evidence_root or root_path)
    security_dir = base / "reports" / "security"
    if sarif_paths is None:
        sarif_paths = sorted(security_dir.glob("*.sarif"))
    if secret_paths is None:
        secret_paths = sorted(
            path
            for path in security_dir.glob("*.json")
            if "secret" in path.name.lower()
        )
    if sbom_paths is None:
        sbom_paths = sorted(
            path
            for path in security_dir.glob("*.json")
            if any(token in path.name.lower() for token in ("sbom", "cdx", "spdx"))
        )

    def resolved(items: Sequence[str | Path]) -> list[Path]:
        result: list[Path] = []
        for item in items:
            try:
                path = resolve_within(root_path, item)
            except (PathSecurityError, FileNotFoundError, OSError):
                continue
            if path.is_file() and path not in result:
                result.append(path)
        return result

    return resolved(sarif_paths), resolved(secret_paths), resolved(sbom_paths)


def run_security_gate(
    session: Session,
    project: Project,
    *,
    sarif_paths: Sequence[str | Path] | None = None,
    secret_paths: Sequence[str | Path] | None = None,
    sbom_paths: Sequence[str | Path] | None = None,
    evidence_root: str | Path | None = None,
    reports_dir: str | Path = "reports/gates",
    root: str | Path | None = None,
    config: Mapping[str, Any] | None = None,
) -> SecurityGateResult:
    """Évalue le gate sécurité et persiste le rapport."""
    root_path = Path(root or Path.cwd()).resolve()
    resolved_sarif, resolved_secrets, resolved_sbom = collect_security_paths(
        root=root_path,
        evidence_root=evidence_root,
        sarif_paths=sarif_paths,
        secret_paths=secret_paths,
        sbom_paths=sbom_paths,
    )
    security_findings: list[SecurityFinding] = []
    for path in resolved_sarif:
        security_findings.extend(parse_sarif(path, root=root_path))
    for path in resolved_secrets:
        security_findings.extend(parse_secret_report(path, root=root_path))
    sbom = None
    if resolved_sbom:
        sbom = parse_sbom(resolved_sbom[0], root=root_path)

    evidence = tuple(
        [
            Evidence(
                path=_relative(path, root_path),
                kind="sarif",
                description=path.name,
            )
            for path in resolved_sarif
        ]
        + [
            Evidence(
                path=_relative(path, root_path),
                kind="secrets",
                description=path.name,
            )
            for path in resolved_secrets
        ]
        + [
            Evidence(
                path=_relative(path, root_path),
                kind="sbom",
                description=path.name,
            )
            for path in resolved_sbom
        ]
    )
    if not resolved_sarif and not resolved_secrets:
        control = ControlResult(
            key="security",
            verdict="not_run",
            reason=(
                "aucune preuve d'analyse de sécurité (SARIF ou secrets) ; "
                "un SBOM seul ne suffit pas"
                if resolved_sbom
                else "aucune preuve de sécurité dans reports/security/"
            ),
            evidence=evidence,
        )
        evaluation = evaluate_gate(
            "security",
            [control],
            gate_name="Sécurité",
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
        return SecurityGateResult(
            evaluation=evaluation,
            run=run,
            findings=(),
            sbom=None,
        )

    vulnerabilities = [
        finding for finding in security_findings if finding.category != "secret"
    ]
    secrets = [finding for finding in security_findings if finding.category == "secret"]
    security_settings = security_config(config)
    block_on = set(security_settings["block_on"])
    blocking = [
        finding
        for finding in vulnerabilities
        if finding.severity in block_on
        and (finding.reachable or not security_settings["reachability"])
    ]
    warnings = [
        finding
        for finding in vulnerabilities
        if finding.severity == "medium"
        or (finding.severity in block_on and not finding.reachable)
    ]
    if secrets:
        secret_verdict = "fail"
    elif resolved_secrets or resolved_sarif:
        secret_verdict = "pass"
    else:
        secret_verdict = "not_applicable"

    vulnerability_verdict = "pass"
    if blocking:
        vulnerability_verdict = "fail"
    elif warnings:
        vulnerability_verdict = "warn"
    elif not resolved_sarif:
        vulnerability_verdict = "not_applicable"

    sbom_verdict = "warn"
    sbom_reason = "SBOM absent"
    if sbom is not None:
        sbom_verdict = "pass" if sbom.components > 0 else "warn"
        sbom_reason = f"SBOM {sbom.format} — {sbom.components} composant(s)"

    vulnerability_findings: list[Finding] = []
    for item in blocking:
        vulnerability_findings.append(
            Finding(
                key=item.key,
                severity="critical" if item.severity == "critical" else "error",
                message=(
                    f"{item.message} — atteignable"
                    + (f" — correctif {item.fixed_version}" if item.fixed_version else "")
                ),
                file=item.file,
                line=item.line,
                evidence=item.evidence,
            )
        )
    for item in warnings:
        vulnerability_findings.append(
            Finding(
                key=item.key,
                severity="warning",
                message=f"{item.message} — non atteignable ou risque modéré",
                file=item.file,
                line=item.line,
                evidence=item.evidence,
            )
        )
    secret_findings = [
        Finding(
            key=item.key,
            severity="critical",
            message=item.message or "secret détecté",
            file=item.file,
            line=item.line,
            evidence=item.evidence,
        )
        for item in secrets
    ]
    sbom_findings: list[Finding] = []
    if sbom is None:
        sbom_findings.append(
            Finding(
                key="sbom:missing",
                severity="warning",
                message="SBOM absent : le gate sécurité ne peut pas être vert sans inventaire",
            )
        )
    elif sbom.components == 0:
        sbom_findings.append(
            Finding(
                key="sbom:empty",
                severity="warning",
                message="SBOM sans composant",
            )
        )

    controls = [
        ControlResult(
            key="vulnerabilities",
            verdict=vulnerability_verdict,
            expected=bool(resolved_sarif),
            reason=(
                f"{len(blocking)} bloquante(s), {len(warnings)} non atteignable(s)"
                if resolved_sarif
                else "aucun SARIF fourni"
            ),
            evidence=evidence,
            findings=tuple(vulnerability_findings),
            details={
                "blocking": len(blocking),
                "warnings": len(warnings),
                "categories": sorted({item.category for item in vulnerabilities}),
            },
        ),
        ControlResult(
            key="secrets",
            verdict=secret_verdict,
            expected=bool(resolved_secrets),
            reason=(
                f"{len(secrets)} secret(s) détecté(s)"
                if secrets
                else "aucun secret détecté"
            ),
            evidence=evidence,
            findings=tuple(secret_findings),
        ),
        ControlResult(
            key="sbom",
            verdict=sbom_verdict,
            expected=False,
            reason=sbom_reason,
            evidence=evidence,
            findings=tuple(sbom_findings),
            details={
                "format": sbom.format if sbom else None,
                "components": sbom.components if sbom else 0,
            },
        ),
    ]
    evaluation = evaluate_gate(
        "security",
        controls,
        gate_name="Sécurité",
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
    return SecurityGateResult(
        evaluation=evaluation,
        run=run,
        findings=tuple(security_findings),
        sbom=sbom,
    )
