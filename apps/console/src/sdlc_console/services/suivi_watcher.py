"""Watcher des sources de suivi et diffusion des événements `suivi.updated`."""

from __future__ import annotations

import asyncio
import hashlib
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..models import Project, utc_now
from ..paths import PathSecurityError, resolve_within
from .suivi_generator import generate_suivi
from .suivi_ingestion import ingest_suivi


class EventBroker:
    """Diffusion thread-safe d'événements vers les abonnés SSE."""

    def __init__(self) -> None:
        self._subscribers: dict[
            int,
            tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]],
        ] = {}
        self._next_id = 0
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        with self._lock:
            self._next_id += 1
            self._subscribers[self._next_id] = (loop, queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            for key, (_loop, candidate) in list(self._subscribers.items()):
                if candidate is queue:
                    del self._subscribers[key]
                    return

    def publish(self, event: dict[str, Any]) -> None:
        with self._lock:
            subscribers = list(self._subscribers.values())
        for loop, queue in subscribers:
            if loop.is_closed():
                continue
            try:
                loop.call_soon_threadsafe(queue.put_nowait, event)
            except RuntimeError:
                continue


def _fingerprint(path: Path) -> tuple[int, int, str] | None:
    try:
        stat = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size, digest


def _conflict_data(item: object) -> dict[str, Any]:
    return {
        "feature_key": getattr(item, "feature_key", None),
        "task_key": getattr(item, "task_key", None),
        "kind": getattr(item, "kind", None),
        "message": getattr(item, "message", None),
        "state_status": getattr(item, "state_status", None),
        "tasks_md_checked": getattr(item, "tasks_md_checked", None),
    }


class SuiviWatcher:
    """Surveille `state.json` et les `tasks.md`, resynchronise et publie les événements."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        project_root: str | Path,
        docs_dir: str | Path,
        state_path: str | Path | None = None,
        tasks_path: str | Path | None = None,
        html_path: str | Path | None = None,
        json_path: str | Path | None = None,
        broker: EventBroker | None = None,
        interval_seconds: float = 1.0,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.project_root = Path(project_root).resolve()
        self.docs_dir = resolve_within(
            self.project_root,
            Path(docs_dir),
            allow_missing=True,
        )
        self.state_path = Path(state_path) if state_path is not None else None
        self.tasks_path = Path(tasks_path) if tasks_path is not None else None
        self.html_path = Path(html_path) if html_path is not None else None
        self.json_path = Path(json_path) if json_path is not None else None
        self.broker = broker or EventBroker()
        self.interval_seconds = max(0.05, float(interval_seconds))
        self.on_event = on_event
        self._known: dict[int, dict[Path, tuple[int, int, str] | None]] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="sdlc-suivi-watcher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self.interval_seconds * 4))
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.scan_once()
            except Exception as exc:  # noqa: BLE001 — le watcher ne doit pas mourir
                self._publish(
                    {
                        "type": "suivi.error",
                        "message": str(exc)[:1000],
                        "generated_at": utc_now().astimezone(UTC).isoformat(),
                    }
                )
            self._stop.wait(self.interval_seconds)

    def _publish(self, event: dict[str, Any]) -> None:
        self.broker.publish(event)
        if self.on_event is not None:
            self.on_event(event)

    def _state_for(self, project: Project) -> Path:
        candidate = (
            self.state_path
            if self.state_path is not None
            else self.docs_dir / "suivi" / f"{project.slug}.json"
        )
        return resolve_within(self.project_root, candidate, allow_missing=True)

    def _tasks_for(self, project: Project) -> list[Path]:
        if self.tasks_path is not None:
            candidates = [self.tasks_path]
        else:
            candidates = [
                Path(feature.tasks_file)
                for feature in project.features
                if feature.tasks_file
            ]
        paths: list[Path] = []
        for candidate in candidates:
            try:
                path = resolve_within(self.project_root, candidate, allow_missing=True)
            except PathSecurityError:
                continue
            if path not in paths:
                paths.append(path)
        return paths

    def _generate(self, session: Session, project: Project) -> datetime:
        moment = utc_now()
        html_path = (
            resolve_within(self.project_root, self.html_path, allow_missing=True)
            if self.html_path is not None
            else None
        )
        json_path = (
            resolve_within(self.project_root, self.json_path, allow_missing=True)
            if self.json_path is not None
            else None
        )
        generate_suivi(
            session,
            project,
            html_path=html_path,
            json_path=json_path,
            docs_dir=self.docs_dir,
            generated_at=moment,
        )
        return moment

    def scan_once(self) -> list[dict[str, Any]]:
        """Scanne les sources et publie un événement par projet modifié."""
        with self._lock:
            events: list[dict[str, Any]] = []
            with self.session_factory() as session:
                projects = list(
                    session.scalars(select(Project).order_by(Project.id)).all()
                )
                for project in projects:
                    try:
                        events.extend(self._scan_project(session, project))
                    except Exception as exc:  # noqa: BLE001 — un projet ne bloque pas les autres
                        session.rollback()
                        event = {
                            "type": "suivi.error",
                            "project_id": project.id,
                            "project_slug": project.slug,
                            "message": str(exc)[:1000],
                            "generated_at": utc_now().astimezone(UTC).isoformat(),
                        }
                        self._publish(event)
                        events.append(event)
            return events

    def _scan_project(self, session: Session, project: Project) -> list[dict[str, Any]]:
        state = self._state_for(project)
        tasks = self._tasks_for(project)
        watched = [path for path in [state, *tasks] if path.exists()]
        fingerprints = {path: _fingerprint(path) for path in watched}
        previous = self._known.get(project.id)
        if previous is None:
            self._known[project.id] = fingerprints
            return []
        changed = sorted(
            [
                path
                for path in set(fingerprints) | set(previous)
                if previous.get(path) != fingerprints.get(path)
            ],
            key=str,
        )
        if not changed:
            self._known[project.id] = fingerprints
            return []

        state_source = state if state.exists() else None
        tasks_sources = [path for path in tasks if path.exists()]
        if state_source is None and not tasks_sources:
            self._known[project.id] = fingerprints
            return []
        result = ingest_suivi(
            session,
            project,
            state_path=state_source,
            tasks_paths=tasks_sources,
        )
        session.commit()
        moment = self._generate(session, project)
        conflicts = [_conflict_data(item) for item in result.inconsistencies]
        event: dict[str, Any] = {
            "type": "suivi.updated",
            "project_id": project.id,
            "project_slug": project.slug,
            "sources": [str(path) for path in changed],
            "generated_at": moment.astimezone(UTC).isoformat(),
            "inconsistencies": len(conflicts),
            "conflicts": conflicts,
            "html_path": str(
                self.html_path
                if self.html_path is not None
                else self.docs_dir / f"suivi-{project.slug}.html"
            ),
        }
        self._publish(event)
        self._known[project.id] = fingerprints
        return [event]
