"""Application FastAPI de la Console SDLC.

L'application expose la santé, le jeton CSRF et le suivi généré. Les autres
routes métier arrivent avec les lots suivants.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from . import __version__
from .db import DEFAULT_DATABASE_URL, make_engine, make_session_factory
from .models import Feature, Project, Task
from .security import (
    DEFAULT_ALLOWED_HOSTS,
    DEFAULT_ALLOWED_ORIGINS,
    CsrfProtector,
    SecurityMiddleware,
)
from .services.features_view import (
    build_feature_detail,
    build_features_view,
    build_task_report,
    get_task_view,
    list_tasks_view,
)
from .services.gates import config_fingerprint as gate_config_fingerprint
from .services.gates import gate_run_history, latest_gate_runs
from .services.overview import build_overview
from .services.suivi_generator import generate_suivi, suivi_status
from .services.suivi_watcher import EventBroker, SuiviWatcher
from .services.task_update import TaskUpdateError, update_task_status
from .services.team_metrics import build_team_metrics
from .services.waivers import (
    WaiverError,
    create_waiver,
    list_waivers,
    waiver_data,
)


class TaskStatusUpdate(BaseModel):
    """Corps JSON de mise à jour d'une tâche."""

    status: Literal["todo", "doing", "done", "blocked", "cancelled"]
    note: str | None = None


class WaiverCreate(BaseModel):
    """Corps JSON de création d'une dérogation."""

    gate_key: str
    target_type: Literal["gate", "gate_run", "finding"]
    target_id: str | None = None
    reason: str
    owner: str
    approver: str
    expires_at: datetime


def _sse_frame(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "message")
    return (
        f"event: {event_type}\n"
        f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    )


