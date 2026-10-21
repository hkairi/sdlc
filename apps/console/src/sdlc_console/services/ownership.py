"""Bus factor et propriété par zone à partir de CODEOWNERS et de l'historique."""

from __future__ import annotations

import fnmatch
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Commit, Person, PersonIdentity, Project, Repository, utc_now
from .aggregation import aggregate_commits
from .projects import list_repositories

DEFAULT_WINDOW_DAYS = 90


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


@dataclass(frozen=True)
class CodeownerRule:
    repository_id: int
    pattern: str
    owners: tuple[str, ...]
    source: str


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def parse_codeowners(
    text: str,
    *,
    repository_id: int,
    source: str = "CODEOWNERS",
) -> tuple[CodeownerRule, ...]:
    """Parse un fichier CODEOWNERS (sections GitLab ignorées)."""
    rules: list[CodeownerRule] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("["):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0]
        owners = tuple(owner.lstrip("@") for owner in parts[1:] if owner)
        if pattern and owners:
            rules.append(
                CodeownerRule(
                    repository_id=repository_id,
                    pattern=pattern,
                    owners=owners,
                    source=source,
                )
            )
    return tuple(rules)


def _codeowner_files(repository: Repository) -> list[Path]:
    root = Path(repository.local_path)
    candidates = [
        root / "CODEOWNERS",
        root / ".github" / "CODEOWNERS",
        root / "docs" / "CODEOWNERS",
    ]
    return [path for path in candidates if path.is_file()]


def discover_codeowners(
    repositories: Sequence[Repository],
) -> tuple[CodeownerRule, ...]:
    rules: list[CodeownerRule] = []
    for repository in repositories:
        for path in _codeowner_files(repository):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            rules.extend(
                parse_codeowners(
                    text,
                    repository_id=repository.id,
                    source=_relative(path, Path(repository.local_path)),
                )
            )
    return tuple(rules)


def _owner_map(session: Session, project: Project) -> tuple[dict[str, Person], dict[str, Person]]:
    by_email: dict[str, Person] = {}
    by_external: dict[str, Person] = {}
    identities = list(
        session.scalars(
            select(PersonIdentity).where(PersonIdentity.project_id == project.id)
        ).all()
    )
    for identity in identities:
        person = identity.person
        if person is None or person.is_bot:
            continue
        if identity.email:
            by_email[identity.email.casefold()] = person
        if identity.external_id:
            by_external[identity.external_id.casefold()] = person
    return by_email, by_external


def _resolve_owner(
    owner: str,
    persons_by_name: Mapping[str, Person],
    by_email: Mapping[str, Person],
    by_external: Mapping[str, Person],
) -> Person | None:
    key = owner.lstrip("@").casefold()
    return (
        by_email.get(key)
        or by_external.get(key)
        or persons_by_name.get(key)
    )


