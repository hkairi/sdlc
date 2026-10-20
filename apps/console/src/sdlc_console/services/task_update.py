"""Mise à jour atomique d'une tâche : state.json, tasks.md, base et HTML."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import Feature, Project, SuiviInconsistency, Task, utc_now
from ..paths import resolve_within
from .features import TASK_STATUSES
from .suivi_generator import build_suivi_data, render_suivi_html
from .suivi_ingestion import TASK_LINE


class TaskUpdateError(ValueError):
    """Erreur de mise à jour d'une tâche."""


@dataclass(frozen=True)
class TaskUpdateResult:
    """Résultat d'une mise à jour atomique."""

    task: Task
    status: str
    note: str | None
    state_path: Path
    tasks_path: Path
    html_path: Path
    json_path: Path
    duration_ms: float
    generated_at: datetime


def _iso_date(value: datetime) -> str:
    return value.astimezone(UTC).date().isoformat()


def _state_feature_matches(raw: dict[str, Any], feature: Feature, tasks_path: Path) -> bool:
    identifiers = {
        str(raw.get("id") or ""),
        str(raw.get("key") or ""),
        str(raw.get("change") or ""),
        str(raw.get("name") or ""),
    }
    if feature.key in identifiers or (feature.change and feature.change in identifiers):
        return True
    raw_tasks = raw.get("tasks_file")
    if raw_tasks:
        raw_path = Path(str(raw_tasks))
        return raw_path == tasks_path or raw_path.name == tasks_path.name
    return False


