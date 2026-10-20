"""Utilitaires de normalisation partagés par les collecteurs."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse


def as_mapping(value: Any) -> Mapping[str, Any]:
    """Renvoie un mapping ou un dictionnaire vide si la valeur est absente."""
    return value if isinstance(value, Mapping) else {}


def parse_datetime(value: Any) -> datetime | None:
    """Convertit une date ISO ou un horodatage Unix en datetime UTC, ou None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def as_int(value: Any) -> int | None:
    """Convertit une valeur numérique fournisseur en entier, ou None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def repository_path_from_url(url: str) -> str:
    """Extrait `groupe/projet` d'une URL GitLab ou GitHub."""
    if "://" not in url and "@" in url and ":" in url:
        path = url.split(":", 1)[1].strip("/")
    else:
        path = urlparse(url).path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path


def repository_owner_and_name(url: str) -> tuple[str, str]:
    """Extrait `(owner, nom)` d'une URL GitHub."""
    path = repository_path_from_url(url)
    parts = path.split("/")
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[1]
