"""Tests de redaction étendue : exports, stats, journaux et paquets de revue."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, IngestionRun, utc_now
from sdlc_console.redaction import redact_log_file, redact_value
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.projects import create_project
from sdlc_console.services.review_package import build_review_package

TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"


class RedactionExtendedTest(unittest.TestCase):
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
        self.feature = create_feature(self.session, self.project, key="atlas", name="Atlas")
        self.task = create_task(
            self.session,
            self.feature,
            key="6.12",
            title="Redaction",
            note=f"ne pas publier {TOKEN}",
        )
        self.run = IngestionRun(
            project_id=self.project.id,
            source="git",
            status="done",
            stats_json=json.dumps({"token": TOKEN, "ok": 1}),
            finished_at=utc_now(),
        )
        self.session.add(self.run)
        self.session.commit()

    def test_redaction_structuree_et_journal(self) -> None:
        value = redact_value({"token": TOKEN, "nested": [f"Bearer {TOKEN}"]})
        self.assertEqual(value["token"], "***")
        self.assertNotIn(TOKEN, json.dumps(value))
        log = self.root / "run.log"
        log.write_text(f"token={TOKEN}\n<script>x</script>\n", encoding="utf-8")
        self.assertTrue(redact_log_file(log))
        text = log.read_text(encoding="utf-8")
        self.assertNotIn(TOKEN, text)
        self.assertIn("<script>x</script>", text)

    def test_paquet_revue_expurge_et_csp(self) -> None:
        (self.root / "spec.md").write_text(f"# Spec\n{TOKEN}\n", encoding="utf-8")
        result = build_review_package(
            self.session,
            self.project,
            task_key="6.12",
            spec_paths=["spec.md"],
            diff=f"diff --git a/a b/a\n+token={TOKEN}\n",
            root=self.root,
        )
        serialized = json.dumps(result.payload)
        self.assertNotIn(TOKEN, serialized)
        self.assertIn("***", serialized)
        self.assertTrue(result.payload["csp"]["ok"])
        self.assertNotIn(TOKEN, result.path.read_text(encoding="utf-8"))

    def test_exports_json_et_csv_expurges(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        json_response = client.get(f"/api/projects/{self.project.id}/export?format=json")
        self.assertEqual(json_response.status_code, 200)
        self.assertNotIn(TOKEN, json_response.text)
        self.assertIn("***", json_response.text)
        csv_response = client.get(f"/api/projects/{self.project.id}/export?format=csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertNotIn(TOKEN, csv_response.text)
        self.assertIn("attachment", csv_response.headers["content-disposition"])


if __name__ == "__main__":
    unittest.main()
