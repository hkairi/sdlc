"""Chargement et validation de `sdlc.config.yaml`.

Le schéma JSON embarqué (`config.schema.json`) est la référence. Le chargement
échoue explicitement si le fichier est absent, si le YAML est invalide ou si une
clé obligatoire manque.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

DEFAULT_CONFIG_PATH = Path("sdlc.config.yaml")
SCHEMA_PATH = Path(__file__).with_name("config.schema.json")


class ConfigError(ValueError):
    """Erreur de configuration lisible par l'utilisateur."""


@dataclass(frozen=True)
class Config:
    """Configuration validée."""

    data: dict[str, Any]
    path: Path

    @property
    def project_name(self) -> str:
        project = self.data.get("project") or {}
        return str(project.get("name", ""))

    @property
    def confidentiality(self) -> str:
        return str(self.data.get("confidentiality", ""))


def load_schema(path: Path | None = None) -> dict[str, Any]:
    """Charge le schéma JSON embarqué."""
    schema_path = path or SCHEMA_PATH
    try:
        raw = schema_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"schéma introuvable : {schema_path}") from exc
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"schéma JSON invalide : {schema_path}") from exc
    if not isinstance(schema, dict):
        raise ConfigError(f"schéma JSON invalide : {schema_path}")
    return schema


def validate_config(data: Any, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """Valide une configuration déjà chargée et la renvoie."""
    if not isinstance(data, dict):
        raise ConfigError("la configuration doit être un objet YAML")
    validator = Draft202012Validator(schema or load_schema())
    errors = sorted(validator.iter_errors(data), key=lambda error: (list(error.path), error.message))
    if errors:
        details = []
        for error in errors[:10]:
            location = ".".join(str(part) for part in error.path) or "(racine)"
            details.append(f"{location}: {error.message}")
        raise ConfigError("configuration invalide — " + " ; ".join(details))
    return data


def load_config(path: str | Path | None = None) -> Config:
    """Charge `sdlc.config.yaml`, le valide et renvoie la configuration."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise ConfigError(f"configuration absente : {config_path}")
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML invalide dans {config_path} : {exc}") from exc
    validated = validate_config(data)
    return Config(data=validated, path=config_path)