def _event_stream(
    request: Request,
    broker: EventBroker,
    project_filter: int | None,
) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        queue = broker.subscribe()
        try:
            yield _sse_frame(
                {
                    "type": "ready",
                    "project_id": project_filter,
                }
            )
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if (
                    project_filter is not None
                    and event.get("project_id") not in (None, project_filter)
                ):
                    continue
                yield _sse_frame(event)
        finally:
            broker.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def create_app(
    *,
    allowed_hosts: set[str] | None = None,
    allowed_origins: set[str] | None = None,
    csrf_secret: bytes | None = None,
    database_url: str | None = None,
    session_factory: sessionmaker[Session] | None = None,
    docs_dir: str | Path | None = None,
    project_root: str | Path | None = None,
    state_path: str | Path | None = None,
    tasks_path: str | Path | None = None,
    suivi_html_path: str | Path | None = None,
    suivi_json_path: str | Path | None = None,
    open_suivi_on_ready: bool = True,
    config_fingerprint: str | None = None,
    watcher_enabled: bool = True,
    watcher_interval: float = 1.0,
) -> FastAPI:
    """Crée l'application FastAPI avec la sécurité locale et le suivi."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        watcher: SuiviWatcher | None = None
        engine_created = False
        if watcher_enabled:
            factory = application.state.session_factory
            if factory is None:
                engine = make_engine(str(application.state.database_url))
                application.state.engine = engine
                factory = make_session_factory(engine)
                application.state.session_factory = factory
                engine_created = True
            watcher = SuiviWatcher(
                factory,
                project_root=application.state.project_root,
                docs_dir=application.state.docs_dir,
                state_path=application.state.state_path,
                tasks_path=application.state.tasks_path,
                html_path=application.state.suivi_html_path,
                json_path=application.state.suivi_json_path,
                broker=application.state.broker,
                interval_seconds=watcher_interval,
            )
            watcher.start()
            application.state.watcher = watcher
        try:
            yield
        finally:
            if watcher is not None:
                watcher.stop()
            if engine_created and application.state.engine is not None:
                application.state.engine.dispose()

    app = FastAPI(title="Console SDLC", version=__version__, lifespan=lifespan)
    csrf = CsrfProtector(csrf_secret)
    app.add_middleware(
        SecurityMiddleware,
        allowed_hosts=allowed_hosts or set(DEFAULT_ALLOWED_HOSTS),
        allowed_origins=allowed_origins or set(DEFAULT_ALLOWED_ORIGINS),
        csrf=csrf,
    )
    app.state.session_factory = session_factory
    app.state.database_url = database_url or os.environ.get(
        "SDLC_DATABASE_URL",
        DEFAULT_DATABASE_URL,
    )
    app.state.engine = None
    app.state.project_root = (
        Path(project_root) if project_root is not None else Path.cwd()
    )
    app.state.docs_dir = Path(docs_dir) if docs_dir is not None else Path("docs")
    app.state.state_path = Path(state_path) if state_path is not None else None
    app.state.tasks_path = Path(tasks_path) if tasks_path is not None else None
    app.state.suivi_html_path = (
        Path(suivi_html_path) if suivi_html_path is not None else None
    )
    app.state.suivi_json_path = (
        Path(suivi_json_path) if suivi_json_path is not None else None
    )
    app.state.open_suivi_on_ready = bool(open_suivi_on_ready)
    app.state.gate_config_fingerprint = (
        config_fingerprint
        if config_fingerprint is not None
        else gate_config_fingerprint(None)
    )
    app.state.broker = EventBroker()
    app.state.watcher = None

    def _session() -> Generator[Session, None, None]:
        factory = app.state.session_factory
        if factory is None:
            engine = make_engine(str(app.state.database_url))
            factory = make_session_factory(engine)
            app.state.engine = engine
            app.state.session_factory = factory
        session = factory()
        try:
            yield session
        finally:
            session.close()

    def _project(session: Session, project_id: int) -> Project:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="projet introuvable")
        return project

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/csrf")
    def csrf_token() -> dict[str, str]:
        return {"token": csrf.issue()}

    @app.get("/api/events")
    async def events(
        request: Request,
        project_id: int | None = Query(default=None),
    ) -> StreamingResponse:
        return _event_stream(request, app.state.broker, project_id)

    @app.get("/api/projects/{project_id}/events")
    async def project_events(
        project_id: int,
        request: Request,
    ) -> StreamingResponse:
        return _event_stream(request, app.state.broker, project_id)

    @app.get("/api/projects")
    def projects(session: Session = Depends(_session)) -> list[dict[str, object]]:  # noqa: B008
        rows = session.scalars(select(Project).order_by(Project.name)).all()
        return [
            {"id": project.id, "name": project.name, "slug": project.slug}
            for project in rows
        ]

    @app.get("/api/projects/{project_id}/overview")
    def get_overview(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return build_overview(session, project)

    @app.get("/api/projects/{project_id}/team")
    def get_team(
        project_id: int,
        repository_id: str | None = Query(default=None),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        try:
            selected = (
                None
                if repository_id is None or repository_id == "all"
                else [int(repository_id)]
            )
            return build_team_metrics(
                session,
                project,
                repository_ids=selected,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/waivers")
    def get_waivers(
        project_id: int,
        gate_key: str | None = Query(default=None),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        records = list_waivers(session, project, gate_key=gate_key)
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "waivers": [waiver_data(record) for record in records],
            "total": len(records),
        }

    @app.post("/api/projects/{project_id}/waivers")
    def post_waiver(
        project_id: int,
        payload: WaiverCreate,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        try:
            record = create_waiver(
                session,
                project,
                gate_key=payload.gate_key,
                target_type=payload.target_type,
                target_id=payload.target_id,
                reason=payload.reason,
                owner=payload.owner,
                approver=payload.approver,
                expires_at=payload.expires_at,
                actor_label="orchestrateur local",
            )
            session.commit()
        except WaiverError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"waiver": waiver_data(record)}

    @app.get("/api/projects/{project_id}/gates")
    def get_gates(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        gates = latest_gate_runs(
            session,
            project,
            current_fingerprint=app.state.gate_config_fingerprint,
        )
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "gates": gates,
            "total": len(gates),
        }

    @app.get("/api/projects/{project_id}/gates/{gate_key}/runs")
    def get_gate_runs(
        project_id: int,
        gate_key: str,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        runs = gate_run_history(
            session,
            project,
            gate_key,
            current_fingerprint=app.state.gate_config_fingerprint,
        )
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "gate_key": gate_key,
            "runs": runs,
            "total": len(runs),
        }

    @app.get("/api/projects/{project_id}/features")
    def get_features(
        project_id: int,
        phase: str | None = Query(default=None),
        gate: str | None = Query(default=None),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return build_features_view(session, project, phase=phase, gate=gate)

    @app.get("/api/projects/{project_id}/features/{feature_key}")
    def get_feature(
        project_id: int,
        feature_key: str,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        payload = build_feature_detail(session, project, feature_key)
        if payload is None:
            raise HTTPException(status_code=404, detail="feature introuvable")
        return payload

    @app.get("/api/projects/{project_id}/tasks")
    def get_tasks(
        project_id: int,
        feature_key: str | None = Query(default=None),
        status: str | None = Query(default=None),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return list_tasks_view(
            session,
            project,
            feature_key=feature_key,
            status=status,
        )

    @app.get("/api/projects/{project_id}/tasks/{task_id}")
    def get_task(
        project_id: int,
        task_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        payload = get_task_view(session, project, task_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="tâche introuvable")
        return payload

    @app.patch("/api/projects/{project_id}/tasks/{task_id}")
    def patch_task(
        project_id: int,
        task_id: int,
        payload: TaskStatusUpdate,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        task = session.scalar(
            select(Task)
            .join(Feature, Task.feature_id == Feature.id)
            .where(Feature.project_id == project.id, Task.id == task_id)
        )
        if task is None:
            raise HTTPException(status_code=404, detail="tâche introuvable")
        try:
            result = update_task_status(
                session,
                project,
                task,
                status=payload.status,
                note=payload.note,
                state_path=app.state.state_path,
                tasks_path=app.state.tasks_path,
                html_path=app.state.suivi_html_path,
                json_path=app.state.suivi_json_path,
                docs_dir=app.state.docs_dir,
                root=app.state.project_root,
            )
        except (TaskUpdateError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        app.state.broker.publish(
            {
                "type": "suivi.updated",
                "project_id": project.id,
                "project_slug": project.slug,
                "sources": [
                    str(result.tasks_path),
                    str(result.state_path),
                    str(result.html_path),
                ],
                "generated_at": result.generated_at.isoformat(),
                "duration_ms": result.duration_ms,
                "inconsistencies": 0,
                "conflicts": [],
            }
        )
        return {
            "task": get_task_view(session, project, task_id),
            "supports": {
                "tasks_md": str(result.tasks_path),
                "state_json": str(result.state_path),
                "html": str(result.html_path),
                "json": str(result.json_path),
            },
            "duration_ms": result.duration_ms,
            "generated_at": result.generated_at.isoformat(),
        }

    @app.get("/api/projects/{project_id}/tasks/{task_id}/report")
    def get_task_report(
        project_id: int,
        task_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        payload = build_task_report(session, project, task_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="tâche introuvable")
        return payload

    @app.get("/api/projects/{project_id}/suivi")
    def get_suivi(
        project_id: int,
        request: Request,
        format: Literal["json", "html"] | None = Query(default=None),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> Response:
        project = _project(session, project_id)
        document = generate_suivi(
            session,
            project,
            html_path=app.state.suivi_html_path,
            json_path=app.state.suivi_json_path,
            docs_dir=app.state.docs_dir,
        )
        accept = request.headers.get("accept", "")
        if format == "html" or (format is None and "text/html" in accept):
            return HTMLResponse(
                document.html,
                media_type="text/html; charset=utf-8",
            )
        return JSONResponse(document.data)

    @app.get("/api/projects/{project_id}/suivi/status")
    def get_suivi_status(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        payload = suivi_status(
            session,
            project,
            html_path=app.state.suivi_html_path,
            json_path=app.state.suivi_json_path,
            docs_dir=app.state.docs_dir,
        )
        payload["open_on_ready"] = app.state.open_suivi_on_ready
        payload["url"] = f"/api/projects/{project_id}/suivi?format=html"
        return payload

    return app


app = create_app()
