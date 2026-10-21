"""Ingestion de `docs/suivi/state.json` et de `openspec/changes/*/tasks.md`."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import Feature, IngestionRun, Project, Task, utc_now
from ..models import SuiviInconsistency as SuiviInconsistencyRecord
from ..paths import is_secret_path
from ..redaction import redact
from .features import FEATURE_STATUSES, TASK_STATUSES
from .providers.common import parse_datetime

TASK_LINE = re.compile(r"^- \[(?P<check>[ xX])\] (?P<key>[0-9]+(?:\.[0-9]+)+) (?P<body>.+)$")
SECTION_LINE = re.compile(r"^## (?P<number>[0-9]+)\.\s+(?P<title>.+)$")
DEPENDENCIES = re.compile(r"^\*\*\[[^\]]+\]\*\*\s*")

_STATUS_ALIASES = {
    "in_progress": "doing",
    "in-progress": "doing",
    "en_cours": "doing",
    "completed": "done",
    "complete": "done",
    "termine": "done",
    "terminé": "done",
    "pending": "todo",
    "a_faire": "todo",
    "à_faire": "todo",
    "canceled": "cancelled",
}


class SuiviIngestionError(RuntimeError):
    """Erreur de lecture ou de validation du suivi."""


@dataclass(frozen=True)
class ParsedStateTask:
    key: str
    title: str
    description: str | None
    lot: str | None
    status: str
    updated_at: datetime | None
    note: str | None
    executor_label: str | None
    reviewer_label: str | None
    files: tuple[str, ...]
    acceptance: str | None


@dataclass(frozen=True)
class ParsedStateFeature:
    key: str
    name: str
    status: str
    change: str | None
    objective: str | None
    tasks_file: str | None
    sources: Mapping[str, Any]
    phases: tuple[Mapping[str, Any], ...]
    spec_path: str | None
    delivered: bool
    blocked: bool
    version: str | None
    updated_at: datetime | None
    tasks: tuple[ParsedStateTask, ...]


@dataclass(frozen=True)
class ParsedMdTask:
    key: str
    checked: bool
    title: str
    description: str
    lot: str | None


@dataclass(frozen=True)
class ParsedTasksMd:
    path: Path
    change: str
    tasks: tuple[ParsedMdTask, ...]


@dataclass(frozen=True)
class SuiviInconsistency:
    feature_key: str
    task_key: str
    kind: str
    message: str
    state_status: str | None = None
    tasks_md_checked: bool | None = None


@dataclass(frozen=True)
class SuiviIngestionResult:
    run: IngestionRun
    stats: Mapping[str, Any]
    inconsistencies: tuple[SuiviInconsistency, ...] = field(default_factory=tuple)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "oui"}
    return False


def _normalize_status(value: Any, allowed: frozenset[str], label: str) -> str:
    raw = (_text(value) or "").strip().lower().replace("-", "_")
    status = _STATUS_ALIASES.get(raw, raw)
    if status not in allowed:
        raise SuiviIngestionError(f"statut de {label} invalide : {value!r}")
    return status


def _same_path(first: str | Path | None, second: str | Path) -> bool:
    if not first:
        return False
    left = Path(first).as_posix().strip("/")
    right = Path(second).as_posix().strip("/")
    return left == right or right.endswith(left) or left.endswith(right)


def _read_json(path: str | Path) -> Any:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise SuiviIngestionError(f"fichier de suivi introuvable : {source}")
    if is_secret_path(source):
        raise SuiviIngestionError(f"lecture de secret refusée : {source}")
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SuiviIngestionError(f"state.json invalide : {source} : {exc}") from exc


def parse_state_file(path: str | Path) -> tuple[ParsedStateFeature, ...]:
    """Analyse `state.json` sans écrire en base."""
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise SuiviIngestionError("state.json doit être un objet JSON")
    features = payload.get("features")
    if not isinstance(features, list):
        raise SuiviIngestionError("state.json : liste `features` absente")
    file_updated = parse_datetime(payload.get("file_updated"))
    parsed: list[ParsedStateFeature] = []
    for index, raw_feature in enumerate(features):
        if not isinstance(raw_feature, Mapping):
            raise SuiviIngestionError(f"state.json : feature #{index + 1} invalide")
        key = _text(raw_feature.get("id") or raw_feature.get("key") or raw_feature.get("change"))
        if not key:
            raise SuiviIngestionError(f"state.json : feature #{index + 1} sans clé")
        tasks_raw = raw_feature.get("tasks")
        tasks: list[ParsedStateTask] = []
        if isinstance(tasks_raw, list):
            for task_index, raw_task in enumerate(tasks_raw):
                if not isinstance(raw_task, Mapping):
                    raise SuiviIngestionError(
                        f"state.json : tâche #{task_index + 1} invalide dans {key}"
                    )
                task_key = _text(raw_task.get("id") or raw_task.get("key"))
                if not task_key:
                    raise SuiviIngestionError(
                        f"state.json : tâche #{task_index + 1} sans clé dans {key}"
                    )
                text = _text(raw_task.get("text"))
                title = _text(raw_task.get("title")) or text or task_key
                files_raw = raw_task.get("files")
                files: tuple[str, ...] = ()
                if isinstance(files_raw, list):
                    files = tuple(str(item) for item in files_raw if item is not None)
                tasks.append(
                    ParsedStateTask(
                        key=task_key,
                        title=title,
                        description=text,
                        lot=_text(raw_task.get("lot")),
                        status=_normalize_status(
                            raw_task.get("status", "todo"),
                            TASK_STATUSES,
                            "tâche",
                        ),
                        updated_at=parse_datetime(raw_task.get("updated")),
                        note=_text(raw_task.get("note")),
                        executor_label=_text(raw_task.get("executor")),
                        reviewer_label=_text(raw_task.get("reviewer")),
                        files=files,
                        acceptance=_text(raw_task.get("acceptance")),
                    )
                )
        sources_raw = raw_feature.get("sources")
        sources: Mapping[str, Any] = sources_raw if isinstance(sources_raw, Mapping) else {}
        phases_raw = raw_feature.get("phases")
        phases: tuple[Mapping[str, Any], ...] = ()
        if isinstance(phases_raw, list):
            phases = tuple(item for item in phases_raw if isinstance(item, Mapping))
        delivered = _bool(raw_feature.get("delivered"))
        blocked = _bool(raw_feature.get("blocked"))
        statuses = [task.status for task in tasks]
        explicit_status = _text(raw_feature.get("status"))
        if explicit_status:
            status = _normalize_status(explicit_status, FEATURE_STATUSES, "feature")
        elif blocked or "blocked" in statuses:
            status = "blocked"
        elif delivered or (statuses and all(item == "done" for item in statuses)):
            status = "done"
        elif any(item in {"doing", "done"} for item in statuses):
            status = "doing"
        else:
            status = "todo"
        spec_path = (
            _text(sources.get("design"))
            or _text(sources.get("proposal"))
            or _text(raw_feature.get("tasks_file"))
        )
        parsed.append(
            ParsedStateFeature(
                key=key,
                name=_text(raw_feature.get("name")) or key,
                status=status,
                change=_text(raw_feature.get("change")),
                objective=_text(raw_feature.get("objective")),
                tasks_file=_text(raw_feature.get("tasks_file")),
                sources=sources,
                phases=phases,
                spec_path=spec_path,
                delivered=delivered,
                blocked=blocked,
                version=_text(raw_feature.get("version")),
                updated_at=file_updated,
                tasks=tuple(tasks),
            )
        )
    return tuple(parsed)


def parse_tasks_md_file(path: str | Path) -> ParsedTasksMd:
    """Analyse un `tasks.md` OpenSpec sans écrire en base."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise SuiviIngestionError(f"tasks.md introuvable : {source}")
    if is_secret_path(source):
        raise SuiviIngestionError(f"lecture de secret refusée : {source}")
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SuiviIngestionError(f"tasks.md illisible : {source} : {exc}") from exc
    section: str | None = None
    tasks: list[ParsedMdTask] = []
    for line in lines:
        section_match = SECTION_LINE.match(line)
        if section_match:
            section = f"L{section_match.group('number')}"
            continue
        task_match = TASK_LINE.match(line)
        if not task_match:
            continue
        body = DEPENDENCIES.sub("", task_match.group("body")).strip()
        tasks.append(
            ParsedMdTask(
                key=task_match.group("key"),
                checked=task_match.group("check").lower() == "x",
                title=body,
                description=body,
                lot=section,
            )
        )
    if not tasks:
        raise SuiviIngestionError(f"tasks.md sans tâche : {source}")
    return ParsedTasksMd(path=source, change=source.parent.name, tasks=tuple(tasks))


