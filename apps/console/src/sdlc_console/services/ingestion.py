"""Ingestion Git incrémentale et idempotente.

Le dépôt est lu en lecture seule via `git log --numstat`. Les commits sont
identifiés par `(repository_id, sha)` et dédupliqués par `commit_fingerprint`.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Commit, IngestionRun, Person, Project, Repository, utc_now
from ..redaction import redact
from .people import create_person, is_bot_identity, normalize_email, resolve_person
from .projects import list_repositories, validate_git_repository

GIT_LOG_FORMAT = "%x1e%H%x1f%ae%x1f%an%x1f%aI%x1f%cI%x1f%P%x1f%B%x1f"
TRAILER_RE = re.compile(
    r"^(?P<key>Assisted-by|Co-authored-by):\s*(?P<value>.+)$",
    re.IGNORECASE | re.MULTILINE,
)
AI_AGENT_RE = re.compile(
    r"\b(claude|anthropic|codex|openai|chatgpt|gpt(?:-?\d+)?|copilot|cursor|gemini|"
    r"aider|devin|qwen|llama|mistral|deepseek|sonnet|opus|haiku|assistant)\b",
    re.IGNORECASE,
)


class GitIngestionError(RuntimeError):
    """Échec de lecture ou de compréhension d'un dépôt Git."""


@dataclass(frozen=True)
class ParsedCommit:
    """Commit normalisé extrait de `git log`."""

    sha: str
    author_email: str
    author_name: str
    authored_at: datetime
    committed_at: datetime
    parents: tuple[str, ...]
    message: str
    trailers: tuple[dict[str, str], ...]
    ai_assisted: bool
    additions: int
    deletions: int
    files_changed: int
    files: tuple[str, ...]
    is_merge: bool

    @property
    def fingerprint(self) -> str:
        return compute_commit_fingerprint(self.sha, self.author_email, self.authored_at)


def as_utc(value: datetime) -> datetime:
    """Normalise une date en UTC, en supposant UTC si elle est naïve."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def compute_commit_fingerprint(sha: str, email: str, authored_at: datetime) -> str:
    """Empreinte normative : sha + email normalisé + date d'auteur UTC ISO 8601."""
    normalized_email = normalize_email(email) if email else ""
    body = f"{sha}\n{normalized_email}\n{as_utc(authored_at).isoformat()}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def parse_trailers(message: str) -> list[dict[str, str]]:
    """Extrait les trailers `Assisted-by` et `Co-authored-by` du message."""
    return [
        {"key": match.group("key").lower(), "value": match.group("value").strip()}
        for match in TRAILER_RE.finditer(message)
    ]


def detect_ai_assisted(trailers: list[dict[str, str]]) -> bool:
    """Vrai si un trailer désigne un agent IA connu."""
    return any(AI_AGENT_RE.search(trailer["value"]) is not None for trailer in trailers)


def parse_git_log(output: str) -> list[ParsedCommit]:
    """Analyse la sortie de `git log --numstat` au format interne."""
    commits: list[ParsedCommit] = []
    for raw in output.split("\x1e"):
        if not raw.strip():
            continue
        fields = raw.split("\x1f", 6)
        if len(fields) < 7:
            continue
        sha, email, name, authored_raw, committed_raw, parents_raw, rest = fields
        if "\x1f" in rest:
            message, numstat = rest.split("\x1f", 1)
        else:
            message, numstat = rest, ""

        additions = 0
        deletions = 0
        files_changed = 0
        files: list[str] = []
        for line in numstat.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            files_changed += 1
            if parts[2].strip():
                files.append(parts[2].strip())
            if parts[0].isdigit():
                additions += int(parts[0])
            if parts[1].isdigit():
                deletions += int(parts[1])

        trailers = parse_trailers(message)
        parents = tuple(parents_raw.split())
        commits.append(
            ParsedCommit(
                sha=sha.strip(),
                author_email=normalize_email(email) if email.strip() else "",
                author_name=name.strip(),
                authored_at=as_utc(datetime.fromisoformat(authored_raw.strip())),
                committed_at=as_utc(datetime.fromisoformat(committed_raw.strip())),
                parents=parents,
                message=message.strip(),
                trailers=tuple(trailers),
                ai_assisted=detect_ai_assisted(trailers),
                additions=additions,
                deletions=deletions,
                files_changed=files_changed,
                files=tuple(files),
                is_merge=len(parents) > 1,
            )
        )
    return commits


