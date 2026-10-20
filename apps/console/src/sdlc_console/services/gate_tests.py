"""Gate de tests : lecture JUnit, échecs, ignorés modifiés et quarantaine."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import GateRun, Project, utc_now
from ..paths import PathSecurityError, resolve_within
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
class TestCaseResult:
    """Résultat normalisé d'un cas JUnit."""

    key: str
    suite: str
    name: str
    status: str
    classname: str | None = None
    file: str | None = None
    line: int | None = None
    message: str | None = None
    duration: float | None = None
    source: str | None = None


@dataclass(frozen=True)
class QuarantineEntry:
    """Quarantaine d'un test, avec ticket et expiration."""

    test: str
    ticket: str
    expires_at: datetime
    reason: str | None = None
    owner: str | None = None

    def is_valid(self, now: datetime) -> bool:
        expires = (
            self.expires_at.replace(tzinfo=UTC)
            if self.expires_at.tzinfo is None
            else self.expires_at.astimezone(UTC)
        )
        return bool(self.test.strip() and self.ticket.strip() and expires > now)


@dataclass(frozen=True)
class TestsGateResult:
    """Résultat complet du gate de tests."""

    evaluation: GateEvaluation
    run: GateRun
    tests: tuple[TestCaseResult, ...]
    quarantined: tuple[str, ...] = field(default_factory=tuple)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _case_key(classname: str | None, name: str, suite: str) -> str:
    prefix = classname or suite or "tests"
    return f"{prefix}::{name}"


def _parse_case(case: ET.Element, suite: str, source: Path) -> TestCaseResult:
    name = case.attrib.get("name") or "(sans nom)"
    classname = case.attrib.get("classname")
    file_name = case.attrib.get("file")
    status = "pass"
    message: str | None = None
    line: int | None = None
    for child in list(case):
        tag = _local_name(child.tag)
        if tag in {"failure", "error"}:
            status = "fail"
            message = child.attrib.get("message") or (child.text or "").strip() or None
            if child.attrib.get("line"):
                try:
                    line = int(child.attrib["line"])
                except ValueError:
                    line = None
            break
        if tag == "skipped":
            status = "skipped"
            message = child.attrib.get("message") or (child.text or "").strip() or None
            break
    duration: float | None = None
    if case.attrib.get("time"):
        try:
            duration = float(case.attrib["time"])
        except ValueError:
            duration = None
    return TestCaseResult(
        key=_case_key(classname, name, suite),
        suite=suite,
        name=name,
        status=status,
        classname=classname,
        file=file_name,
        line=line,
        message=message,
        duration=duration,
        source=str(source),
    )


def parse_junit(path: str | Path, *, root: str | Path | None = None) -> tuple[TestCaseResult, ...]:
    """Lit un fichier JUnit XML et renvoie les cas normalisés."""
    root_path = Path(root or Path.cwd()).resolve()
    try:
        source = resolve_within(root_path, path)
    except (PathSecurityError, FileNotFoundError, OSError) as exc:
        raise GateError(f"preuve JUnit illisible : {path} : {exc}") from exc
    try:
        tree = ET.parse(source)
    except ET.ParseError as exc:
        raise GateError(f"JUnit XML invalide : {path} : {exc}") from exc
    tests: list[TestCaseResult] = []
    for element in tree.getroot().iter():
        if _local_name(element.tag) != "testcase":
            continue
        parent_suite = ""
        for candidate in tree.getroot().iter():
            if element in list(candidate):
                if _local_name(candidate.tag) == "testsuite":
                    parent_suite = candidate.attrib.get("name") or ""
                break
        tests.append(_parse_case(element, parent_suite, source))
    return tuple(tests)


def collect_junit_paths(
    *,
    root: str | Path | None = None,
    junit_paths: Sequence[str | Path] | None = None,
    evidence_root: str | Path | None = None,
) -> list[Path]:
    """Résout les preuves JUnit, ou utilise `reports/junit/*.xml` par défaut."""
    root_path = Path(root or Path.cwd()).resolve()
    base = Path(evidence_root or root_path)
    if junit_paths:
        candidates = [Path(item) for item in junit_paths]
    else:
        candidates = sorted((base / "reports" / "junit").glob("*.xml"))
    paths: list[Path] = []
    for candidate in candidates:
        try:
            path = resolve_within(root_path, candidate)
        except (PathSecurityError, FileNotFoundError, OSError):
            continue
        if path.is_file() and path not in paths:
            paths.append(path)
    return paths


def _matches_changed(test: TestCaseResult, changed_files: set[str]) -> bool:
    if not changed_files:
        return False
    candidates = {
        item.replace("\\", "/").lstrip("./").casefold()
        for item in changed_files
    }
    test_paths = set()
    if test.file:
        test_paths.add(test.file.replace("\\", "/").lstrip("./").casefold())
    if test.classname:
        test_paths.add(
            test.classname.replace(".", "/").replace("\\", "/").lstrip("./").casefold()
        )
    return any(
        candidate == test_path
        or candidate.endswith("/" + test_path)
        or candidate.startswith(test_path + ".")
        for candidate in candidates
        for test_path in test_paths
    )


