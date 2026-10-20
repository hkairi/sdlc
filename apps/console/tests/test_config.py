"""Tests du schéma et du chargement de configuration."""

from __future__ import annotations

import copy
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from sdlc_console.config import (
    ConfigError,
    load_config,
    load_schema,
    validate_config,
)

HAS_YAML = importlib.util.find_spec("yaml") is not None
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
REPO_ROOT = Path(__file__).resolve().parents[3]

MINIMAL: dict = {
    "version": 1,
    "project": {"name": "Atlas", "kind": "new", "stack": ["python"]},
    "agents": {"claude": {"enabled": True, "cli": "claude -p", "models": {"build": "sonnet"}}},
    "orchestrator": "claude",
    "executors": ["claude"],
    "confidentiality": "client",
    "ci": {
        "tool": "github-actions",
        "mode": "integrate",
        "coverage_min": 80,
        "block_on": ["critique", "haute"],
    },
    "deploy": {
        "decided_at": "conception",
        "targets": [{"component": "api", "profile": "vps-compose"}],
    },
    "organisation": {
        "parallelism": "sequential",
        "commit_cadence": "feature",
        "max_review_iterations": 3,
        "task_timeout_min": 30,
    },
    "gates": {
        "default": "toi",
        "spec_freeze": "client-po",
        "recette": "client-po",
        "go_no_go": "toi",
    },
    "dashboard": {
        "file": "docs/suivi-projet.html",
        "reports_dir": "reports/",
        "embed_markdown": True,
        "embed_max_kb": 2048,
        "publish": "none",
    },
    "paths": {
        "templates": ".sdlc/templates",
        "spec": ".sdlc/workflow-sdlc.md",
        "docs": "docs",
        "reports": "reports",
        "ci_script": "scripts/ci.sh",
    },
}


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema non installé")
class SchemaTest(unittest.TestCase):
    def test_schema_est_un_json_valide(self) -> None:
        schema = load_schema()
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertIn("required", schema)

    def test_config_minimale_valide(self) -> None:
        self.assertEqual(validate_config(copy.deepcopy(MINIMAL)), MINIMAL)

    def test_config_sans_project_echoue(self) -> None:
        data = copy.deepcopy(MINIMAL)
        del data["project"]
        with self.assertRaises(ConfigError):
            validate_config(data)

    def test_confidentiality_invalide_echoue(self) -> None:
        data = copy.deepcopy(MINIMAL)
        data["confidentiality"] = "secret"
        with self.assertRaises(ConfigError) as ctx:
            validate_config(data)
        self.assertIn("confidentiality", str(ctx.exception))

    def test_champs_console_optionnels(self) -> None:
        data = copy.deepcopy(MINIMAL)
        data["ui"] = {"open_suivi_on_ready": True, "suivi_path": "/suivi"}
        data["review"] = {"independence": "different_agent_and_model", "blind": True}
        data["retention"] = {"default_days": 365, "exclude_audit": True}
        self.assertEqual(validate_config(data), data)


@unittest.skipUnless(HAS_YAML and HAS_JSONSCHEMA, "pyyaml/jsonschema non installés")
class LoadConfigTest(unittest.TestCase):
    def _write(self, content: str) -> Path:
        descriptor, name = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        return Path(name)

    def test_load_config_minimale(self) -> None:
        import yaml

        path = self._write(yaml.safe_dump(MINIMAL, allow_unicode=True))
        config = load_config(path)
        self.assertEqual(config.project_name, "Atlas")
        self.assertEqual(config.confidentiality, "client")

    def test_load_config_exemple_du_depot(self) -> None:
        example = REPO_ROOT / "sdlc.config.example.yaml"
        if not example.exists():
            self.skipTest("sdlc.config.example.yaml absent")
        config = load_config(example)
        self.assertEqual(config.data["project"]["name"], "Atlas")

    def test_config_absente(self) -> None:
        with self.assertRaises(ConfigError):
            load_config("/tmp/inexistant-sdlc-config.yaml")

    def test_yaml_invalide(self) -> None:
        path = self._write("project: [\n")
        with self.assertRaises(ConfigError):
            load_config(path)


if __name__ == "__main__":
    unittest.main()
