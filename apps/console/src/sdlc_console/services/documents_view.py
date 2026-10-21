"""Vue Documentation : inventaire, fraîcheur, lecture sûre et génération."""

from __future__ import annotations

import html
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import Project
from ..paths import PathSecurityError, is_secret_path, resolve_within

GENERATED_NOTICE = "Fichier généré, ne pas modifier."
DEFAULT_REVIEW_DAYS = 90
MAX_DOCUMENT_BYTES = 200_000
READABLE_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".json", ".yaml", ".yml"}


@dataclass(frozen=True)
class DocumentSpec:
    key: str
    label: str
    patterns: tuple[str, ...]
    required: bool = True


DOCUMENT_SPECS: tuple[DocumentSpec, ...] = (
    DocumentSpec("brief", "Brief", ("docs/00-cadrage/brief.md",)),
    DocumentSpec(
        "exigences",
        "Exigences non fonctionnelles",
        ("docs/00-cadrage/exigences-nf.md",),
    ),
    DocumentSpec("adr", "ADR", ("docs/architecture/adr/*.md",)),
    DocumentSpec("specs", "Specs OpenSpec", ("openspec/changes/*/specs/*/spec.md",)),
    DocumentSpec("recette", "Recette", ("docs/recette/*.md",)),
    DocumentSpec("runbook", "Runbook", ("docs/ops/runbook.md",)),
    DocumentSpec("incidents", "Incidents", ("docs/incidents/*.md",)),
    DocumentSpec("release_notes", "Notes de version", ("docs/release-notes/*.md",)),
)


def _iso(value: datetime) -> str:
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()


def _review_days(config: Mapping[str, Any] | None) -> int:
    config = config or {}
    documentation = config.get("documentation")
    documentation = documentation if isinstance(documentation, Mapping) else {}
    docs = config.get("docs")
    docs = docs if isinstance(docs, Mapping) else {}
    value = documentation.get("freshness_days", docs.get("freshness_days", DEFAULT_REVIEW_DAYS))
    return int(value) if isinstance(value, int) and value > 0 else DEFAULT_REVIEW_DAYS


def _config_path(config: Mapping[str, Any] | None, key: str, default: str) -> str:
    config = config or {}
    paths = config.get("paths")
    paths = paths if isinstance(paths, Mapping) else {}
    value = paths.get(key)
    return str(value) if isinstance(value, str) and value else default