def _run_git_log(path: Path, *, since: datetime | None, timeout: int) -> str:
    command = [
        "git",
        "-C",
        str(path),
        "-c",
        "core.quotepath=false",
        "log",
        "--all",
        "--numstat",
        "--no-renames",
        f"--format={GIT_LOG_FORMAT}",
    ]
    if since is not None:
        command.append(f"--since={as_utc(since).isoformat()}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitIngestionError(f"échec de l'exécution de git log : {exc}") from exc
    if result.returncode != 0:
        message = result.stderr.strip()[:500] or result.stdout.strip()[:500]
        raise GitIngestionError(f"git log a échoué ({result.returncode}) : {message}")
    return result.stdout


def last_ingestion(session: Session, repository: Repository, *, successful: bool = True) -> IngestionRun | None:
    """Dernière exécution d'ingestion d'un dépôt, réussie par défaut."""
    query = select(IngestionRun).where(IngestionRun.repository_id == repository.id)
    if successful:
        query = query.where(IngestionRun.status == "done")
    return session.scalar(query.order_by(IngestionRun.finished_at.desc(), IngestionRun.id.desc()))


def last_project_ingestion(session: Session, project: Project) -> IngestionRun | None:
    """Dernière ingestion réussie du projet, tous dépôts confondus."""
    return session.scalar(
        select(IngestionRun)
        .where(IngestionRun.project_id == project.id, IngestionRun.status == "done")
        .order_by(IngestionRun.finished_at.desc(), IngestionRun.id.desc())
    )


def _commit_person(session: Session, repository: Repository, item: ParsedCommit) -> Person:
    if item.author_email:
        return resolve_person(
            session,
            repository.project,
            email=item.author_email,
            display_name=item.author_name or item.author_email,
        )
    return create_person(
        session,
        repository.project,
        display_name=item.author_name or "inconnu",
        is_bot=is_bot_identity(None, item.author_name),
    )


def ingest_repository(
    session: Session,
    repository: Repository,
    *,
    since: datetime | None = None,
    full: bool = False,
    timeout: int = 300,
) -> IngestionRun:
    """Ingère un dépôt et renvoie l'exécution associée.

    Par défaut, l'ingestion reprend depuis la dernière exécution réussie avec
    un jour de recouvrement. `full=True` force une lecture complète ; `since`
    impose une date de départ explicite.
    """
    if repository.retired_at is not None:
        raise GitIngestionError("un dépôt retiré ne peut pas être ingéré")

    if since is None and not full:
        previous = last_ingestion(session, repository)
        if previous is not None and previous.finished_at is not None:
            since = as_utc(previous.finished_at) - timedelta(days=1)

    run = IngestionRun(
        project_id=repository.project_id,
        repository_id=repository.id,
        source="git",
        started_at=utc_now(),
        status="running",
    )
    session.add(run)
    session.flush()

    try:
        path = validate_git_repository(repository.local_path)
        output = _run_git_log(path, since=since, timeout=timeout)
        parsed = parse_git_log(output)
        inserted = 0
        skipped = 0
        with session.begin_nested():
            for item in parsed:
                existing = session.scalar(
                    select(Commit).where(
                        Commit.repository_id == repository.id,
                        Commit.sha == item.sha,
                    )
                )
                if existing is not None:
                    skipped += 1
                    continue
                person = _commit_person(session, repository, item)
                session.add(
                    Commit(
                        repository_id=repository.id,
                        sha=item.sha,
                        person_id=person.id,
                        author_name=item.author_name,
                        author_email=item.author_email,
                        authored_at=item.authored_at,
                        committed_at=item.committed_at,
                        additions=item.additions,
                        deletions=item.deletions,
                        files_changed=item.files_changed,
                        files_json=json.dumps(list(item.files), ensure_ascii=False),
                        is_merge=item.is_merge,
                        is_bot=person.is_bot,
                        ai_assisted=item.ai_assisted,
                        trailers_json=json.dumps(
                            list(item.trailers),
                            sort_keys=True,
                            ensure_ascii=False,
                        ),
                        commit_fingerprint=item.fingerprint,
                        message=item.message,
                    )
                )
                inserted += 1
        total = session.scalar(
            select(func.count(Commit.id)).where(Commit.repository_id == repository.id)
        )
        run.status = "done"
        run.finished_at = utc_now()
        run.stats_json = redact(
            json.dumps(
                {
                    "scanned": len(parsed),
                    "inserted": inserted,
                    "skipped": skipped,
                    "total": int(total or 0),
                },
                sort_keys=True,
            )
        )
        session.flush()
        return run
    except Exception as exc:  # noqa: BLE001 - on conserve l'échec dans le run
        run.status = "failed"
        run.finished_at = utc_now()
        run.error = redact(str(exc))[:2000]
        run.stats_json = redact(
            json.dumps({"error": str(exc)[:500]}, ensure_ascii=False)
        )
        session.flush()
        if isinstance(exc, GitIngestionError):
            raise
        raise GitIngestionError(str(exc)) from exc


def ingest_project(
    session: Session,
    project: Project,
    *,
    full: bool = False,
    timeout: int = 300,
) -> list[IngestionRun]:
    """Ingère tous les dépôts actifs d'un projet."""
    return [
        ingest_repository(session, repository, full=full, timeout=timeout)
        for repository in list_repositories(session, project)
    ]