def _upsert_feature(
    session: Session,
    project: Project,
    parsed: ParsedStateFeature,
) -> tuple[Feature, bool]:
    feature = session.scalar(
        select(Feature).where(Feature.project_id == project.id, Feature.key == parsed.key)
    )
    created = feature is None
    if feature is None:
        feature = Feature(
            project_id=project.id,
            key=parsed.key,
            name=parsed.name,
            status=parsed.status,
            updated_at=parsed.updated_at or utc_now(),
        )
        session.add(feature)
        session.flush()
    feature.name = parsed.name
    feature.status = parsed.status
    feature.change = parsed.change
    feature.objective = parsed.objective
    feature.tasks_file = parsed.tasks_file
    feature.sources_json = json.dumps(dict(parsed.sources), sort_keys=True, ensure_ascii=False)
    feature.phases_json = json.dumps(
        [dict(phase) for phase in parsed.phases],
        sort_keys=True,
        ensure_ascii=False,
    )
    feature.spec_path = parsed.spec_path
    feature.delivered = parsed.delivered
    feature.blocked = parsed.blocked
    feature.version = parsed.version
    if parsed.updated_at is not None:
        feature.updated_at = parsed.updated_at
    return feature, created


def _upsert_state_task(
    session: Session,
    feature: Feature,
    parsed: ParsedStateTask,
) -> tuple[Task, bool]:
    task = session.scalar(
        select(Task).where(Task.feature_id == feature.id, Task.key == parsed.key)
    )
    created = task is None
    if task is None:
        task = Task(
            feature_id=feature.id,
            key=parsed.key,
            title=parsed.title,
            status=parsed.status,
            updated_at=parsed.updated_at or utc_now(),
        )
        session.add(task)
        session.flush()
    task.title = parsed.title
    task.description = parsed.description
    task.lot = parsed.lot
    task.status = parsed.status
    task.executor_label = parsed.executor_label
    task.reviewer_label = parsed.reviewer_label
    task.files_json = json.dumps(list(parsed.files), ensure_ascii=False)
    task.acceptance = parsed.acceptance
    task.note = parsed.note
    if parsed.updated_at is not None:
        task.updated_at = parsed.updated_at
    return task, created


