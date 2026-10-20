"""Gate de couverture : Cobertura, lcov, JaCoCo et trois seuils."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import GateRun, Project
from ..paths import PathSecurityError, resolve_within
from .gate_config import coverage_thresholds
from .gates import (
    ControlResult,
    Evidence,
    Finding,
    GateError,
    GateEvaluation,
    evaluate_gate,
    persist_gate_run,
)

COVERAGE_SUFFIXES = {".xml", ".info", ".lcov"}


@dataclass
class FileCoverage:
    """Couverture d'un fichier : numéro de ligne → nombre d'exécutions."""

    path: str
    lines: dict[int, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.lines)

    @property
    def covered(self) -> int:
        return sum(1 for hits in self.lines.values() if hits > 0)

    @property
    def percent(self) -> float:
        return round(self.covered * 100 / self.total, 2) if self.total else 0.0


@dataclass
class CoverageData:
    """Couverture agrégée de plusieurs preuves."""

    files: dict[str, FileCoverage] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(item.total for item in self.files.values())

    @property
    def covered(self) -> int:
        return sum(item.covered for item in self.files.values())

    @property
    def percent(self) -> float:
        return round(self.covered * 100 / self.total, 2) if self.total else 0.0

    def merge(self, other: CoverageData) -> None:
        for path, item in other.files.items():
            if path not in self.files:
                self.files[path] = FileCoverage(path=path, lines=dict(item.lines))
                continue
            target = self.files[path]
            for line, hits in item.lines.items():
                target.lines[line] = max(target.lines.get(line, 0), hits)
        for source in other.sources:
            if source not in self.sources:
                self.sources.append(source)


@dataclass(frozen=True)
class CoverageGateResult:
    """Résultat du gate de couverture."""

    evaluation: GateEvaluation
    run: GateRun
    coverage: CoverageData
    thresholds: dict[str, float]
    metrics: dict[str, Any]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _normalize_file(path: str, root: Path) -> str:
    raw = path.replace("\\", "/")
    if raw.startswith("./"):
        raw = raw[2:]
    candidate = Path(raw)
    if candidate.is_absolute():
        return _relative(candidate, root)
    return raw


def _int(value: str | None, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def parse_cobertura(path: Path, *, root: Path) -> CoverageData:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise GateError(f"Cobertura invalide : {path} : {exc}") from exc
    root_element = tree.getroot()
    if _local_name(root_element.tag) != "coverage":
        raise GateError(f"racine Cobertura attendue `coverage` : {path}")
    data = CoverageData(sources=[str(path)])
    for element in root_element.iter():
        if _local_name(element.tag) != "class":
            continue
        filename = element.attrib.get("filename")
        if not filename:
            continue
        lines: dict[int, int] = {}
        for child in element.iter():
            if _local_name(child.tag) != "line":
                continue
            number = _int(child.attrib.get("number"), -1)
            if number >= 0:
                lines[number] = max(lines.get(number, 0), _int(child.attrib.get("hits")))
        if lines:
            key = _normalize_file(filename, root)
            existing = data.files.get(key)
            if existing is None:
                data.files[key] = FileCoverage(path=key, lines=lines)
            else:
                for number, hits in lines.items():
                    existing.lines[number] = max(existing.lines.get(number, 0), hits)
    return data


def parse_lcov(path: Path, *, root: Path) -> CoverageData:
    data = CoverageData(sources=[str(path)])
    current: FileCoverage | None = None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise GateError(f"lcov illisible : {path} : {exc}") from exc
    for line in lines:
        if line.startswith("SF:"):
            filename = line[3:].strip()
            key = _normalize_file(filename, root)
            current = data.files.setdefault(key, FileCoverage(path=key))
        elif line.startswith("DA:") and current is not None:
            payload = line[3:].split(",", 1)
            if len(payload) != 2:
                continue
            number = _int(payload[0], -1)
            if number >= 0:
                current.lines[number] = max(
                    current.lines.get(number, 0),
                    _int(payload[1]),
                )
        elif line.startswith("end_of_record"):
            current = None
    return data


def parse_jacoco(path: Path, *, root: Path) -> CoverageData:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise GateError(f"JaCoCo invalide : {path} : {exc}") from exc
    root_element = tree.getroot()
    if _local_name(root_element.tag) != "report":
        raise GateError(f"racine JaCoCo attendue `report` : {path}")
    data = CoverageData(sources=[str(path)])
    for package in root_element.iter():
        if _local_name(package.tag) != "package":
            continue
        package_name = package.attrib.get("name", "").replace(".", "/")
        for sourcefile in package:
            if _local_name(sourcefile.tag) != "sourcefile":
                continue
            filename = sourcefile.attrib.get("name", "")
            if not filename:
                continue
            key = f"{package_name}/{filename}".lstrip("/")
            item = data.files.setdefault(key, FileCoverage(path=key))
            for child in sourcefile:
                if _local_name(child.tag) != "line":
                    continue
                number = _int(child.attrib.get("nr"), -1)
                covered = _int(child.attrib.get("ci"))
                if number >= 0:
                    item.lines[number] = max(item.lines.get(number, 0), covered)
    return data


def collect_coverage_paths(
    *,
    root: str | Path | None = None,
    evidence_paths: Sequence[str | Path] | None = None,
    evidence_root: str | Path | None = None,
) -> list[Path]:
    root_path = Path(root or Path.cwd()).resolve()
    base = Path(evidence_root or root_path)
    if evidence_paths:
        candidates = [Path(item) for item in evidence_paths]
    else:
        candidates = sorted(
            path
            for path in (base / "reports" / "coverage").glob("*")
            if path.suffix.lower() in COVERAGE_SUFFIXES
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


def _format_for(path: Path) -> str:
    if path.suffix.lower() in {".info", ".lcov"}:
        return "lcov"
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise GateError(f"preuve de couverture illisible : {path} : {exc}") from exc
    tag = _local_name(root.tag)
    if tag == "coverage":
        return "cobertura"
    if tag == "report":
        return "jacoco"
    raise GateError(f"format de couverture non reconnu : {path} ({tag})")


def parse_coverage(path: str | Path, *, root: str | Path | None = None) -> CoverageData:
    root_path = Path(root or Path.cwd()).resolve()
    try:
        source = resolve_within(root_path, path)
    except (PathSecurityError, FileNotFoundError, OSError) as exc:
        raise GateError(f"preuve de couverture illisible : {path} : {exc}") from exc
    fmt = _format_for(source)
    if fmt == "cobertura":
        return parse_cobertura(source, root=root_path)
    if fmt == "lcov":
        return parse_lcov(source, root=root_path)
    return parse_jacoco(source, root=root_path)


def _thresholds(
    config: Mapping[str, Any] | None,
    overrides: Mapping[str, float] | None,
) -> dict[str, float]:
    try:
        return coverage_thresholds(config, overrides)
    except ValueError as exc:
        raise GateError(str(exc)) from exc


def _changed_metric(
    data: CoverageData,
    changed_lines: Mapping[str, Sequence[int]] | None,
    changed_files: Sequence[str],
) -> dict[str, Any] | None:
    if changed_lines is None:
        if not changed_files:
            return None
        selected: dict[str, Sequence[int]] = {}
        for candidate in changed_files:
            normalized = candidate.replace("\\", "/").lstrip("./")
            match = next(
                (path for path in data.files if path == normalized or path.endswith("/" + normalized)),
                None,
            )
            if match is not None:
                selected[match] = sorted(data.files[match].lines)
        changed_lines = selected
    if not changed_lines:
        return None
    total = 0
    covered = 0
    for filename, lines in changed_lines.items():
        normalized = filename.replace("\\", "/").lstrip("./")
        match = next(
            (path for path in data.files if path == normalized or path.endswith("/" + normalized)),
            None,
        )
        item = data.files[match] if match is not None else None
        for line in lines:
            total += 1
            if item is not None and item.lines.get(int(line), 0) > 0:
                covered += 1
    if total == 0:
        return None
    return {
        "covered": covered,
        "total": total,
        "percent": round(covered * 100 / total, 2),
    }


def _files_below(data: CoverageData, threshold: float) -> list[FileCoverage]:
    return [
        item
        for item in sorted(data.files.values(), key=lambda file: file.path)
        if item.total > 0 and item.percent < threshold
    ]


def run_coverage_gate(
    session: Session,
    project: Project,
    *,
    evidence_paths: Sequence[str | Path] | None = None,
    evidence_root: str | Path | None = None,
    changed_lines: Mapping[str, Sequence[int]] | None = None,
    changed_files: Sequence[str] = (),
    thresholds: Mapping[str, float] | None = None,
    reports_dir: str | Path = "reports/gates",
    root: str | Path | None = None,
    config: Mapping[str, Any] | None = None,
    languages: Mapping[str, Any] | None = None,
) -> CoverageGateResult:
    """Évalue les trois seuils de couverture et persiste le gate."""
    root_path = Path(root or Path.cwd()).resolve()
    paths = collect_coverage_paths(
        root=root_path,
        evidence_paths=evidence_paths,
        evidence_root=evidence_root,
    )
    coverage = CoverageData()
    for path in paths:
        coverage.merge(parse_coverage(path, root=root_path))
    values = _thresholds(config, thresholds)
    evidence = tuple(
        Evidence(path=_relative(path, root_path), kind="coverage", description=path.name)
        for path in paths
    )
    language_defs = languages
    if language_defs is None and isinstance(config, Mapping):
        quality = config.get("quality")
        if isinstance(quality, Mapping) and isinstance(quality.get("languages"), Mapping):
            language_defs = quality["languages"]
    tiers: list[int] = []
    if isinstance(language_defs, Mapping):
        for definition in language_defs.values():
            if isinstance(definition, Mapping) and definition.get("tier") is not None:
                try:
                    tiers.append(int(definition["tier"]))
                except (TypeError, ValueError):
                    continue
    if tiers and 1 not in tiers:
        control = ControlResult(
            key="coverage",
            verdict="not_applicable",
            expected=False,
            reason=(
                "aucun langage de tier 1 : la couverture n'est pas applicable "
                f"(tiers détectés : {sorted(set(tiers))})"
            ),
            evidence=evidence,
            details={"tiers": sorted(set(tiers)), "thresholds": values},
        )
        evaluation = evaluate_gate(
            "coverage",
            [control],
            gate_name="Couverture",
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
        return CoverageGateResult(
            evaluation=evaluation,
            run=run,
            coverage=coverage,
            thresholds=values,
            metrics={"tiers": sorted(set(tiers))},
        )
    if not paths:
        control = ControlResult(
            key="coverage",
            verdict="not_run",
            reason="aucune preuve de couverture trouvée dans reports/coverage/",
            evidence=(),
            details={"thresholds": values},
        )
        evaluation = evaluate_gate(
            "coverage",
            [control],
            gate_name="Couverture",
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
        return CoverageGateResult(
            evaluation=evaluation,
            run=run,
            coverage=coverage,
            thresholds=values,
            metrics={},
        )

    global_metric = {
        "covered": coverage.covered,
        "total": coverage.total,
        "percent": coverage.percent,
        "threshold": values["global"],
    }
    below = _files_below(coverage, values["file"])
    changed = _changed_metric(coverage, changed_lines, changed_files)
    findings: list[Finding] = []
    global_verdict = "pass"
    if coverage.total == 0:
        global_verdict = "not_run"
        findings.append(
            Finding(
                key="coverage:global",
                severity="error",
                message="aucune ligne exécutable dans les preuves de couverture",
            )
        )
    elif coverage.percent < values["global"]:
        global_verdict = "fail"
        findings.append(
            Finding(
                key="coverage:global",
                severity="error",
                message=(
                    f"couverture globale {coverage.percent}% < seuil {values['global']}%"
                ),
            )
        )

    changed_verdict = "not_applicable"
    if changed is not None:
        changed_verdict = "pass"
        if changed["percent"] < values["changed"]:
            changed_verdict = "fail"
            findings.append(
                Finding(
                    key="coverage:changed",
                    severity="error",
                    message=(
                        f"couverture des lignes modifiées {changed['percent']}% "
                        f"< seuil {values['changed']}%"
                    ),
                )
            )

    file_verdict = "pass"
    if below:
        file_verdict = "fail"
        for item in below:
            findings.append(
                Finding(
                    key=f"coverage:file:{item.path}",
                    severity="error",
                    message=f"couverture du fichier {item.percent}% < seuil {values['file']}%",
                    file=item.path,
                )
            )

    controls = [
        ControlResult(
            key="global",
            verdict=global_verdict,
            reason=f"{coverage.percent}% ({coverage.covered}/{coverage.total})",
            evidence=evidence,
            findings=tuple(findings),
            details={"metric": global_metric, "threshold": values["global"]},
        ),
        ControlResult(
            key="changed",
            verdict=changed_verdict,
            expected=changed is not None,
            reason=(
                f"{changed['percent']}% ({changed['covered']}/{changed['total']})"
                if changed is not None
                else "aucune ligne modifiée fournie"
            ),
            evidence=evidence,
            details={"metric": changed, "threshold": values["changed"]},
        ),
        ControlResult(
            key="file",
            verdict=file_verdict,
            reason=(
                f"{len(below)} fichier(s) sous le seuil {values['file']}%"
                if below
                else f"tous les fichiers respectent {values['file']}%"
            ),
            evidence=evidence,
            details={
                "threshold": values["file"],
                "files_below": [item.path for item in below],
                "files": {
                    item.path: item.percent for item in coverage.files.values()
                },
            },
        ),
    ]
    evaluation = evaluate_gate(
        "coverage",
        controls,
        gate_name="Couverture",
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
    metrics = {
        "global": global_metric,
        "changed": changed,
        "file": {
            "threshold": values["file"],
            "below": [item.path for item in below],
        },
    }
    return CoverageGateResult(
        evaluation=evaluation,
        run=run,
        coverage=coverage,
        thresholds=values,
        metrics=metrics,
    )
