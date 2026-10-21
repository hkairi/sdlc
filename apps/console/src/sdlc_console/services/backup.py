"""Sauvegarde et restauration globales du fichier SQLite."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import utc_now

BACKUP_SUFFIX = ".sqlite3"
MANIFEST_SUFFIX = ".json"


class BackupError(ValueError):
    """Sauvegarde ou restauration impossible."""


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def database_path_from_session(session: Session) -> Path:
    """Retourne le fichier SQLite de la session, jamais une URL distante."""
    bind = session.get_bind()
    url = getattr(bind, "url", None)
    if url is None:
        url = getattr(getattr(bind, "engine", None), "url", None)
    if url is None or url.get_backend_name() != "sqlite":
        raise BackupError("la sauvegarde globale exige une base SQLite")
    database = url.database
    if not database or database == ":memory:":
        raise BackupError("la base SQLite en mémoire n'est pas sauvegardable")
    path = Path(database)
    if not path.is_file():
        raise BackupError(f"fichier SQLite introuvable : {path}")
    return path.resolve()


def _manifest_path(backup_path: Path) -> Path:
    return backup_path.with_suffix(MANIFEST_SUFFIX)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity(path: Path) -> bool:
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return False
    return bool(row and row[0] == "ok")


def _write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError(f"manifeste de sauvegarde illisible : {path}") from exc
    if not isinstance(data, dict):
        raise BackupError(f"manifeste de sauvegarde invalide : {path}")
    return data


def backup_database(
    session: Session,
    *,
    backups_dir: str | Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Copie le fichier SQLite complet avec l'API de sauvegarde SQLite."""
    source_path = database_path_from_session(session)
    target_dir = Path(backups_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    moment = _aware(now) or utc_now()
    backup_id = f"{moment.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    backup_path = target_dir / f"{backup_id}{BACKUP_SUFFIX}"
    temporary = backup_path.with_suffix(".tmp")
    try:
        source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
        destination = sqlite3.connect(temporary)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        temporary.replace(backup_path)
    except sqlite3.Error as exc:
        temporary.unlink(missing_ok=True)
        raise BackupError(f"sauvegarde SQLite impossible : {exc}") from exc
    if not _integrity(backup_path):
        backup_path.unlink(missing_ok=True)
        raise BackupError("la sauvegarde produite échoue au contrôle d'intégrité")
    manifest = {
        "id": backup_id,
        "created_at": _iso(moment),
        "source": str(source_path),
        "backup_path": str(backup_path),
        "sha256": _sha256(backup_path),
        "size_bytes": backup_path.stat().st_size,
        "verified": True,
        "verified_at": _iso(moment),
        "restore_tested": False,
        "restore_tested_at": None,
    }
    _write_manifest(_manifest_path(backup_path), manifest)
    return manifest


def verify_backup(path: str | Path) -> dict[str, Any]:
    """Vérifie l'intégrité SQLite et l'empreinte du manifeste."""
    backup_path = Path(path).resolve()
    if backup_path.suffix == MANIFEST_SUFFIX:
        manifest = _read_manifest(backup_path)
        backup_path = Path(str(manifest.get("backup_path") or backup_path.with_suffix(BACKUP_SUFFIX)))
    if not backup_path.is_file():
        raise BackupError(f"sauvegarde introuvable : {backup_path}")
    manifest_path = _manifest_path(backup_path)
    manifest = _read_manifest(manifest_path) if manifest_path.is_file() else {
        "id": backup_path.stem,
        "backup_path": str(backup_path),
        "created_at": _iso(datetime.fromtimestamp(backup_path.stat().st_mtime, tz=UTC)),
        "restore_tested": False,
    }
    integrity = _integrity(backup_path)
    digest = _sha256(backup_path)
    expected = manifest.get("sha256")
    verified = bool(integrity and (expected is None or digest == expected))
    manifest.update(
        {
            "backup_path": str(backup_path),
            "sha256": digest,
            "size_bytes": backup_path.stat().st_size,
            "verified": verified,
            "verified_at": _iso(utc_now()),
        }
    )
    _write_manifest(manifest_path, manifest)
    if not verified:
        raise BackupError("sauvegarde invalide : intégrité ou empreinte incorrecte")
    return manifest


def restore_backup(
    source: str | Path,
    target: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Restaure une sauvegarde vérifiée dans un nouveau fichier SQLite."""
    manifest = verify_backup(source)
    source_path = Path(str(manifest["backup_path"]))
    target_path = Path(target).resolve()
    if target_path.exists() and not overwrite:
        raise BackupError(f"la cible existe déjà : {target_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = target_path.with_suffix(".restore.tmp")
    try:
        source_connection = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
        target_connection = sqlite3.connect(temporary)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()
        temporary.replace(target_path)
    except sqlite3.Error as exc:
        temporary.unlink(missing_ok=True)
        raise BackupError(f"restauration SQLite impossible : {exc}") from exc
    if not _integrity(target_path):
        raise BackupError("la restauration échoue au contrôle d'intégrité")
    manifest["restore_tested"] = True
    manifest["restore_tested_at"] = _iso(utc_now())
    manifest["restored_to"] = str(target_path)
    _write_manifest(_manifest_path(source_path), manifest)
    return manifest


def backup_status(path: str | Path) -> dict[str, Any]:
    """Renvoie l'âge et l'état de la dernière sauvegarde vérifiée."""
    backup_path = Path(path).resolve()
    if backup_path.suffix == MANIFEST_SUFFIX:
        manifest = _read_manifest(backup_path)
        backup_path = Path(str(manifest.get("backup_path") or backup_path.with_suffix(BACKUP_SUFFIX)))
    if not backup_path.is_file():
        raise BackupError(f"sauvegarde introuvable : {backup_path}")
    manifest = verify_backup(backup_path)
    created = _aware(datetime.fromisoformat(str(manifest["created_at"]))) or utc_now()
    age_hours = round((utc_now() - created).total_seconds() / 3600, 2)
    return {**manifest, "age_hours": age_hours, "fresh": age_hours <= 24}


def list_backups(backups_dir: str | Path) -> dict[str, Any]:
    """Liste les sauvegardes, leur âge et leur état de vérification."""
    directory = Path(backups_dir).resolve()
    records: list[dict[str, Any]] = []
    if directory.is_dir():
        for manifest_path in sorted(directory.glob(f"*{MANIFEST_SUFFIX}")):
            try:
                manifest = _read_manifest(manifest_path)
                backup_path = Path(str(manifest.get("backup_path") or manifest_path.with_suffix(BACKUP_SUFFIX)))
                if not backup_path.is_file():
                    continue
                created = _aware(datetime.fromisoformat(str(manifest.get("created_at"))))
                age_hours = round((utc_now() - created).total_seconds() / 3600, 2) if created else None
                records.append(
                    {
                        **manifest,
                        "age_hours": age_hours,
                        "fresh": age_hours is not None and age_hours <= 24,
                    }
                )
            except (BackupError, ValueError):
                continue
    records.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {
        "backups": records,
        "total": len(records),
        "latest": records[0] if records else None,
        "latest_age_hours": records[0].get("age_hours") if records else None,
        "latest_fresh": records[0].get("fresh") if records else None,
        "sources": {"backups": str(directory)},
    }