def _quarantine_finding(
    entry: QuarantineEntry,
    *,
    now: datetime,
    expired: bool,
) -> Finding:
    state = "expirée" if expired else "active"
    return Finding(
        key=f"quarantine:{entry.test}",
        severity="warning" if not expired else "error",
        message=(
            f"Quarantaine {state} — ticket {entry.ticket} — expiration "
            f"{entry.expires_at.isoformat()}"
            + (f" — {entry.reason}" if entry.reason else "")
        ),
        evidence=None,
    )


def run_tests_gate(
    session: Session,
    project: Project,
    *,
    junit_paths: Sequence[str | Path] | None = None,
    changed_files: Sequence[str] = (),
    quarantine: Sequence[QuarantineEntry] = (),
    flaky_tests: Sequence[str] = (),
    reports_dir: str | Path = "reports/gates",
    root: str | Path | None = None,
    evidence_root: str | Path | None = None,
    config: Mapping[str, Any] | None = None,
) -> TestsGateResult:
    """Évalue le gate tests depuis les preuves JUnit et persiste le run."""
    root_path = Path(root or Path.cwd()).resolve()
    now = utc_now()
    paths = collect_junit_paths(
        root=root_path,
        junit_paths=junit_paths,
        evidence_root=evidence_root,
    )
    tests: list[TestCaseResult] = []
    for path in paths:
        tests.extend(parse_junit(path, root=root_path))
    evidence = tuple(
        Evidence(
            path=_relative(path, root_path),
            kind="junit",
            description=path.name,
        )
        for path in paths
    )
    if not paths:
        control = ControlResult(
            key="junit",
            verdict="not_run",
            reason="aucune preuve JUnit trouvée dans reports/junit/*.xml",
            evidence=(),
        )
        evaluation = evaluate_gate(
            "tests",
            [control],
            gate_name="Tests",
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
        return TestsGateResult(evaluation=evaluation, run=run, tests=())

    quarantine_by_test = {
        entry.test: entry
        for entry in quarantine
        if entry.is_valid(now)
    }
    expired_quarantine = {
        entry.test: entry
        for entry in quarantine
        if not entry.is_valid(now)
    }
    changed = {item for item in changed_files if item}
    findings: list[Finding] = []
    failed = 0
    skipped_modified = 0
    quarantined: list[str] = []
    for test in tests:
        if test.status == "fail":
            entry = quarantine_by_test.get(test.key)
            if entry is not None:
                quarantined.append(test.key)
                findings.append(
                    _quarantine_finding(entry, now=now, expired=False)
                )
                continue
            failed += 1
            findings.append(
                Finding(
                    key=test.key,
                    severity="critical",
                    message=test.message or "test en échec",
                    file=test.file or test.classname,
                    line=test.line,
                    evidence=_relative(Path(test.source), root_path) if test.source else None,
                )
            )
        elif test.status == "skipped" and _matches_changed(test, changed):
            skipped_modified += 1
            findings.append(
                Finding(
                    key=test.key,
                    severity="error",
                    message=(
                        "test ignoré sur du code modifié"
                        + (f" — {test.message}" if test.message else "")
                    ),
                    file=test.file or test.classname,
                    line=test.line,
                    evidence=_relative(Path(test.source), root_path) if test.source else None,
                )
            )
        elif test.status == "skipped":
            findings.append(
                Finding(
                    key=test.key,
                    severity="info",
                    message="test ignoré hors code modifié",
                    file=test.file or test.classname,
                    line=test.line,
                    evidence=_relative(Path(test.source), root_path) if test.source else None,
                )
            )
        elif test.key in flaky_tests and test.key not in quarantine_by_test:
            findings.append(
                Finding(
                    key=test.key,
                    severity="warning",
                    message="test instable sans quarantaine valide (ticket et expiration requis)",
                    file=test.file or test.classname,
                    line=test.line,
                    evidence=_relative(Path(test.source), root_path) if test.source else None,
                )
            )

    for test_key, entry in quarantine_by_test.items():
        if not any(
            finding.key == f"quarantine:{test_key}" for finding in findings
        ):
            findings.append(_quarantine_finding(entry, now=now, expired=False))

    for test_key, entry in expired_quarantine.items():
        if any(test.key == test_key and test.status == "fail" for test in tests):
            findings.append(_quarantine_finding(entry, now=now, expired=True))

    if failed or skipped_modified:
        verdict = "fail"
        reason = (
            f"{failed} test(s) en échec, {skipped_modified} test(s) ignoré(s) "
            "sur du code modifié"
        )
    elif quarantined:
        verdict = "warn"
        reason = f"{len(quarantined)} test(s) en quarantaine valide"
    elif any(finding.severity == "warning" for finding in findings):
        verdict = "warn"
        reason = "tests instables ou quarantaine à surveiller"
    else:
        verdict = "pass"
        reason = f"{len(tests)} test(s) exécuté(s), aucun échec bloquant"
    control = ControlResult(
        key="junit",
        verdict=verdict,
        reason=reason,
        evidence=evidence,
        findings=tuple(findings),
    )
    evaluation = evaluate_gate(
        "tests",
        [control],
        gate_name="Tests",
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
    return TestsGateResult(
        evaluation=evaluation,
        run=run,
        tests=tuple(tests),
        quarantined=tuple(quarantined),
    )
