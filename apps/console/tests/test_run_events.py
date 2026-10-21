"""Tests du flux SSE des journaux de run."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, TaskRun, utc_now
from sdlc_console.services.projects import create_project


def _next_nonempty(lines) -> str:
    for line in lines:
        if line:
            return line
    raise AssertionError("flux SSE terminé")


class RunEventsTest(unittest.TestCase):
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
        self.log = self.root / "reports" / "runs" / "run-sse.log"
        self.log.parent.mkdir(parents=True)
        self.log.write_text(
            "<script>alert(1)</script>\n"
            "token=ghp_abcdefghijklmnopqrstuvwxyz0123456789\n",
            encoding="utf-8",
        )
        self.run = TaskRun(
            project_id=self.project.id,
            run_id="run-sse",
            status="done",
            log_path=str(self.log),
            origin="lancée",
            imported_at=utc_now(),
        )
        self.session.add(self.run)
        self.session.commit()

    def test_log_echappe_et_redacte(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        with client.stream("GET", "/api/runs/run-sse/events") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/event-stream", response.headers["content-type"])
            lines = response.iter_lines()
            self.assertEqual(_next_nonempty(lines), "event: ready")
            ready = json.loads(_next_nonempty(lines)[len("data: ") :])
            self.assertEqual(ready["type"], "ready")
            self.assertEqual(_next_nonempty(lines), "event: run.log")
            log_event = json.loads(_next_nonempty(lines)[len("data: ") :])
            self.assertEqual(log_event["type"], "run.log")
            self.assertIn("<script>alert(1)</script>", log_event["text"])
            self.assertNotIn("ghp_", log_event["text"])
            self.assertIn("***", log_event["text"])
            self.assertEqual(_next_nonempty(lines), "event: run.status")
            status = json.loads(_next_nonempty(lines)[len("data: ") :])
            self.assertEqual(status["status"], "done")

    def test_run_introuvable(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        with client.stream("GET", "/api/runs/inconnu/events") as response:
            lines = response.iter_lines()
            self.assertEqual(_next_nonempty(lines), "event: run.error")


if __name__ == "__main__":
    unittest.main()
