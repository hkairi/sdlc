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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from . import __version__
from .db import DEFAULT_DATABASE_URL, make_engine, make_session_factory
from .models import (
    Feature,
    GateFinding,
    GateRun,
    HumanNotification,
    Project,
    ReviewPackage,
    Task,
    TaskRun,
)
from .redaction import redact
from .security import (
    DEFAULT_ALLOWED_HOSTS,
    DEFAULT_ALLOWED_ORIGINS,
    CsrfProtector,
    SecurityMiddleware,
)
from .services.agent_runner import (
    RunPreflightError,
    cancel_run,
    enqueue_run,
    refresh_run,
)
from .services.audit import anchor_audit, verify_audit_chain
from .services.backup import BackupError, backup_database, backup_status, list_backups, verify_backup
from .services.config_view import build_configuration_view
from .services.decisions import (
    DecisionError,
    create_decision,
    decision_data,
    list_decisions,
    project_for_review,
)
from .services.deployments_view import build_deployments_view
from .services.documents_view import build_documents_view, read_document
from .services.dora import build_dora
from .services.escalations import (
    EscalationError,
    acknowledge_notification,
    escalate_timed_out_tasks,
    notification_data,
)
from .services.exports import build_export
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
from .services.ownership import build_ownership
from .services.pagination import PageParams, PaginationError
from .services.process_flow import build_process_flow
from .services.process_profiles import (
    ProcessError,
    build_process_inventory,
    create_override,
)
from .services.purge import PurgeError, run_audit_purge, run_purge
from .services.quality_view import build_performance_data_view
from .services.review_package import (
    ReviewPackageError,
    build_review_package,
    list_review_packages,
)
from .services.review_report import ReviewReportError, build_review_report
from .services.review_selection import candidates_from_config, select_reviewer
from .services.run_budget import apply_budget, budget_summary
from .services.run_journal import (
    build_independence,
    build_run_journal,
    record_independence_alert,
)
from .services.security_view import build_security_view
from .services.suivi_generator import generate_suivi, suivi_status
from .services.suivi_watcher import EventBroker, SuiviWatcher
from .services.task_update import TaskUpdateError, update_task_status
from .services.team_metrics import build_team_metrics
from .services.validation_chain import build_validation_chain
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


class RunBudgetUpdate(BaseModel):
    """Mise à jour du budget et du coût d'un run."""

    estimated_cost_eur: float | None = None
    cost_eur: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    budget_eur: float | None = None


class RunCreate(BaseModel):
    """Corps JSON de lancement d'un run configuré."""

    agent_id: str
    model: str
    role: Literal["executor", "reviewer"] = "executor"
    task_key: str
    repository_id: int
    budget_eur: float | None = None
    timeout_seconds: int | None = None


class DecisionCreate(BaseModel):
    """Corps JSON d'une décision humaine."""

    decision: Literal["approve", "approve_with_conditions", "reject", "info"]
    reason: str
    conditions: list[str] = []
    actor_label: str = "décision depuis le poste local, non authentifiée"
    actor_person_id: int | None = None
    scope: str | None = None
    expires_at: datetime | None = None


class ReviewReportCreate(BaseModel):
    """Corps JSON d'un rapport de revue."""

    verdict: Literal["pass", "warn", "fail"]
    confidence: float
    findings: list[dict[str, Any]]
    unverified: list[str] = []
    options: list[dict[str, Any]] = []
    recommendation: str = ""
    risks: list[str] = []
    questions: list[str] = []


class BackupCreate(BaseModel):
    """Corps JSON d'une sauvegarde globale."""

    label: str | None = None


class BackupVerify(BaseModel):
    """Corps JSON d'une vérification de sauvegarde."""

    backup_id: str | None = None


class PurgeRequest(BaseModel):
    """Corps JSON d'une purge explicite."""

    confirm: bool = False
    actor_label: str = "purge depuis le poste local"


class AuditPurgeRequest(BaseModel):
    """Corps JSON d'une purge d'audit ancrée."""

    cutoff: datetime | None = None
    actor_label: str = "purge d'audit locale"


class AuditAnchorRequest(BaseModel):
    """Corps JSON d'un ancrage d'audit."""

    reason: str = "ancrage manuel"
    actor_label: str = "purge depuis le poste local"


class NotificationAck(BaseModel):
    """Acquittement d'une notification humaine."""

    actor_label: str = "décision depuis le poste local, non authentifiée"


