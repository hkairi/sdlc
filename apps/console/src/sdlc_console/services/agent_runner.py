"""Runner d'agents local : préflight, file, concurrence et lancement."""

from __future__ import annotations

import contextlib
import os
import shlex
import shutil
import signal
import subprocess
import threading
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Project, Repository, TaskRun, utc_now
from ..paths import is_secret_path
from ..redaction import redact, redact_log_file
from .agent_sandbox import audit_git_refusals, install_git_guard

RUN_STATUSES = frozenset({"queued", "running", "done", "failed", "timeout", "cancelled"})


class RunPreflightError(ValueError):
    """Le lancement ne respecte pas les règles de préflight."""


@dataclass(frozen=True)
class RunPlan:
    agent_id: str
    model: str
    role: str
    task_key: str
    repository: Repository
    command: tuple[str, ...]
    budget_eur: float | None
    timeout_seconds: int
    max_concurrency: int
    read_only: bool = False
    errors: tuple[str, ...] = field(default_factory=tuple)


def _agent_config(config: Mapping[str, Any] | None, agent_id: str) -> Mapping[str, Any]:
    agents = (config or {}).get("agents")
    if not isinstance(agents, Mapping):
        return {}
    raw = agents.get(agent_id)
    return raw if isinstance(raw, Mapping) else {}


def _model_config(agent: Mapping[str, Any], model: str) -> Mapping[str, Any]:
    models = agent.get("models")
    if not isinstance(models, Mapping):
        return {}
    raw = models.get(model)
    return raw if isinstance(raw, Mapping) else {}


def _as_command(value: Any) -> list[str]:
    if isinstance(value, str):
        return shlex.split(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(item) for item in value]
    return []


def _format_command(command: Sequence[str], context: Mapping[str, str]) -> tuple[str, ...]:
    values = [item.format_map(context) for item in command]
    return tuple(values)


def prepare_run(
    session: Session,
    project: Project,
    *,
    agent_id: str,
    model: str,
    role: str,
    task_key: str,
    repository_id: int,
    budget_eur: float | None = None,
    timeout_seconds: int | None = None,
    config: Mapping[str, Any] | None = None,
) -> RunPlan:
    """Vérifie la CLI, le modèle, le dépôt, le budget et la durée avant exécution."""
    agent = _agent_config(config, agent_id)
    model_config = _model_config(agent, model)
    errors: list[str] = []
    if not agent.get("enabled", False):
        errors.append(f"agent désactivé ou inconnu : {agent_id}")
    if not model_config and not model:
        errors.append(f"modèle inconnu : {model}")
    repository = session.get(Repository, repository_id)
    if repository is None or repository.project_id != project.id:
        errors.append(f"dépôt hors projet : {repository_id}")
        repository = None
    elif is_secret_path(Path(repository.local_path)):
        errors.append(f"dépôt dans un chemin de secret : {repository.local_path}")
        repository = None
    if not task_key.strip():
        errors.append("tâche requise")
    context = {
        "agent": agent_id,
        "model": model,
        "role": role,
        "task": task_key,
        "repository": repository.local_path if repository else "",
        "budget_eur": str(budget_eur or ""),
    }
    command = _as_command(model_config.get("command"))
    if not command and agent.get("cli"):
        command = [str(agent["cli"]), model]
    command = list(_format_command(command, context))
    if not command:
        errors.append("modèle sans commande configurée")
    elif shutil.which(command[0]) is None:
        errors.append(f"CLI introuvable : {command[0]}")
    max_budget = model_config.get("max_cost_eur", (config or {}).get("review", {}).get("max_cost_eur"))
    if budget_eur is not None and isinstance(max_budget, (int, float)) and budget_eur > max_budget:
        errors.append(f"budget {budget_eur} € > plafond {max_budget} €")
    duration = timeout_seconds or int(model_config.get("timeout_seconds", 300))
    if duration <= 0:
        errors.append("durée maximale invalide")
    runner = (config or {}).get("runner")
    runner = runner if isinstance(runner, Mapping) else {}
    max_concurrency = int(
        model_config.get("max_concurrency")
        or runner.get("max_concurrency")
        or 1
    )
    return RunPlan(
        agent_id=agent_id,
        model=model,
        role=role,
        task_key=task_key.strip(),
        repository=repository,  # type: ignore[arg-type]
        command=tuple(command),
        budget_eur=budget_eur,
        timeout_seconds=duration,
        max_concurrency=min(max_concurrency, 16),
        read_only=role == "reviewer",
        errors=tuple(errors),
    )


def _running(session: Session, project: Project, agent_id: str) -> int:
    return int(
        session.scalar(
            select(func.count(TaskRun.id)).where(
                TaskRun.project_id == project.id,
                TaskRun.agent_id == agent_id,
                TaskRun.status == "running",
            )
        )
        or 0
    )


def _log_path(root: Path, run_id: str) -> Path:
    directory = root / "reports" / "runs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{run_id}.log"


def _pump_log(stream: BinaryIO, handle: TextIO) -> None:
    """Recopie la sortie brute en redactant chaque ligne avant écriture."""
    try:
        for line in iter(stream.readline, b""):
            handle.write(redact(line.decode("utf-8", errors="replace")))
            handle.flush()
    finally:
        handle.close()
        stream.close()


