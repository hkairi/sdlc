"""Matrice de traçabilité exigence → scénario → test → tâche.

Les exigences et scénarios sont lus dans les specs OpenSpec. Les liens vers
les tests et les tâches sont déclarés dans un manifeste YAML explicite, ce qui
rend la matrice auditable et reproductible sans appariement heuristique fragile.
"""

from __future__ import annotations

import ast
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..paths import resolve_within
from .suivi_ingestion import parse_tasks_md_file


class TraceabilityError(RuntimeError):
    """Erreur de lecture ou de validation de la matrice."""


@dataclass(frozen=True)
class TestRef:
    path: str
    name: str


@dataclass(frozen=True)
class TaskRef:
    key: str
    title: str
    checked: bool
    lot: str | None
    source: str


@dataclass(frozen=True)
class ScenarioTrace:
    title: str
    text: str
    tests: tuple[TestRef, ...] = ()


@dataclass(frozen=True)
class RequirementTrace:
    id: str
    spec: str
    title: str
    text: str
    scenarios: tuple[ScenarioTrace, ...]
    tests: tuple[TestRef, ...]
    tasks: tuple[TaskRef, ...]
    has_tests: bool


@dataclass(frozen=True)
class TraceabilityMatrix:
    requirements: tuple[RequirementTrace, ...]
    unverified_requirements: tuple[str, ...]
    stats: Mapping[str, int]


@dataclass(frozen=True)
class ManifestEntry:
    tests: tuple[str, ...]
    tasks: tuple[str, ...]
    scenarios: Mapping[str, tuple[str, ...]]


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "exigence"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TraceabilityError(f"fichier illisible : {path} : {exc}") from exc


def _parse_spec(path: Path) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    scenario: dict[str, Any] | None = None
    for line in _read_text(path).splitlines():
        requirement_match = re.match(r"^### Requirement:\s*(.+)$", line)
        if requirement_match:
            current = {
                "title": requirement_match.group(1).strip(),
                "lines": [],
                "scenarios": [],
            }
            requirements.append(current)
            scenario = None
            continue
        scenario_match = re.match(r"^#### Scenario:\s*(.+)$", line)
        if scenario_match and current is not None:
            scenario = {"title": scenario_match.group(1).strip(), "lines": []}
            current["scenarios"].append(scenario)
            continue
        if current is None:
            continue
        if scenario is not None:
            scenario["lines"].append(line)
        else:
            current["lines"].append(line)
    if not requirements:
        raise TraceabilityError(f"aucune exigence dans {path}")
    return requirements