def _feature_for_md(
    session: Session,
    project: Project,
    parsed: ParsedTasksMd,
    state_features: Mapping[str, ParsedStateFeature],
    features_by_key: dict[str, Feature],
) -> tuple[Feature, bool]:
    for parsed_feature in state_features.values():
        if (
            parsed_feature.change == parsed.change
            or parsed_feature.key == parsed.change
            or _same_path(parsed_feature.tasks_file, parsed.path)
        ):
            feature = features_by_key.get(parsed_feature.key)
            if feature is not None:
                return feature, False
    feature = session.scalar(
        select(Feature).where(
            Feature.project_id == project.id,
            (Feature.change == parsed.change) | (Feature.key == parsed.change),
        )
    )
    if feature is not None:
        return feature, False
    for candidate in features_by_key.values():
        if _same_path(candidate.tasks_file, parsed.path):
            return candidate, False
    checked = [task.checked for task in parsed.tasks]
    if all(checked):
        status = "done"
    elif any(checked):
        status = "doing"
    else:
        status = "todo"
    feature = Feature(
        project_id=project.id,
        key=parsed.change,
        name=parsed.change,
        status=status,
        change=parsed.change,
        tasks_file=str(parsed.path),
        sources_json=json.dumps({"tasks": str(parsed.path)}, ensure_ascii=False),
        updated_at=utc_now(),
    )
    session.add(feature)
    session.flush()
    features_by_key[feature.key] = feature
    return feature, True