def _start_run(
    session: Session,
    project: Project,
    run: TaskRun,
    plan: RunPlan,
    *,
    root: Path,
) -> None:
    log_path = _log_path(root, run.run_id)
    env, _audit_path, guard = install_git_guard(
        root,
        run.run_id,
        base_env=os.environ,
        read_only=run.role == "reviewer",
    )
    command = list(plan.command)
    if guard is not None and Path(command[0]).name == "git":
        command[0] = str(guard)
    handle = log_path.open("a", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=plan.repository.local_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )
    assert process.stdout is not None
    threading.Thread(
        target=_pump_log,
        args=(process.stdout, handle),
        name=f"sdlc-log-{run.run_id}",
        daemon=True,
    ).start()
    run.status = "running"
    run.pid = process.pid
    run.process_group = process.pid
    run.log_path = str(log_path)
    run.started_at = utc_now()
    session.flush()


def enqueue_run(
    session: Session,
    project: Project,
    *,
    agent_id: str,
    model: str,
    role: str,
    task_key: str,
    repository_id: int,
    budget_eur: float | None = None,
    timeout_seconds: int | None = None,
    config: Mapping[str, Any] | None = None,
    root: str | Path | None = None,
) -> TaskRun:
    """Crée un run en file, puis démarre ceux qui ont un slot disponible."""
    plan = prepare_run(
        session,
        project,
        agent_id=agent_id,
        model=model,
        role=role,
        task_key=task_key,
        repository_id=repository_id,
        budget_eur=budget_eur,
        timeout_seconds=timeout_seconds,
        config=config,
    )
    if plan.errors:
        raise RunPreflightError(" ; ".join(plan.errors))
    run = TaskRun(
        project_id=project.id,
        run_id=f"run-{uuid.uuid4().hex[:16]}",
        task_key=plan.task_key,
        agent_id=plan.agent_id,
        primary_repository_id=plan.repository.id,
        model=plan.model,
        role=plan.role,
        status="queued",
        budget_eur=plan.budget_eur,
        timeout_seconds=plan.timeout_seconds,
        origin="lancée",
        imported_at=utc_now(),
    )
    session.add(run)
    session.flush()
    dispatch_queue(
        session,
        project,
        agent_id=agent_id,
        config=config,
        root=root,
    )
    return run


def dispatch_queue(
    session: Session,
    project: Project,
    *,
    agent_id: str | None = None,
    config: Mapping[str, Any] | None = None,
    root: str | Path | None = None,
) -> list[TaskRun]:
    """Démarre les runs en file dans la limite de concurrence."""
    root_path = Path(root or Path.cwd()).resolve()
    query = select(TaskRun).where(
        TaskRun.project_id == project.id,
        TaskRun.status == "queued",
    )
    if agent_id:
        query = query.where(TaskRun.agent_id == agent_id)
    queued = list(session.scalars(query.order_by(TaskRun.id)).all())
    started: list[TaskRun] = []
    for run in queued:
        plan = prepare_run(
            session,
            project,
            agent_id=run.agent_id or "",
            model=run.model or "",
            role=run.role or "executor",
            task_key=run.task_key or "",
            repository_id=run.primary_repository_id or 0,
            budget_eur=run.budget_eur,
            timeout_seconds=None,
            config=config,
        )
        if plan.errors:
            run.status = "failed"
            run.exit_code = 1
            run.ended_at = utc_now()
            continue
        if _running(session, project, run.agent_id or "") >= plan.max_concurrency:
            continue
        _start_run(session, project, run, plan, root=root_path)
        started.append(run)
    session.flush()
    return started


def _audit_git_attempts(session: Session, run: TaskRun) -> None:
    if not run.log_path:
        return
    redact_log_file(run.log_path)
    project = session.get(Project, run.project_id)
    if project is None:
        return
    root = Path(run.log_path).resolve().parents[2]
    audit_git_refusals(session, project, run, root=root)


def refresh_run(session: Session, run: TaskRun) -> TaskRun:
    """Actualise un run depuis son processus enfant, si disponible."""
    if run.status != "running" or run.pid is None:
        return run
    try:
        pid, status = os.waitpid(run.pid, os.WNOHANG)
    except ChildProcessError:
        return run
    if pid == 0:
        if run.started_at is not None:
            started = (
                run.started_at.replace(tzinfo=UTC)
                if run.started_at.tzinfo is None
                else run.started_at.astimezone(UTC)
            )
            limit = run.timeout_seconds or 3600
            if (datetime.now(UTC) - started).total_seconds() > limit:
                if run.process_group:
                    with contextlib.suppress(ProcessLookupError, PermissionError):
                        os.killpg(run.process_group, signal.SIGTERM)
                with contextlib.suppress(ChildProcessError):
                    os.waitpid(run.pid, 0)
                run.status = "timeout"
                run.ended_at = utc_now()
                _audit_git_attempts(session, run)
        return run
    exit_code = os.waitstatus_to_exitcode(status)
    run.exit_code = exit_code
    run.status = "done" if exit_code == 0 else "failed"
    run.ended_at = utc_now()
    _audit_git_attempts(session, run)
    session.flush()
    return run


def cancel_run(session: Session, run: TaskRun) -> TaskRun:
    """Annule un run en file ou en cours."""
    if run.status == "queued":
        run.status = "cancelled"
        run.ended_at = utc_now()
    elif run.status == "running":
        run.cancel_requested = True
        if run.process_group:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(run.process_group, signal.SIGTERM)
        run.status = "cancelled"
        run.ended_at = utc_now()
        _audit_git_attempts(session, run)
    session.flush()
    return run