def _test_refs(path: Path, root: Path) -> tuple[TestRef, ...]:
    text = _read_text(path)
    relative = _relative(path, root)
    refs: list[TestRef] = []
    if path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx"}:
        pattern = re.compile(
            r"""\b(?:it|test)\(\s*(?:"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)')"""
        )
        for match in pattern.finditer(text):
            name = match.group(1) if match.group(1) is not None else match.group(2)
            refs.append(TestRef(path=relative, name=name or ""))
        if not refs:
            refs.append(TestRef(path=relative, name=""))
        return tuple(refs)
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise TraceabilityError(f"fichier de test illisible : {path} : {exc}") from exc

    def add(name: str) -> None:
        refs.append(TestRef(path=relative, name=name))

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith(
                    "test_"
                ):
                    add(f"{node.name}.{child.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            add(node.name)
    if not refs:
        refs.append(TestRef(path=relative, name=""))
    return tuple(refs)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _load_manifest(path: Path) -> dict[str, ManifestEntry]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TraceabilityError(f"manifeste de traçabilité illisible : {path} : {exc}") from exc
    if not isinstance(raw, Mapping):
        raise TraceabilityError("le manifeste doit être un objet YAML")
    requirements = raw.get("requirements")
    if not isinstance(requirements, Mapping):
        raise TraceabilityError("le manifeste doit contenir `requirements`")
    entries: dict[str, ManifestEntry] = {}
    for title, raw_entry in requirements.items():
        if not isinstance(title, str) or not title.strip():
            raise TraceabilityError("titre d'exigence invalide dans le manifeste")
        if raw_entry is None:
            raw_entry = {}
        if not isinstance(raw_entry, Mapping):
            raise TraceabilityError(f"entrée de manifeste invalide pour {title}")
        tests_raw = raw_entry.get("tests", [])
        tasks_raw = raw_entry.get("tasks", [])
        scenarios_raw = raw_entry.get("scenarios", {})
        if not isinstance(tests_raw, list) or not all(isinstance(item, str) for item in tests_raw):
            raise TraceabilityError(f"`tests` invalide pour {title}")
        if not isinstance(tasks_raw, list) or not all(isinstance(item, str) for item in tasks_raw):
            raise TraceabilityError(f"`tasks` invalide pour {title}")
        if not isinstance(scenarios_raw, Mapping):
            raise TraceabilityError(f"`scenarios` invalide pour {title}")
        scenarios: dict[str, tuple[str, ...]] = {}
        for scenario_title, refs in scenarios_raw.items():
            if not isinstance(scenario_title, str) or not isinstance(refs, list):
                raise TraceabilityError(f"scénario invalide pour {title}")
            if not all(isinstance(item, str) for item in refs):
                raise TraceabilityError(f"références de test invalides pour {title}")
            scenarios[scenario_title] = tuple(refs)
        entries[title.strip()] = ManifestEntry(
            tests=tuple(tests_raw),
            tasks=tuple(tasks_raw),
            scenarios=scenarios,
        )
    return entries


def _task_refs(paths: Sequence[Path], root: Path) -> dict[str, TaskRef]:
    refs: dict[str, TaskRef] = {}
    for path in paths:
        parsed = parse_tasks_md_file(path)
        source = _relative(path, root)
        for task in parsed.tasks:
            if task.key in refs:
                raise TraceabilityError(
                    f"clé de tâche dupliquée {task.key} entre {refs[task.key].source} et {source}"
                )
            refs[task.key] = TaskRef(
                key=task.key,
                title=task.title,
                checked=task.checked,
                lot=task.lot,
                source=source,
            )
    return refs


def _resolve_test_ref(
    reference: str,
    root: Path,
    cache: dict[Path, tuple[TestRef, ...]],
) -> TestRef:
    if "::" not in reference:
        raise TraceabilityError(f"référence de test attendue `chemin::nom` : {reference}")
    raw_path, name = reference.split("::", 1)
    if not raw_path or not name:
        raise TraceabilityError(f"référence de test invalide : {reference}")
    path = resolve_within(root, raw_path)
    if path not in cache:
        cache[path] = _test_refs(path, root)
    for ref in cache[path]:
        if ref.name == name:
            return ref
    raise TraceabilityError(f"test introuvable : {reference}")


def build_traceability_matrix(
    *,
    spec_paths: Sequence[str | Path],
    tasks_paths: Sequence[str | Path],
    manifest_path: str | Path,
    root: str | Path | None = None,
) -> TraceabilityMatrix:
    """Construit la matrice depuis les specs, tasks.md et le manifeste."""
    root_path = Path(root or Path.cwd()).resolve()
    specs = sorted(Path(path).expanduser().resolve() for path in spec_paths)
    tasks = sorted(Path(path).expanduser().resolve() for path in tasks_paths)
    manifest = _load_manifest(Path(manifest_path).expanduser().resolve())
    task_refs = _task_refs(tasks, root_path)
    test_cache: dict[Path, tuple[TestRef, ...]] = {}

    known_titles = {
        requirement["title"]
        for spec in specs
        for requirement in _parse_spec(spec)
    }
    unknown = set(manifest) - known_titles
    if unknown:
        raise TraceabilityError(
            "exigences inconnues dans le manifeste : " + ", ".join(sorted(unknown))
        )

    requirements: list[RequirementTrace] = []
    used_ids: set[str] = set()
    for spec in specs:
        capability = spec.parent.name
        for raw_requirement in _parse_spec(spec):
            title = raw_requirement["title"]
            identifier = f"{capability}:{_slug(title)}"
            if identifier in used_ids:
                suffix = 2
                while f"{identifier}-{suffix}" in used_ids:
                    suffix += 1
                identifier = f"{identifier}-{suffix}"
            used_ids.add(identifier)
            entry = manifest.get(title, ManifestEntry((), (), {}))
            tests: list[TestRef] = []
            for reference in entry.tests:
                path = resolve_within(root_path, reference)
                cache_key = path
                if cache_key not in test_cache:
                    test_cache[cache_key] = _test_refs(path, root_path)
                tests.extend(test_cache[cache_key])
            scenario_traces: list[ScenarioTrace] = []
            for raw_scenario in raw_requirement["scenarios"]:
                scenario_title = raw_scenario["title"]
                scenario_tests: list[TestRef] = []
                for reference in entry.scenarios.get(scenario_title, ()):
                    scenario_tests.append(_resolve_test_ref(reference, root_path, test_cache))
                scenario_traces.append(
                    ScenarioTrace(
                        title=scenario_title,
                        text="\n".join(raw_scenario["lines"]).strip(),
                        tests=tuple(scenario_tests),
                    )
                )
                tests.extend(scenario_tests)
            requirement_tasks: list[TaskRef] = []
            for task_key in entry.tasks:
                task_ref = task_refs.get(task_key)
                if task_ref is None:
                    raise TraceabilityError(
                        f"tâche {task_key} introuvable pour l'exigence {title}"
                    )
                requirement_tasks.append(task_ref)
            unique_tests = tuple(dict.fromkeys(tests))
            unique_tasks = tuple({task.key: task for task in requirement_tasks}.values())
            requirements.append(
                RequirementTrace(
                    id=identifier,
                    spec=capability,
                    title=title,
                    text="\n".join(raw_requirement["lines"]).strip(),
                    scenarios=tuple(scenario_traces),
                    tests=unique_tests,
                    tasks=unique_tasks,
                    has_tests=bool(unique_tests),
                )
            )

    unverified = tuple(
        requirement.id for requirement in requirements if not requirement.has_tests
    )
    stats = {
        "requirements": len(requirements),
        "scenarios": sum(len(requirement.scenarios) for requirement in requirements),
        "tests": sum(len(requirement.tests) for requirement in requirements),
        "tasks": sum(len(requirement.tasks) for requirement in requirements),
        "covered_requirements": len(requirements) - len(unverified),
        "unverified_requirements": len(unverified),
    }
    return TraceabilityMatrix(
        requirements=tuple(requirements),
        unverified_requirements=unverified,
        stats=stats,
    )


def traceability_to_dict(matrix: TraceabilityMatrix) -> dict[str, Any]:
    """Sérialise la matrice pour l'API ou un export JSON."""
    return {
        "stats": dict(matrix.stats),
        "unverified_requirements": list(matrix.unverified_requirements),
        "requirements": [
            {
                "id": requirement.id,
                "spec": requirement.spec,
                "title": requirement.title,
                "text": requirement.text,
                "has_tests": requirement.has_tests,
                "scenarios": [
                    {
                        "title": scenario.title,
                        "text": scenario.text,
                        "tests": [
                            {"path": test.path, "name": test.name}
                            for test in scenario.tests
                        ],
                    }
                    for scenario in requirement.scenarios
                ],
                "tests": [
                    {"path": test.path, "name": test.name} for test in requirement.tests
                ],
                "tasks": [
                    {
                        "key": task.key,
                        "title": task.title,
                        "checked": task.checked,
                        "lot": task.lot,
                        "source": task.source,
                    }
                    for task in requirement.tasks
                ],
            }
            for requirement in matrix.requirements
        ],
    }