def _upsert_md_task(
    session: Session,
    feature: Feature,
    parsed: ParsedMdTask,
) -> tuple[Task, bool]:
    task = session.scalar(
        select(Task).where(Task.feature_id == feature.id, Task.key == parsed.key)
    )
    if task is None:
        task = Task(
            feature_id=feature.id,
            key=parsed.key,
            title=parsed.title,
            description=parsed.description,
            lot=parsed.lot,
            status="done" if parsed.checked else "todo",
            files_json="[]",
            updated_at=utc_now(),
        )
        session.add(task)
        session.flush()
        return task, True
    task.description = parsed.description
    if parsed.lot is not None:
        task.lot = parsed.lot
    if not task.title:
        task.title = parsed.title
    return task, False


def _compare(
    state_tasks: Mapping[str, Mapping[str, str]],
    md_tasks: Mapping[str, Mapping[str, bool]],
) -> list[SuiviInconsistency]:
    inconsistencies: list[SuiviInconsistency] = []
    for feature_key in sorted(set(state_tasks) | set(md_tasks)):
        state_for_feature = state_tasks.get(feature_key, {})
        md_for_feature = md_tasks.get(feature_key, {})
        for task_key in sorted(set(state_for_feature) | set(md_for_feature)):
            state_status = state_for_feature.get(task_key)
            checked = md_for_feature.get(task_key)
            if state_status is not None and checked is not None:
                if state_status == "done" and not checked:
                    inconsistencies.append(
                        SuiviInconsistency(
                            feature_key=feature_key,
                            task_key=task_key,
                            kind="etat_done_case_vide",
                            message="state.json indique done mais tasks.md n'est pas coché",
                            state_status=state_status,
                            tasks_md_checked=checked,
                        )
                    )
                elif state_status != "done" and checked:
                    inconsistencies.append(
                        SuiviInconsistency(
                            feature_key=feature_key,
                            task_key=task_key,
                            kind="etat_non_done_case_cochee",
                            message="tasks.md est coché mais state.json n'indique pas done",
                            state_status=state_status,
                            tasks_md_checked=checked,
                        )
                    )
            elif state_status is not None:
                inconsistencies.append(
                    SuiviInconsistency(
                        feature_key=feature_key,
                        task_key=task_key,
                        kind="tache_absente_tasks_md",
                        message="tâche présente dans state.json mais absente de tasks.md",
                        state_status=state_status,
                    )
                )
            elif checked is not None:
                inconsistencies.append(
                    SuiviInconsistency(
                        feature_key=feature_key,
                        task_key=task_key,
                        kind="case_absente_state",
                        message="tâche présente dans tasks.md mais absente de state.json",
                        tasks_md_checked=checked,
                    )
                )
    return inconsistencies


