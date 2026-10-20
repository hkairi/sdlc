"""Confine les chemins d'ingestion au périmètre du projet.

Refuse les chemins hors racine, les traversées `..`, les liens symboliques qui
sortent du périmètre et les fichiers de secrets.
"""

from __future__ import annotations

from pathlib import Path

SECRET_SUFFIXES = (".pem", ".key")
SECRET_NAMES = {".env"}


class PathSecurityError(ValueError):
    """Chemin refusé par la politique de sécurité."""


def is_secret_path(path: Path) -> bool:
    """Vrai si le chemin désigne un secret à ne jamais lire."""
    if path.name in SECRET_NAMES or path.name.startswith(".env."):
        return True
    if path.name.endswith(SECRET_SUFFIXES):
        return True
    return "secrets" in path.parts


def resolve_within(
    root: str | Path,
    candidate: str | Path,
    *,
    allow_missing: bool = False,
) -> Path:
    """Résout `candidate` dans `root` et refuse toute sortie du périmètre."""
    root_path = Path(root).resolve()
    raw = Path(candidate)
    target = (raw if raw.is_absolute() else root_path / raw).resolve()

    if not target.is_relative_to(root_path):
        raise PathSecurityError(f"chemin hors périmètre : {candidate}")
    if is_secret_path(target):
        raise PathSecurityError(f"lecture de secret refusée : {target}")
    if not allow_missing and not target.exists():
        raise FileNotFoundError(target)
    return target