def _match(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    candidate = pattern.replace("\\", "/").lstrip("/")
    if candidate.endswith("/"):
        return normalized.startswith(candidate) or normalized == candidate.rstrip("/")
    if fnmatch.fnmatch(normalized, candidate):
        return True
    if "/" not in candidate:
        return fnmatch.fnmatch(normalized.rsplit("/", 1)[-1], candidate)
    return False


def _files(commit: Commit) -> list[str]:
    try:
        value = json.loads(commit.files_json)
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _bus_factor(person_commits: Mapping[int, int]) -> int | None:
    total = sum(person_commits.values())
    if total == 0:
        return None
    cumulative = 0
    for index, count in enumerate(
        sorted(person_commits.values(), reverse=True),
        start=1,
    ):
        cumulative += count
        if cumulative * 100 >= total * 50:
            return index
    return None


def build_ownership(
    session: Session,
    project: Project,
    *,
    repository_ids: Sequence[int] | None = None,
    codeowners_paths: Sequence[str | Path] | None = None,
    window_days: int | None = DEFAULT_WINDOW_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calcule le bus factor et les propriétaires par zone CODEOWNERS."""
    repositories = list_repositories(session, project)
    if repository_ids is not None:
        wanted = set(repository_ids)
        available = {repository.id for repository in repositories}
        missing = wanted - available
        if missing:
            raise ValueError(f"dépôts inconnus ou retirés : {sorted(missing)}")
        repositories = [repository for repository in repositories if repository.id in wanted]
    by_id = {repository.id: repository for repository in repositories}
    if codeowners_paths is not None:
        rules: list[CodeownerRule] = []
        for item in codeowners_paths:
            path = Path(item)
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            repository_id = next(iter(by_id), 0)
            rules.extend(
                parse_codeowners(
                    text,
                    repository_id=repository_id,
                    source=str(path),
                )
            )
    else:
        rules = list(discover_codeowners(repositories))
    if not rules:
        return {
            "generated_at": _iso(utc_now()),
            "project": {"id": project.id, "name": project.name, "slug": project.slug},
            "window_days": window_days,
            "zones": [],
            "alerts": [],
            "status": "not_measured",
            "sources": {"codeowners": [], "commits": "git"},
        }

    aggregation = aggregate_commits(session, project, repository_ids=[repo.id for repo in repositories])
    commits = list(
        session.scalars(
            select(Commit).where(Commit.id.in_(aggregation.unique_commit_ids))
        ).all()
    ) if aggregation.unique_commit_ids else []
    moment = now or utc_now()
    moment = moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
    cutoff = moment - timedelta(days=window_days) if window_days is not None else None
    eligible: list[Commit] = []
    for commit in commits:
        if commit.is_bot or commit.is_merge or commit.person is None or commit.person.is_bot:
            continue
        committed = (
            commit.committed_at.replace(tzinfo=UTC)
            if commit.committed_at.tzinfo is None
            else commit.committed_at.astimezone(UTC)
        )
        if cutoff is not None and committed < cutoff:
            continue
        eligible.append(commit)

    by_email, by_external = _owner_map(session, project)
    persons_by_name = {
        person.display_name.casefold(): person
        for person in session.scalars(
            select(Person).where(Person.project_id == project.id)
        ).all()
        if not person.is_bot
    }
    zones: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    for rule in rules:
        repository = by_id.get(rule.repository_id)
        if repository is None:
            continue
        zone_commits = [
            commit
            for commit in eligible
            if commit.repository_id == rule.repository_id
            and any(_match(file_name, rule.pattern) for file_name in _files(commit))
        ]
        counts: dict[int, int] = {}
        for commit in zone_commits:
            if commit.person is not None and commit.person_id is not None:
                counts[commit.person_id] = counts.get(commit.person_id, 0) + 1
        ranked: list[dict[str, Any]] = []
        for person_id, count in counts.items():
            person = session.get(Person, person_id)
            ranked.append(
                {
                    "person_id": person_id,
                    "name": person.display_name if person is not None else "inconnu",
                    "commits": count,
                    "share": round(count * 100 / len(zone_commits), 2) if zone_commits else 0.0,
                }
            )
        ranked.sort(key=lambda item: (-int(item["commits"]), str(item["name"])))
        bus = _bus_factor(counts)
        owners = [
            person
            for owner in rule.owners
            if (person := _resolve_owner(owner, persons_by_name, by_email, by_external)) is not None
        ]
        owner_names = [person.display_name for person in owners]
        zone = {
            "zone": rule.pattern,
            "repository_id": repository.id,
            "repository_name": repository.name,
            "declared_owners": list(rule.owners),
            "owners": owner_names,
            "commits": len(zone_commits),
            "bus_factor": bus,
            "risk": bus == 1,
            "primary_owner": ranked[0] if ranked else None,
            "secondary_owner": ranked[1] if len(ranked) > 1 else None,
            "persons": ranked,
            "source": f"{rule.source} + historique",
        }
        if zone_commits:
            zone["status"] = "measured"
        else:
            zone["status"] = "not_measured"
        zones.append(zone)
        if bus == 1:
            alerts.append(
                {
                    "zone": rule.pattern,
                    "repository_id": repository.id,
                    "severity": "high",
                    "message": (
                        f"bus factor 1 sur la zone {rule.pattern} : "
                        f"{ranked[0]['name'] if ranked else 'inconnu'} concentre "
                        "au moins 50 % des commits"
                    ),
                }
            )
    return {
        "generated_at": _iso(utc_now()),
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "window_days": window_days,
        "zones": zones,
        "alerts": alerts,
        "status": "measured" if any(zone["status"] == "measured" for zone in zones) else "not_measured",
        "sources": {
            "codeowners": sorted({rule.source for rule in rules}),
            "commits": "git",
        },
    }