def _locate_state_task(
    state: dict[str, Any],
    feature: Feature,
    task: Task,
    tasks_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    features = state.get("features")
    if not isinstance(features, list):
        raise TaskUpdateError("state.json sans liste de features")
    raw_feature = next(
        (
            item
            for item in features
            if isinstance(item, dict) and _state_feature_matches(item, feature, tasks_path)
        ),
        None,
    )
    if raw_feature is None:
        raise TaskUpdateError(f"feature absente de state.json : {feature.key}")
    raw_tasks = raw_feature.get("tasks")
    if not isinstance(raw_tasks, list):
        raise TaskUpdateError(f"tâches absentes de state.json pour {feature.key}")
    raw_task = next(
        (
            item
            for item in raw_tasks
            if isinstance(item, dict)
            and str(item.get("id") or item.get("key") or "") == task.key
        ),
        None,
    )
    if raw_task is None:
        raise TaskUpdateError(f"tâche absente de state.json : {task.key}")
    return raw_feature, raw_task


def _update_state_text(
    text: str,
    feature: Feature,
    task: Task,
    tasks_path: Path,
    *,
    status: str,
    note: str | None,
    moment: datetime,
) -> str:
    try:
        state = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TaskUpdateError(f"state.json illisible : {exc}") from exc
    if not isinstance(state, dict):
        raise TaskUpdateError("state.json doit contenir un objet")
    _raw_feature, raw_task = _locate_state_task(state, feature, task, tasks_path)
    date = _iso_date(moment)
    raw_task["status"] = status
    raw_task["updated"] = date
    if note is not None:
        raw_task["note"] = note
    history = raw_task.get("history")
    if not isinstance(history, list):
        history = []
    entry: dict[str, Any] = {"date": date, "status": status}
    if note is not None:
        entry["note"] = note
    history.append(entry)
    raw_task["history"] = history
    state["file_updated"] = date
    return json.dumps(state, ensure_ascii=False, indent=2) + "\n"


def _update_tasks_text(text: str, task_key: str, *, done: bool) -> str:
    checkbox = "x" if done else " "
    lines = text.splitlines(keepends=True)
    found = 0
    updated: list[str] = []
    for line in lines:
        if line.endswith("\r\n"):
            ending, body = "\r\n", line[:-2]
        elif line.endswith("\n"):
            ending, body = "\n", line[:-1]
        elif line.endswith("\r"):
            ending, body = "\r", line[:-1]
        else:
            ending, body = "", line
        if TASK_LINE.match(body):
            match = TASK_LINE.match(body)
            assert match is not None
            if match.group("key") == task_key:
                found += 1
                body = f"- [{checkbox}] {task_key} {match.group('body')}"
        updated.append(body + ending)
    if found == 0:
        raise TaskUpdateError(f"tâche absente de tasks.md : {task_key}")
    if found > 1:
        raise TaskUpdateError(f"tâche dupliquée dans tasks.md : {task_key}")
    return "".join(updated)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _snapshot(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _restore(path: Path, content: bytes | None) -> None:
    try:
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    except (FileNotFoundError, NotADirectoryError):
        # Le chemin de sortie peut être invalide ; les autres supports sont
        # restaurés indépendamment.
        return


def _default_paths(
    project: Project,
    *,
    docs_dir: Path,
) -> tuple[Path, Path]:
    html = docs_dir / f"suivi-{project.slug}.html"
    json_path = docs_dir / "suivi" / f"{project.slug}.generated.json"
    return html, json_path


def update_task_status(
    session: Session,
    project: Project,
    task: Task,
    *,
    status: str,
    note: str | None = None,
    state_path: str | Path | None = None,
    tasks_path: str | Path | None = None,
    html_path: str | Path | None = None,
    json_path: str | Path | None = None,
    docs_dir: str | Path | None = None,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
) -> TaskUpdateResult:
    """Met à jour les trois supports et la base, ou restaure tout en cas d'échec."""
    started = time.perf_counter()
    normalized = status.strip().lower()
    if normalized not in TASK_STATUSES:
        raise TaskUpdateError(f"statut de tâche invalide : {status}")
    if task.feature.project_id != project.id:
        raise TaskUpdateError("tâche hors du projet")

    root_path = Path(root or Path.cwd()).resolve()
    feature = task.feature
    docs = Path(docs_dir) if docs_dir is not None else root_path / "docs"
    docs = resolve_within(root_path, docs, allow_missing=True)
    default_html, default_json = _default_paths(project, docs_dir=docs)
    state_candidate = (
        Path(state_path)
        if state_path is not None
        else docs / "suivi" / f"{project.slug}.json"
    )
    fallback_tasks = (
        Path("openspec")
        / "changes"
        / (feature.change or feature.key)
        / "tasks.md"
    )
    tasks_candidate = (
        Path(tasks_path)
        if tasks_path is not None
        else Path(feature.tasks_file) if feature.tasks_file else fallback_tasks
    )
    try:
        state_target = resolve_within(root_path, state_candidate)
        tasks_target = resolve_within(root_path, tasks_candidate)
    except FileNotFoundError as exc:
        raise TaskUpdateError(f"source de suivi introuvable : {exc}") from exc
    html_target = resolve_within(
        root_path,
        Path(html_path) if html_path is not None else default_html,
        allow_missing=True,
    )
    json_target = resolve_within(
        root_path,
        Path(json_path) if json_path is not None else default_json,
        allow_missing=True,
    )
    targets = {state_target, tasks_target, html_target, json_target}
    if len(targets) < 4:
        raise TaskUpdateError("les supports state, tasks, HTML et JSON doivent être distincts")

    try:
        state_text = state_target.read_text(encoding="utf-8")
        tasks_text = tasks_target.read_text(encoding="utf-8")
    except OSError as exc:
        raise TaskUpdateError(f"source de suivi illisible : {exc}") from exc
    moment = generated_at or utc_now()
    next_state = _update_state_text(
        state_text,
        feature,
        task,
        tasks_target,
        status=normalized,
        note=note,
        moment=moment,
    )
    next_tasks = _update_tasks_text(
        tasks_text,
        task.key,
        done=normalized == "done",
    )

    snapshots = {path: _snapshot(path) for path in targets}
    try:
        task.status = normalized
        if note is not None:
            task.note = note
        task.updated_at = moment
        feature.updated_at = moment
        session.execute(
            delete(SuiviInconsistency).where(
                SuiviInconsistency.project_id == project.id,
                SuiviInconsistency.feature_key == feature.key,
                SuiviInconsistency.task_key == task.key,
            )
        )
        session.flush()
        data = build_suivi_data(session, project, generated_at=moment)
        html_text = render_suivi_html(data)
        json_text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        _atomic_write(tasks_target, next_tasks)
        _atomic_write(state_target, next_state)
        _atomic_write(html_target, html_text)
        _atomic_write(json_target, json_text)
        session.commit()
    except Exception:
        for path, content in snapshots.items():
            _restore(path, content)
        session.rollback()
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 1)
    return TaskUpdateResult(
        task=task,
        status=normalized,
        note=note,
        state_path=state_target,
        tasks_path=tasks_target,
        html_path=html_target,
        json_path=json_target,
        duration_ms=duration_ms,
        generated_at=moment,
    )