def _ingest(
    session: Session,
    project: Project,
    *,
    state_path: str | Path | None,
    tasks_paths: Sequence[str | Path] | None,
    feature_override: Feature | None = None,
) -> SuiviIngestionResult:
    if state_path is None and not tasks_paths:
        raise SuiviIngestionError("aucune source de suivi fournie")
    source = "suivi" if state_path is not None and tasks_paths else (
        "state.json" if state_path is not None else "tasks.md"
    )
    run = IngestionRun(
        project_id=project.id,
        repository_id=None,
        source=source,
        started_at=utc_now(),
        status="running",
    )
    session.add(run)
    session.flush()
    try:
        parsed_features = parse_state_file(state_path) if state_path is not None else ()
        parsed_md = [parse_tasks_md_file(path) for path in (tasks_paths or ())]
        stats: dict[str, Any] = {
            "features_seen": len(parsed_features),
            "features_inserted": 0,
            "features_updated": 0,
            "tasks_seen": sum(len(feature.tasks) for feature in parsed_features),
            "tasks_inserted": 0,
            "tasks_updated": 0,
            "md_files": len(parsed_md),
            "md_tasks_inserted": 0,
            "md_tasks_updated": 0,
        }
        state_tasks: dict[str, dict[str, str]] = {}
        md_tasks: dict[str, dict[str, bool]] = {}
        features_by_key: dict[str, Feature] = {}
        with session.begin_nested():
            for parsed_feature in parsed_features:
                feature, created = _upsert_feature(session, project, parsed_feature)
                features_by_key[feature.key] = feature
                stats["features_inserted" if created else "features_updated"] += 1
                state_tasks[feature.key] = {}
                for state_task in parsed_feature.tasks:
                    _task, task_created = _upsert_state_task(session, feature, state_task)
                    stats["tasks_inserted" if task_created else "tasks_updated"] += 1
                    state_tasks[feature.key][state_task.key] = state_task.status
            for parsed_file in parsed_md:
                if feature_override is not None and len(parsed_md) == 1:
                    feature = feature_override
                else:
                    feature, feature_created = _feature_for_md(
                        session,
                        project,
                        parsed_file,
                        {item.key: item for item in parsed_features},
                        features_by_key,
                    )
                    if feature_created:
                        stats["features_inserted"] += 1
                md_tasks.setdefault(feature.key, {})
                for md_task in parsed_file.tasks:
                    _task, task_created = _upsert_md_task(session, feature, md_task)
                    stats["md_tasks_inserted" if task_created else "md_tasks_updated"] += 1
                    md_tasks[feature.key][md_task.key] = md_task.checked
        inconsistencies = _compare(state_tasks, md_tasks) if parsed_md and state_path is not None else []
        stats["inconsistencies"] = len(inconsistencies)
        if parsed_md and state_path is not None:
            with session.begin_nested():
                session.execute(
                    delete(SuiviInconsistencyRecord).where(
                        SuiviInconsistencyRecord.project_id == project.id
                    )
                )
                for item in inconsistencies:
                    session.add(
                        SuiviInconsistencyRecord(
                            project_id=project.id,
                            ingestion_run_id=run.id,
                            feature_key=item.feature_key,
                            task_key=item.task_key,
                            kind=item.kind,
                            message=item.message,
                            state_status=item.state_status,
                            tasks_md_checked=item.tasks_md_checked,
                        )
                    )
        run.status = "done"
        run.finished_at = utc_now()
        run.stats_json = redact(
            json.dumps(stats, sort_keys=True, ensure_ascii=False)
        )
        session.flush()
        return SuiviIngestionResult(
            run=run,
            stats=stats,
            inconsistencies=tuple(inconsistencies),
        )
    except Exception as exc:  # noqa: BLE001 - l'échec est journalisé puis propagé
        run.status = "failed"
        run.finished_at = utc_now()
        run.error = redact(str(exc))[:2000]
        run.stats_json = redact(
            json.dumps({"error": str(exc)[:500]}, ensure_ascii=False)
        )
        session.flush()
        if isinstance(exc, SuiviIngestionError):
            raise
        raise SuiviIngestionError(str(exc)) from exc


def ingest_state(session: Session, project: Project, state_path: str | Path) -> SuiviIngestionResult:
    """Ingère uniquement `state.json`."""
    return _ingest(session, project, state_path=state_path, tasks_paths=None)


def ingest_tasks_md(
    session: Session,
    project: Project,
    tasks_path: str | Path,
    *,
    feature: Feature | None = None,
) -> SuiviIngestionResult:
    """Ingère uniquement un `tasks.md`."""
    return _ingest(
        session,
        project,
        state_path=None,
        tasks_paths=[tasks_path],
        feature_override=feature,
    )


def ingest_suivi(
    session: Session,
    project: Project,
    *,
    state_path: str | Path | None = None,
    tasks_paths: Sequence[str | Path] | None = None,
) -> SuiviIngestionResult:
    """Ingère `state.json` et un ou plusieurs `tasks.md`, puis compare."""
    return _ingest(
        session,
        project,
        state_path=state_path,
        tasks_paths=tasks_paths,
    )