def _generated(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return False
    return (
        relative.startswith("reports/")
        or relative.startswith("docs/suivi")
        or (relative.startswith("docs/") and relative.endswith(".html"))
    )


def _regenerate_url(relative: str, project_id: int) -> str | None:
    if relative.startswith("docs/suivi"):
        return f"/api/projects/{project_id}/suivi?format=json"
    return None


def _document_data(
    path: Path,
    *,
    root: Path,
    project_id: int,
    review_days: int,
    now: datetime,
) -> dict[str, Any]:
    stat = path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
    age_days = round((now - modified).total_seconds() / 86400, 1)
    relative = path.relative_to(root).as_posix()
    generated = _generated(path, root)
    stale = age_days > review_days
    return {
        "path": relative,
        "label": path.name,
        "exists": True,
        "status": "stale" if stale else "fresh",
        "updated_at": _iso(modified),
        "age_days": age_days,
        "review_days": review_days,
        "generated": generated,
        "editable": not generated,
        "notice": GENERATED_NOTICE if generated else None,
        "regenerate_url": _regenerate_url(relative, project_id) if generated else None,
        "link": f"/api/projects/{project_id}/documents?path={html.escape(relative, quote=True)}",
    }


def _configured_specs(
    config: Mapping[str, Any] | None,
    docs_dir: Path | None,
) -> tuple[DocumentSpec, ...]:
    # Les chemins documentaires restent des valeurs par défaut explicites ; un
    # projet peut les déplacer via paths.* sans jamais sortir de sa racine.
    specs: list[DocumentSpec] = []
    for spec in DOCUMENT_SPECS:
        patterns = list(spec.patterns)
        if docs_dir is not None and spec.patterns and spec.patterns[0].startswith("docs/"):
            patterns = [
                str(docs_dir / pattern.removeprefix("docs/")) for pattern in patterns
            ]
        specs.append(DocumentSpec(spec.key, spec.label, tuple(patterns), spec.required))
    return tuple(specs)


def build_documents_view(
    session: Session,
    project: Project,
    *,
    root: str | Path | None = None,
    docs_dir: str | Path | None = None,
    config: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Liste les documents attendus, leur fraîcheur et leur statut."""
    root_path = Path(root or Path.cwd()).resolve()
    docs_path = Path(docs_dir).resolve() if docs_dir is not None else None
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    review_days = _review_days(config)
    documents: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for spec in _configured_specs(config, docs_path):
        found = False
        for pattern in spec.patterns:
            candidate = Path(pattern)
            if candidate.is_absolute():
                matches = sorted(candidate.parent.glob(candidate.name))
            else:
                matches = sorted(root_path.glob(pattern))
            for path in matches:
                try:
                    resolved = resolve_within(root_path, path)
                except (PathSecurityError, FileNotFoundError, OSError):
                    continue
                if not resolved.is_file() or is_secret_path(resolved):
                    continue
                data = _document_data(
                    resolved,
                    root=root_path,
                    project_id=project.id,
                    review_days=review_days,
                    now=moment,
                )
                data["key"] = spec.key
                data["label"] = spec.label
                documents.append(data)
                seen_paths.add(data["path"])
                found = True
        if not found and spec.required:
            documents.append(
                {
                    "key": spec.key,
                    "label": spec.label,
                    "path": spec.patterns[0],
                    "exists": False,
                    "status": "missing",
                    "updated_at": None,
                    "age_days": None,
                    "review_days": review_days,
                    "generated": False,
                    "editable": False,
                    "notice": None,
                    "regenerate_url": None,
                    "link": None,
                }
            )

    for pattern in ("docs/suivi.html", "docs/suivi-*.html", "docs/suivi/*.json", "reports/gates/*.json"):
        for path in sorted(root_path.glob(pattern)):
            try:
                resolved = resolve_within(root_path, path)
            except (PathSecurityError, FileNotFoundError, OSError):
                continue
            if not resolved.is_file() or is_secret_path(resolved):
                continue
            data = _document_data(
                resolved,
                root=root_path,
                project_id=project.id,
                review_days=review_days,
                now=moment,
            )
            if data["path"] in seen_paths:
                continue
            data["key"] = "generated"
            data["label"] = "Document généré"
            documents.append(data)
            seen_paths.add(data["path"])

    present = [item for item in documents if item["exists"]]
    return {
        "generated_at": _iso(moment),
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "review_days": review_days,
        "documents": documents,
        "summary": {
            "expected": len(documents),
            "present": len(present),
            "missing": sum(1 for item in documents if item["status"] == "missing"),
            "stale": sum(1 for item in documents if item["status"] == "stale"),
            "generated": sum(1 for item in documents if item["generated"]),
        },
        "sources": {
            "documents": "docs/",
            "specs": "openspec/",
            "reports": "reports/",
            "paths": "sdlc.config.yaml paths.*",
        },
    }


def read_document(
    project: Project,
    path: str | Path,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Lit un document Markdown/texte dans le périmètre, sans HTML interprété."""
    root_path = Path(root or Path.cwd()).resolve()
    try:
        target = resolve_within(root_path, path)
    except PathSecurityError as exc:
        raise ValueError(str(exc)) from exc
    if not target.is_file():
        raise FileNotFoundError(target)
    if is_secret_path(target):
        raise ValueError("lecture de secret refusée")
    if target.suffix.lower() not in READABLE_SUFFIXES:
        raise ValueError("format de document non supporté")
    raw = target.read_bytes()
    truncated = len(raw) > MAX_DOCUMENT_BYTES
    text = raw[:MAX_DOCUMENT_BYTES].decode("utf-8", errors="replace")
    relative = target.relative_to(root_path).as_posix()
    generated = _generated(target, root_path)
    return {
        "path": relative,
        "label": target.name,
        "markdown": text if target.suffix.lower() in {".md", ".markdown"} else None,
        "text": text,
        "truncated": truncated,
        "generated": generated,
        "editable": not generated,
        "notice": GENERATED_NOTICE if generated else None,
        "regenerate_url": _regenerate_url(relative, project.id) if generated else None,
        "html_disabled": True,
        "size_bytes": len(raw),
    }
