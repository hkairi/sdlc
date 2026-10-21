"""Tests de la vue Performance & données."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.gate_data import run_data_gate
from sdlc_console.services.gate_performance import StaticSignal, run_performance_gate
from sdlc_console.services.projects import create_project
from sdlc_console.services.quality_view import build_performance_data_view


class QualityViewTest(unittest.TestCase):
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
        self.session.commit()

    def _seed_performance(self) -> None:
        perf_dir = self.root / "reports" / "perf"
        perf_dir.mkdir(parents=True)
        (perf_dir / "search.json").write_text(
            json.dumps({"case": "/search", "p95_ms": 120, "budget_ms": 300}),
            encoding="utf-8",
        )
        run_performance_gate(
            self.session,
            self.project,
            root=self.root,
            static_signals=[
                StaticSignal(
                    kind="unbounded_query",
                    message="requête non bornée",
                    file="src/repo.py",
                    line=12,
                )
            ],
        )
        self.session.commit()

    def _seed_data(self) -> None:
        migrations = self.root / "reports" / "data" / "migrations"
        logs = self.root / "reports" / "data" / "logs"
        migrations.mkdir(parents=True)
        logs.mkdir(parents=True)
        (migrations / "001.sql").write_text(
            "ALTER TABLE users ADD COLUMN age INTEGER;\n",
            encoding="utf-8",
        )
        (logs / "app.log").write_text(
            "2026-10-21 contact alice@example.com\n",
            encoding="utf-8",
        )
        (self.root / "reports" / "data" / "backup.json").write_text(
            json.dumps({"verified": True, "restore_tested": True, "age_hours": 2}),
            encoding="utf-8",
        )
        run_data_gate(
            self.session,
            self.project,
            root=self.root,
            retention_days=365,
            encrypted=True,
        )
        self.session.commit()

    def test_vue_performance_et_donnees(self) -> None:
        self._seed_performance()
        self._seed_data()
        view = build_performance_data_view(
            self.session,
            self.project,
            root=self.root,
            config={"quality": {"performance": {"p95_ms": 300}}},
        )
        self.assertEqual(view["performance"]["status"], "measured")
        self.assertEqual(view["performance"]["cases"][0]["case"], "/search")
        self.assertEqual(view["performance"]["budgets"]["default_p95_ms"], 300.0)
        self.assertEqual(view["performance"]["signals"][0]["file"], "src/repo.py")
        self.assertIn("unbounded_query", view["performance"]["signals"][0]["key"])
        self.assertEqual(view["data"]["status"], "measured")
        self.assertEqual(len(view["data"]["pii"]), 1)
        self.assertEqual(view["data"]["pii"][0]["file"], "reports/data/logs/app.log")
        self.assertEqual(view["data"]["backup"]["age_hours"], 2)
        self.assertEqual(view["data"]["retention_days"], 365)
        self.assertTrue(view["data"]["backup"]["verified"])

    def test_api_performance(self) -> None:
        self._seed_performance()
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
            config_data={},
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/performance")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["performance"]["status"], "measured")
        quality = client.get(f"/api/projects/{self.project.id}/quality")
        self.assertEqual(quality.status_code, 200)
        self.assertIn("data", quality.json())


if __name__ == "__main__":
    unittest.main()
