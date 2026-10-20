"""Gate des langages : détection, adaptateurs et contrôles attendus par tier."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import GateRun, Project
from ..paths import PathSecurityError, resolve_within
from .gates import (
    ControlResult,
    Evidence,
    Finding,
    GateEvaluation,
    evaluate_gate,
    persist_gate_run,
)

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".sql": "sql",
    ".sh": "bash",
    ".vue": "vue",
}
TIER_CONTROLS = {
    1: ("tests", "coverage", "sca", "sast", "performance", "data"),
    2: ("tests", "sca"),
    3: (),
}


@dataclass(frozen=True)
class LanguageSupport:
    """Langage détecté et support déclaré."""

    language: str
    adapter: str | None
    tier: int | None
    supported: bool
    expected_controls: tuple[str, ...]
    files: tuple[str, ...]


@dataclass(frozen=True)
class LanguagesGateResult:
    """Résultat du gate des langages."""

    evaluation: GateEvaluation
    run: GateRun
    languages: tuple[LanguageSupport, ...]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def detect_languages(
    *,
    root: str | Path | None = None,
    paths: Sequence[str | Path] | None = None,
) -> dict[str, list[Path]]:
    """Détecte les langages par extension sans parcourir les dépendances."""
    root_path = Path(root or Path.cwd()).resolve()
    detected: dict[str, list[Path]] = {}
    if paths is not None:
        candidates = []
        for item in paths:
            try:
                candidate = resolve_within(root_path, item)
            except (PathSecurityError, FileNotFoundError, OSError):
                continue
            if candidate.is_file():
                candidates.append(candidate)
    else:
        candidates = [
            path
            for path in root_path.rglob("*")
            if path.is_file()
            and not any(
                part in {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}
                for part in path.parts
            )
        ]
    for path in candidates:
        language = LANGUAGE_EXTENSIONS.get(path.suffix.lower())
        if language is None:
            continue
        detected.setdefault(language, []).append(path)
    return detected


def language_support(
    detected: Mapping[str, Sequence[str | Path]],
    *,
    config: Mapping[str, Any] | None = None,
    root: str | Path | None = None,
) -> tuple[LanguageSupport, ...]:
    root_path = Path(root or Path.cwd()).resolve()
    quality = config.get("quality") if isinstance(config, Mapping) else None
    declared = quality.get("languages") if isinstance(quality, Mapping) else None
    declared = declared if isinstance(declared, Mapping) else {}
    supports: list[LanguageSupport] = []
    for name in sorted(detected):
        definition = declared.get(name)
        adapter = None
        tier = None
        if isinstance(definition, Mapping):
            adapter = str(definition["adapter"]) if definition.get("adapter") else None
            raw_tier = definition.get("tier")
            try:
                tier = int(raw_tier) if raw_tier is not None else None
            except (TypeError, ValueError):
                tier = None
        supported = bool(adapter and tier in {1, 2})
        supports.append(
            LanguageSupport(
                language=name,
                adapter=adapter,
                tier=tier,
                supported=supported,
                expected_controls=TIER_CONTROLS.get(tier or 0, ()),
                files=tuple(_relative(Path(item), root_path) for item in detected[name]),
            )
        )
    return tuple(supports)


def run_languages_gate(
    session: Session,
    project: Project,
    *,
    detected: Mapping[str, Sequence[str | Path]] | None = None,
    source_paths: Sequence[str | Path] | None = None,
    config: Mapping[str, Any] | None = None,
    evidence_paths: Sequence[str | Path] | None = None,
    reports_dir: str | Path = "reports/gates",
    root: str | Path | None = None,
) -> LanguagesGateResult:
    """Évalue le gate des langages et persiste le rapport."""
    root_path = Path(root or Path.cwd()).resolve()
    found = (
        dict(detected)
        if detected is not None
        else detect_languages(root=root_path, paths=source_paths)
    )
    supports = language_support(found, config=config, root=root_path)
    evidence_paths_list: list[Path] = []
    for item in evidence_paths or []:
        try:
            path = resolve_within(root_path, item)
        except (PathSecurityError, FileNotFoundError, OSError):
            continue
        if path.is_file():
            evidence_paths_list.append(path)
    for support in supports:
        for file_name in support.files:
            try:
                path = resolve_within(root_path, file_name)
            except (PathSecurityError, FileNotFoundError, OSError):
                continue
            if path.is_file() and path not in evidence_paths_list:
                evidence_paths_list.append(path)
    if not supports:
        control = ControlResult(
            key="languages",
            verdict="not_run",
            reason="aucun langage détecté",
        )
        evaluation = evaluate_gate(
            "languages",
            [control],
            gate_name="Langages",
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
        return LanguagesGateResult(evaluation, run, ())

    evidence = tuple(
        Evidence(path=_relative(path, root_path), kind="source", description=path.name)
        for path in evidence_paths_list
    )
    unsupported = [item for item in supports if not item.supported]
    findings = [
        Finding(
            key=f"unsupported_language:{item.language}",
            severity="error",
            message=(
                f"langage {item.language} sans adaptateur"
                if item.adapter is None
                else f"langage {item.language} au tier non supporté ({item.tier})"
            ),
            file=item.files[0] if item.files else None,
        )
        for item in unsupported
    ]
    verdict = "fail" if unsupported else "pass"
    control = ControlResult(
        key="languages",
        verdict=verdict,
        expected=True,
        reason=(
            f"{len(unsupported)} langage(s) sans adaptateur"
            if unsupported
            else f"{len(supports)} langage(s) supporté(s)"
        ),
        evidence=evidence,
        findings=tuple(findings),
        details={
            "languages": [
                {
                    "language": item.language,
                    "adapter": item.adapter,
                    "tier": item.tier,
                    "supported": item.supported,
                    "expected_controls": list(item.expected_controls),
                    "files": list(item.files),
                }
                for item in supports
            ],
            "unsupported": [item.language for item in unsupported],
            "tier_controls": {str(key): list(value) for key, value in TIER_CONTROLS.items()},
        },
    )
    evaluation = evaluate_gate(
        "languages",
        [control],
        gate_name="Langages",
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
    return LanguagesGateResult(evaluation, run, supports)
