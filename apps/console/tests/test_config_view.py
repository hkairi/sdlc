"""Tests de la vue Configuration : validation, origines et lecture seule."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.config_view import build_configuration_view
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.projects import create_project

VALID = {
    "version": 1,
    "project": {"name": "Atlas", "kind": "new", "stack": ["python"]},
    "agents": {"claude": {"enabled": True}},
    "orchestrator": "claude",
    "executors": ["claude"],
    "confidentiality": "client",
    "ci": {
        "tool": "gitlab-ci",
        "mode": "integrate",
        "coverage_min": 80,
        "block_on": ["critique"],
    },
    "deploy": {
        "decided_at": "init",
        "targets": [{"component": "api", "profile": "vps-compose"}],
    },
    "organisation": {
        "parallelism": "sequential",
        "commit_cadence": "task",
        "max_review_iterations": 3,
        "task_timeout_min": 30,
    },
    "gates": {"default": "toi"},
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


class ConfigurationViewTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.engine = make_engine(f"sqlite:///{self.root / 'db.sqlite3'}")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.Session = make_session_factory(self.engine)
        self.session = self.Session()
        self.addCleanup(self.session.close)
        self.project = create_project(self.session, name="Atlas", slug="atlas")
        feature = create_feature(self.session, self.project, key="atlas", name="Atlas")
        create_task(self.session, feature, key="1.1", title="Tâche")
        self.session.commit()
        self.config_path = self.root / "sdlc.config.yaml"
        self.config_path.write_text("version: 1\n", encoding="utf-8")

    def test_configuration_valide_et_origines(self) -> None:
        config = {**VALID, "api_token": "ghp_abcdefghijklmnopqrstuvwxyz0123456789"}
        view = build_configuration_view(
            self.session,
            self.project,
            config=config,
            config_path=self.config_path,
            root=self.root,
        )
        self.assertTrue(view["validation"]["valid"])
        self.assertEqual(view["validation"]["errors"], [])
        origins = {row["key"]: row for row in view["origins"]}
        self.assertEqual(origins["project.name"]["origin"], "déclarée")
        self.assertEqual(origins["features.count"]["value"], 1)
        self.assertEqual(origins["features.count"]["origin"], "détectée")
        self.assertEqual(origins["runs.count"]["origin"], "mesurée")
        self.assertTrue(view["config_file"]["exists"])
        self.assertNotIn("ghp_", json.dumps(view["effective"]))
        self.assertIn("lecture seule", view["notice"])

    def test_configuration_invalide_indique_la_cle(self) -> None:
        invalid = {"version": 1, "project": {"name": "Atlas"}}
        view = build_configuration_view(
            self.session,
            self.project,
            config=invalid,
            root=self.root,
        )
        self.assertFalse(view["validation"]["valid"])
        paths = {error["path"] for error in view["validation"]["errors"]}
        self.assertTrue(any(path.startswith("project") for path in paths))
        self.assertTrue(any(path.startswith("agents") for path in paths))

    def test_api_configuration_et_alias(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
            config_data=VALID,
            config_path=self.config_path,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/configuration")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["validation"]["valid"])
        alias = client.get(f"/api/projects/{self.project.id}/config")
        self.assertEqual(alias.status_code, 200)
        self.assertEqual(alias.json()["effective"], response.json()["effective"])


if __name__ == "__main__":
    unittest.main()
