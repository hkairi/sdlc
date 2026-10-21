"""Construction et persistance d'un paquet de revue aveugle."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Project, ReviewPackage, utc_now
from ..paths import PathSecurityError, resolve_within
from ..redaction import redact
from ..security import verify_csp

PACKAGE_SCHEMA = 1


class ReviewPackageError(ValueError):
    """Paquet de revue invalide."""


@dataclass(frozen=True)
class ReviewPackageResult:
    record: ReviewPackage
    payload: dict[str, Any]
    path: Path


def _read_source(
    root: Path,
    path: str | Path,
    label: str,
) -> dict[str, Any]:
    try:
        source = resolve_within(root, path)
        content = source.read_text(encoding="utf-8")
    except (PathSecurityError, FileNotFoundError, OSError) as exc:
        raise ReviewPackageError(f"{label} illisible : {path} : {exc}") from exc
    cleaned = redact(content)
    return {
        "path": str(source.relative_to(root)),
        "sha256": hashlib.sha256(cleaned.encode("utf-8")).hexdigest(),
        "content": cleaned,
    }


def _fingerprint(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_review_package(
    session: Session,
    project: Project,
    *,
    task_key: str,
    feature_key: str | None = None,
    spec_paths: Sequence[str | Path] = (),
    diff: str = "",
    evidence_paths: Sequence[str | Path] = (),
    adr_paths: Sequence[str | Path] = (),
    reports_dir: str | Path = "reports/reviews",
    root: str | Path | None = None,
) -> ReviewPackageResult:
    """Construit un paquet sans récit d'auteur, avec empreinte et fichier JSON."""
    root_path = Path(root or Path.cwd()).resolve()
    if not task_key.strip():
        raise ReviewPackageError("clé de tâche requise")
    specs = [_read_source(root_path, path, "spec") for path in spec_paths]
    evidence = [_read_source(root_path, path, "preuve") for path in evidence_paths]
    adrs = [_read_source(root_path, path, "ADR") for path in adr_paths]
    diff_body = redact(diff.strip())
    if diff_body and not diff_body.startswith(("diff --git", "--- ", "+++ ")):
        raise ReviewPackageError("diff invalide : en-tête diff attendu")
    payload: dict[str, Any] = {
        "schema": PACKAGE_SCHEMA,
        "notice": "Fichier généré, ne pas modifier.",
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "task_key": task_key.strip(),
        "feature_key": feature_key,
        "blind": True,
        "excluded": ["récit de l'auteur", "notes privées", "prompts"],
        "csp": verify_csp(),
        "spec": specs,
        "diff": {
            "sha256": hashlib.sha256(diff_body.encode("utf-8")).hexdigest(),
            "content": diff_body,
        },
        "evidence": evidence,
        "adrs": adrs,
    }
    fingerprint = _fingerprint(payload)
    payload["created_at"] = utc_now().isoformat()
    payload["fingerprint"] = fingerprint
    output_dir = resolve_within(root_path, reports_dir, allow_missing=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_task = "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in task_key
    )
    path = output_dir / f"{safe_task}-{fingerprint[:12]}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    record = ReviewPackage(
        project_id=project.id,
        task_key=task_key.strip(),
        feature_key=feature_key,
        fingerprint=fingerprint,
        report_path=str(path),
        files_json=json.dumps(
            [item["path"] for item in specs + evidence + adrs],
            ensure_ascii=False,
        ),
    )
    session.add(record)
    session.flush()
    return ReviewPackageResult(record=record, payload=payload, path=path)


def list_review_packages(session: Session, project: Project) -> list[ReviewPackage]:
    return list(
        session.scalars(
            select(ReviewPackage)
            .where(ReviewPackage.project_id == project.id)
            .order_by(ReviewPackage.id.desc())
        ).all()
    )