class ReviewPackageCreate(BaseModel):
    """Corps JSON de préparation d'un paquet de revue."""

    task_key: str
    feature_key: str | None = None
    spec_paths: list[str] = []
    diff: str = ""
    evidence_paths: list[str] = []
    adr_paths: list[str] = []


class ProcessOverrideCreate(BaseModel):
    """Corps JSON de surcharge du profil de processus."""

    repository_id: int | None = None
    profile_key: Literal["git_flow", "github_flow", "trunk_based", "gitlab_flow"]
    reason: str
    actor_label: str = "orchestrateur local"


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


def _run_event_stream(
    request: Request,
    session_factory: sessionmaker[Session],
    run_id: str,
) -> StreamingResponse:
    """Diffuse l'état et les nouveaux fragments du journal d'un run."""

    async def stream() -> AsyncIterator[str]:
        session = session_factory()
        offset = 0
        try:
            run = session.scalar(select(TaskRun).where(TaskRun.run_id == run_id))
            if run is None and run_id.isdigit():
                run = session.get(TaskRun, int(run_id))
            if run is None:
                yield _sse_frame({"type": "run.error", "message": "run introuvable"})
                return
            yield _sse_frame(
                {
                    "type": "ready",
                    "run_id": run.run_id,
                    "status": run.status,
                }
            )
            while True:
                refresh_run(session, run)
                session.commit()
                if run.log_path:
                    log_path = Path(run.log_path)
                    try:
                        size = log_path.stat().st_size
                        if size > offset:
                            with log_path.open("r", encoding="utf-8", errors="replace") as handle:
                                handle.seek(offset)
                                chunk = handle.read(size - offset)
                            offset = size
                            if chunk:
                                yield _sse_frame(
                                    {
                                        "type": "run.log",
                                        "run_id": run.run_id,
                                        "offset": offset,
                                        "text": redact(chunk),
                                    }
                                )
                    except FileNotFoundError:
                        pass
                if run.status in {"done", "failed", "timeout", "cancelled"}:
                    yield _sse_frame(
                        {
                            "type": "run.status",
                            "run_id": run.run_id,
                            "status": run.status,
                            "exit_code": run.exit_code,
                            "cost_eur": run.cost_eur,
                            "failure_reason": run.failure_reason,
                        }
                    )
                    break
                if await request.is_disconnected():
                    break
                await asyncio.sleep(0.25)
        finally:
            session.close()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _pagination(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
) -> PageParams:
    """Valide les bornes de pagination avec un message 400 explicite."""
    try:
        return PageParams(limit=limit, offset=offset)
    except PaginationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def default_static_dir() -> Path | None:
    """Retourne le build frontend embarqué s'il contient un index."""
    bundled = Path(__file__).with_name("web") / "dist"
    return bundled.resolve() if (bundled / "index.html").is_file() else None


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
    config_data: dict[str, object] | None = None,
    config_path: str | Path | None = None,
    static_dir: str | Path | None = None,
    backup_dir: str | Path | None = None,
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
    app.state.config_data = config_data or {}
    app.state.config_path = Path(config_path) if config_path is not None else None
    app.state.backup_dir = (
        Path(backup_dir).resolve()
        if backup_dir is not None
        else (Path(project_root).resolve() if project_root is not None else Path.cwd().resolve()) / "backups"
    )
    app.state.static_dir = Path(static_dir).resolve() if static_dir is not None else None
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

    @app.post("/api/backup")
    def post_backup(
        payload: BackupCreate,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        _ = payload
        try:
            manifest = backup_database(
                session,
                backups_dir=app.state.backup_dir,
            )
        except BackupError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"backup": manifest}

    @app.get("/api/backups")
    def get_backups() -> dict[str, object]:
        return list_backups(app.state.backup_dir)

    @app.get("/api/backups/status")
    def get_backup_status() -> dict[str, object]:
        payload = list_backups(app.state.backup_dir)
        latest = payload.get("latest")
        if not isinstance(latest, dict):
            return {
                **payload,
                "status": "not_measured",
                "detail": "aucune sauvegarde vérifiée",
            }
        try:
            manifest = backup_status(str(latest.get("backup_path")))
        except BackupError as exc:
            return {**payload, "status": "invalid", "detail": str(exc)}
        return {**payload, "status": "measured", "latest": manifest}

    @app.post("/api/backups/{backup_id}/verify")
    def post_backup_verify(
        backup_id: str,
        payload: BackupVerify,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        _ = (payload, session)
        if not backup_id.replace("-", "").replace("_", "").replace("T", "").replace("Z", "").isalnum():
            raise HTTPException(status_code=400, detail="identifiant de sauvegarde invalide")
        path = app.state.backup_dir / f"{backup_id}.json"
        try:
            manifest = verify_backup(path)
        except BackupError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"backup": manifest}

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

    @app.get("/api/projects/{project_id}/audit/integrity")
    def get_audit_integrity(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return verify_audit_chain(session, project.id)

    @app.post("/api/projects/{project_id}/audit/anchor")
    def post_audit_anchor(
        project_id: int,
        payload: AuditAnchorRequest,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        event = anchor_audit(
            session,
            project.id,
            actor_label=payload.actor_label,
            reason=payload.reason,
        )
        session.commit()
        return {
            "anchor": {
                "id": event.id,
                "generation": event.generation,
                "hash": event.hash,
            }
        }

    @app.post("/api/projects/{project_id}/audit/purge")
    def post_audit_purge(
        project_id: int,
        payload: AuditPurgeRequest,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        try:
            result = run_audit_purge(
                session,
                project,
                cutoff=payload.cutoff,
                actor_label=payload.actor_label,
            )
            session.commit()
        except PurgeError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=f"{exc.code}: {exc}") from exc
        return result

    @app.post("/api/projects/{project_id}/purge")
    def post_purge(
        project_id: int,
        payload: PurgeRequest,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        try:
            result = run_purge(
                session,
                project,
                backups_dir=app.state.backup_dir,
                config=app.state.config_data,
                root=app.state.project_root,
                confirm=payload.confirm,
                actor_label=payload.actor_label,
            )
            session.commit()
        except PurgeError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=f"{exc.code}: {exc}") from exc
        return result

    @app.get("/api/projects/{project_id}/configuration")
    def get_configuration(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return build_configuration_view(
            session,
            project,
            config=app.state.config_data,
            config_path=app.state.config_path,
            root=app.state.project_root,
        )

    @app.get("/api/projects/{project_id}/config")
    def get_config_alias(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        return get_configuration(project_id, session)

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
            payload = build_team_metrics(
                session,
                project,
                repository_ids=selected,
            )
            payload["validation"] = build_validation_chain(
                session,
                project,
                repository_ids=selected,
            )
            return payload
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/team/validation")
    def get_team_validation(
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
            return build_validation_chain(
                session,
                project,
                repository_ids=selected,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/team/ownership")
    def get_team_ownership(
        project_id: int,
        repository_id: str | None = Query(default=None),
        window_days: int = Query(default=90, ge=1),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        try:
            selected = (
                None
                if repository_id is None or repository_id == "all"
                else [int(repository_id)]
            )
            return build_ownership(
                session,
                project,
                repository_ids=selected,
                window_days=window_days,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/process")
    def get_process(
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
            payload = build_process_inventory(
                session,
                project,
                repository_ids=selected,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload["total"] = len(payload["repositories"])
        return payload

    @app.get("/api/projects/{project_id}/process/flow")
    def get_process_flow(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return build_process_flow(session, project)

    @app.get("/api/projects/{project_id}/review-packages")
    def get_review_packages(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        records = list_review_packages(session, project)
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "packages": [
                {
                    "id": record.id,
                    "task_key": record.task_key,
                    "feature_key": record.feature_key,
                    "fingerprint": record.fingerprint,
                    "path": record.report_path,
                    "created_at": record.created_at.isoformat(),
                }
                for record in records
            ],
            "total": len(records),
        }

    @app.post("/api/projects/{project_id}/reviews")
    def post_review_package(
        project_id: int,
        payload: ReviewPackageCreate,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        try:
            result = build_review_package(
                session,
                project,
                task_key=payload.task_key,
                feature_key=payload.feature_key,
                spec_paths=payload.spec_paths,
                diff=payload.diff,
                evidence_paths=payload.evidence_paths,
                adr_paths=payload.adr_paths,
                root=app.state.project_root,
            )
            session.commit()
        except ReviewPackageError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "package": {
                "id": result.record.id,
                "fingerprint": result.record.fingerprint,
                "path": result.record.report_path,
            },
            "payload": result.payload,
        }

    @app.post("/api/reviews/{package_id}/report")
    def post_review_report(
        package_id: int,
        payload: ReviewReportCreate,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        package = session.get(ReviewPackage, package_id)
        if package is None:
            raise HTTPException(status_code=404, detail="paquet de revue introuvable")
        project = session.get(Project, package.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="projet introuvable")
        try:
            result = build_review_report(
                session,
                project,
                package,
                verdict=payload.verdict,
                confidence=payload.confidence,
                findings=payload.findings,
                unverified=payload.unverified,
                options=payload.options,
                recommendation=payload.recommendation,
                risks=payload.risks,
                questions=payload.questions,
                root=app.state.project_root,
            )
            session.commit()
        except ReviewReportError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "report": {
                "id": result.record.id,
                "task_key": result.record.task_key,
                "verdict": result.record.verdict,
                "confidence": result.record.confidence,
                "path": result.record.report_path,
                "decision_path": result.record.decision_path,
            },
            "payload": result.payload,
        }

    def _run_payload(run: TaskRun) -> dict[str, object]:
        return {
            "id": run.id,
            "run_id": run.run_id,
            "task_key": run.task_key,
            "agent_id": run.agent_id,
            "model": run.model,
            "role": run.role,
            "read_only": run.role == "reviewer",
            "status": run.status,
            "pid": run.pid,
            "process_group": run.process_group,
            "timeout_seconds": run.timeout_seconds,
            "exit_code": run.exit_code,
            "failure_reason": run.failure_reason,
            "budget_eur": run.budget_eur,
            "budget": budget_summary(run),
            "log_path": run.log_path,
            "origin": run.origin,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        }

    @app.get("/api/projects/{project_id}/agents")
    def get_agents(
        project_id: int,
        agent_id: str | None = Query(default=None),
        role: str | None = Query(default=None),
        status: str | None = Query(default=None),
        page: PageParams = Depends(_pagination),  # noqa: B008 — dépendance FastAPI
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        journal = build_run_journal(
            session,
            project,
            agent_id=agent_id,
            role=role,
            status=status,
            limit=page.limit,
            offset=page.offset,
        )
        independence = build_independence(
            session,
            project,
            config=app.state.config_data,
        )
        alert = record_independence_alert(session, project, independence)
        session.commit()
        journal["independence"] = independence
        journal["independence_alert"] = alert
        return journal

    @app.get("/api/projects/{project_id}/runs")
    def get_project_runs(
        project_id: int,
        agent_id: str | None = Query(default=None),
        role: str | None = Query(default=None),
        status: str | None = Query(default=None),
        page: PageParams = Depends(_pagination),  # noqa: B008 — dépendance FastAPI
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return build_run_journal(
            session,
            project,
            agent_id=agent_id,
            role=role,
            status=status,
            limit=page.limit,
            offset=page.offset,
        )

    @app.get("/api/projects/{project_id}/independence")
    def get_independence(
        project_id: int,
        window_days: int = Query(default=30, ge=1),
        persist: bool = Query(default=False),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        summary = build_independence(
            session,
            project,
            window_days=window_days,
            config=app.state.config_data,
        )
        if persist:
            summary["alert"] = record_independence_alert(session, project, summary)
            session.commit()
        return summary

    @app.post("/api/projects/{project_id}/runs")
    def post_run(
        project_id: int,
        payload: RunCreate,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        try:
            run = enqueue_run(
                session,
                project,
                agent_id=payload.agent_id,
                model=payload.model,
                role=payload.role,
                task_key=payload.task_key,
                repository_id=payload.repository_id,
                budget_eur=payload.budget_eur,
                timeout_seconds=payload.timeout_seconds,
                config=app.state.config_data,
                root=app.state.project_root,
            )
            session.commit()
        except RunPreflightError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"run": _run_payload(run)}

    @app.get("/api/runs/{run_id}/events")
    async def get_run_events(
        run_id: str,
        request: Request,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> StreamingResponse:
        _ = session  # La dépendance vérifie le cycle de vie ; le flux ouvre sa session.
        factory = app.state.session_factory
        if factory is None:
            raise HTTPException(status_code=503, detail="base non initialisée")
        return _run_event_stream(request, factory, run_id)

    @app.get("/api/runs/{run_id}")
    def get_run(
        run_id: str,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        run = session.scalar(select(TaskRun).where(TaskRun.run_id == run_id))
        if run is None and run_id.isdigit():
            run = session.get(TaskRun, int(run_id))
        if run is None:
            raise HTTPException(status_code=404, detail="run introuvable")
        refresh_run(session, run)
        session.commit()
        return {"run": _run_payload(run)}

    @app.post("/api/runs/{run_id}/budget")
    def post_run_budget(
        run_id: str,
        payload: RunBudgetUpdate,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        run = session.scalar(select(TaskRun).where(TaskRun.run_id == run_id))
        if run is None and run_id.isdigit():
            run = session.get(TaskRun, int(run_id))
        if run is None:
            raise HTTPException(status_code=404, detail="run introuvable")
        summary = apply_budget(
            session,
            run,
            estimated_cost_eur=payload.estimated_cost_eur,
            cost_eur=payload.cost_eur,
            tokens_in=payload.tokens_in,
            tokens_out=payload.tokens_out,
            budget_eur=payload.budget_eur,
            config=app.state.config_data,
        )
        session.commit()
        return {"run": _run_payload(run), "budget": summary}

    @app.post("/api/runs/{run_id}/cancel")
    def post_cancel_run(
        run_id: str,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        run = session.scalar(select(TaskRun).where(TaskRun.run_id == run_id))
        if run is None and run_id.isdigit():
            run = session.get(TaskRun, int(run_id))
        if run is None:
            raise HTTPException(status_code=404, detail="run introuvable")
        cancel_run(session, run)
        session.commit()
        return {"run": _run_payload(run)}

    @app.post("/api/reviews/{review_id}/decision")
    def post_review_decision(
        review_id: int,
        payload: DecisionCreate,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        selected = project_for_review(session, review_id)
        if selected is None:
            raise HTTPException(status_code=404, detail="rapport de revue introuvable")
        project, report = selected
        try:
            record = create_decision(
                session,
                project,
                subject_type="review_report",
                subject_id=str(report.id),
                decision=payload.decision,
                reason=payload.reason,
                conditions=payload.conditions,
                actor_label=payload.actor_label,
                actor_person_id=payload.actor_person_id,
                scope=payload.scope,
                expires_at=payload.expires_at,
                config=app.state.config_data,
            )
            session.commit()
        except DecisionError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"decision": decision_data(record)}

    @app.get("/api/projects/{project_id}/decisions")
    def get_decisions(
        project_id: int,
        subject_type: str | None = Query(default=None),
        subject_id: str | None = Query(default=None),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        records = list_decisions(
            session,
            project,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "decisions": [decision_data(record) for record in records],
            "total": len(records),
        }

    @app.get("/api/projects/{project_id}/notifications")
    def get_notifications(
        project_id: int,
        pending: bool | None = Query(default=None),
        page: PageParams = Depends(_pagination),  # noqa: B008 — dépendance FastAPI
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        query = select(HumanNotification).where(HumanNotification.project_id == project.id)
        if pending is True:
            query = query.where(HumanNotification.acknowledged_at.is_(None))
        if pending is False:
            query = query.where(HumanNotification.acknowledged_at.is_not(None))
        rows = list(session.scalars(query.order_by(HumanNotification.id.desc())).all())
        total = len(rows)
        paged = rows[page.offset : page.offset + page.limit]
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "notifications": [notification_data(row) for row in paged],
            "total": total,
            "limit": page.limit,
            "offset": page.offset,
            "has_more": page.offset + len(paged) < total,
            "next_offset": page.offset + len(paged) if page.offset + len(paged) < total else None,
        }

    @app.post("/api/notifications/{notification_id}/ack")
    def post_notification_ack(
        notification_id: int,
        payload: NotificationAck,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        notification = session.get(HumanNotification, notification_id)
        if notification is None:
            raise HTTPException(status_code=404, detail="notification introuvable")
        project = session.get(Project, notification.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="projet introuvable")
        try:
            acknowledge_notification(
                session,
                project,
                notification,
                actor_label=payload.actor_label,
            )
            session.commit()
        except EscalationError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"notification": notification_data(notification)}

    @app.post("/api/projects/{project_id}/escalations/check")
    def post_escalation_check(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        escalated = escalate_timed_out_tasks(
            session,
            project,
            config=app.state.config_data,
        )
        session.commit()
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "escalated": escalated,
            "total": len(escalated),
        }

    @app.get("/api/projects/{project_id}/reviewers")
    def get_reviewers(
        project_id: int,
        author_agent: str = Query(default=""),
        author_model: str = Query(default=""),
        author_family: str | None = Query(default=None),
        waiver: bool = Query(default=False),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        selection = select_reviewer(
            author_agent=author_agent,
            author_model=author_model,
            author_family=author_family,
            candidates=candidates_from_config(app.state.config_data),
            waiver=waiver,
        )
        selected = selection.selected
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "selected": (
                {
                    "agent_id": selected.agent_id,
                    "model": selected.model,
                    "family": selected.family,
                    "label": selected.label,
                }
                if selected is not None
                else None
            ),
            "level": selection.level,
            "allowed": selection.allowed,
            "waiver_required": selection.waiver_required,
            "reason": selection.reason,
            "candidates": list(selection.candidates),
        }

    @app.put("/api/projects/{project_id}/process/override")
    def put_process_override(
        project_id: int,
        payload: ProcessOverrideCreate,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        try:
            record = create_override(
                session,
                project,
                repository_id=payload.repository_id,
                profile_key=payload.profile_key,
                reason=payload.reason,
                actor_label=payload.actor_label,
            )
            session.commit()
        except ProcessError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "override": {
                "id": record.id,
                "repository_id": record.repository_id,
                "profile_key": record.profile_key,
                "reason": record.reason,
                "actor_label": record.actor_label,
                "created_at": record.created_at.isoformat(),
            }
        }

    @app.get("/api/projects/{project_id}/deployments")
    def get_deployments(
        project_id: int,
        env: str | None = Query(default=None),
        window_days: int = Query(default=30, ge=1),
        page: PageParams = Depends(_pagination),  # noqa: B008 — dépendance FastAPI
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return build_deployments_view(
            session,
            project,
            env=env,
            limit=page.limit,
            offset=page.offset,
            window_days=window_days,
            root=app.state.project_root,
            current_fingerprint=app.state.gate_config_fingerprint,
        )

    @app.get("/api/projects/{project_id}/go-no-go")
    def get_go_no_go(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        payload = build_deployments_view(
            session,
            project,
            limit=1,
            root=app.state.project_root,
            current_fingerprint=app.state.gate_config_fingerprint,
        )
        return {
            "project": payload["project"],
            "go_no_go": payload["go_no_go"],
            "dora": payload["dora"],
            "sources": payload["sources"],
        }

    @app.get("/api/projects/{project_id}/dora")
    def get_dora(
        project_id: int,
        window_days: int = Query(default=30, ge=1),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return build_dora(session, project, window_days=window_days)

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

    @app.get("/api/projects/{project_id}/security")
    def get_security(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return build_security_view(
            session,
            project,
            root=app.state.project_root,
            config=app.state.config_data,
            current_fingerprint=app.state.gate_config_fingerprint,
        )

    @app.get("/api/projects/{project_id}/performance")
    def get_performance_data(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return build_performance_data_view(
            session,
            project,
            root=app.state.project_root,
            config=app.state.config_data,
            current_fingerprint=app.state.gate_config_fingerprint,
        )

    @app.get("/api/projects/{project_id}/quality")
    def get_quality(
        project_id: int,
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        return build_performance_data_view(
            session,
            project,
            root=app.state.project_root,
            config=app.state.config_data,
            current_fingerprint=app.state.gate_config_fingerprint,
        )

    @app.get("/api/projects/{project_id}/findings")
    def get_findings(
        project_id: int,
        gate_key: str | None = Query(default=None),
        severity: str | None = Query(default=None),
        page: PageParams = Depends(_pagination),  # noqa: B008 — dépendance FastAPI
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        query = (
            select(GateFinding)
            .join(GateRun, GateFinding.gate_run_id == GateRun.id)
            .where(GateRun.project_id == project.id)
        )
        if gate_key:
            query = query.where(GateRun.gate_key == gate_key)
        if severity:
            query = query.where(GateFinding.severity == severity)
        total = int(
            session.scalar(select(func.count()).select_from(query.subquery())) or 0
        )
        rows = list(
            session.scalars(
                query.order_by(GateFinding.id.desc())
                .offset(page.offset)
                .limit(page.limit)
            ).all()
        )
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "filters": {"gate_key": gate_key, "severity": severity},
            "findings": [
                {
                    "id": finding.id,
                    "gate_run_id": finding.gate_run_id,
                    "control": finding.control_key,
                    "key": finding.key,
                    "severity": finding.severity,
                    "message": finding.message,
                    "file": finding.file_path,
                    "line": finding.line,
                    "evidence": finding.evidence_path,
                }
                for finding in rows
            ],
            "total": total,
            "limit": page.limit,
            "offset": page.offset,
            "has_more": page.offset + len(rows) < total,
            "next_offset": page.offset + len(rows) if page.offset + len(rows) < total else None,
        }

    @app.get("/api/projects/{project_id}/gates")
    def get_gates(
        project_id: int,
        page: PageParams = Depends(_pagination),  # noqa: B008 — dépendance FastAPI
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        gates = latest_gate_runs(
            session,
            project,
            current_fingerprint=app.state.gate_config_fingerprint,
        )
        total = len(gates)
        paged = gates[page.offset : page.offset + page.limit]
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "gates": paged,
            "total": total,
            "limit": page.limit,
            "offset": page.offset,
            "has_more": page.offset + len(paged) < total,
            "next_offset": page.offset + len(paged) if page.offset + len(paged) < total else None,
        }

    @app.get("/api/projects/{project_id}/gates/{gate_key}/runs")
    def get_gate_runs(
        project_id: int,
        gate_key: str,
        page: PageParams = Depends(_pagination),  # noqa: B008 — dépendance FastAPI
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        runs = gate_run_history(
            session,
            project,
            gate_key,
            current_fingerprint=app.state.gate_config_fingerprint,
        )
        total = len(runs)
        paged = runs[page.offset : page.offset + page.limit]
        return {
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "gate_key": gate_key,
            "runs": paged,
            "total": total,
            "limit": page.limit,
            "offset": page.offset,
            "has_more": page.offset + len(paged) < total,
            "next_offset": page.offset + len(paged) if page.offset + len(paged) < total else None,
        }

    @app.get("/api/projects/{project_id}/features")
    def get_features(
        project_id: int,
        phase: str | None = Query(default=None),
        gate: str | None = Query(default=None),
        page: PageParams = Depends(_pagination),  # noqa: B008 — dépendance FastAPI
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        try:
            return build_features_view(
                session,
                project,
                phase=phase,
                gate=gate,
                limit=page.limit,
                offset=page.offset,
            )
        except PaginationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        page: PageParams = Depends(_pagination),  # noqa: B008 — dépendance FastAPI
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        try:
            return list_tasks_view(
                session,
                project,
                feature_key=feature_key,
                status=status,
                limit=page.limit,
                offset=page.offset,
            )
        except PaginationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    @app.get("/api/projects/{project_id}/documents")
    def get_documents(
        project_id: int,
        path: str | None = Query(default=None),
        page: PageParams = Depends(_pagination),  # noqa: B008 — dépendance FastAPI
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        payload = build_documents_view(
            session,
            project,
            root=app.state.project_root,
            docs_dir=app.state.docs_dir,
            config=app.state.config_data,
        )
        if path:
            try:
                payload["selected"] = read_document(
                    project,
                    path,
                    root=app.state.project_root,
                )
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail="document introuvable") from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        documents = payload["documents"]
        if isinstance(documents, list):
            total = len(documents)
            payload["documents"] = documents[page.offset : page.offset + page.limit]
            payload["total"] = total
            payload["limit"] = page.limit
            payload["offset"] = page.offset
            payload["has_more"] = page.offset + len(payload["documents"]) < total
            payload["next_offset"] = (
                page.offset + len(payload["documents"])
                if payload["has_more"]
                else None
            )
        return payload

    @app.get("/api/projects/{project_id}/documents/content")
    def get_document_content(
        project_id: int,
        path: str = Query(min_length=1),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> dict[str, object]:
        project = _project(session, project_id)
        try:
            return read_document(project, path, root=app.state.project_root)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="document introuvable") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    @app.get("/api/projects/{project_id}/export")
    def get_export(
        project_id: int,
        format: Literal["json", "csv"] = Query(default="json"),
        session: Session = Depends(_session),  # noqa: B008 — dépendance FastAPI
    ) -> Response:
        project = _project(session, project_id)
        result = build_export(
            session,
            project,
            format=format,
            config=app.state.config_data,
        )
        return Response(
            content=result.content,
            media_type=result.media_type,
            headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
        )

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

    if app.state.static_dir is not None:
        app.mount(
            "/",
            StaticFiles(directory=str(app.state.static_dir), html=True),
            name="frontend",
        )
    return app


app = create_app()
