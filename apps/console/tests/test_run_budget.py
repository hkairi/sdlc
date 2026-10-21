"""Tests du budget et du coût réel des runs."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, TaskRun, utc_now
from sdlc_console.services.projects import create_project
from sdlc_console.services.run_budget import apply_budget, estimate_from_tokens


class RunBudgetTest(unittest.TestCase):
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
        self.run = TaskRun(
            project_id=self.project.id,
            run_id="run-budget",
            status="running",
            agent_id="agent-a",
            model="m1",
            budget_eur=2.0,
            origin="lancée",
            imported_at=utc_now(),
        )
        self.session.add(self.run)
        self.session.commit()

    def test_plafond_atteint_arrete_le_run(self) -> None:
        summary = apply_budget(
            self.session,
            self.run,
            estimated_cost_eur=2.0,
        )
        self.session.commit()
        self.assertEqual(self.run.status, "failed")
        self.assertEqual(self.run.failure_reason, "budget_exceeded")
        self.assertEqual(summary["status"], "budget_exceeded")

    def test_cout_reel_au_dessus_du_budget_est_signale(self) -> None:
        self.run.status = "done"
        self.session.commit()
        summary = apply_budget(self.session, self.run, cost_eur=2.5)
        self.session.commit()
        self.assertTrue(summary["overrun"])
        self.assertEqual(summary["status"], "overrun")
        self.assertEqual(self.run.failure_reason, "budget_exceeded")

    def test_estimation_depuis_tokens(self) -> None:
        self.run.tokens_in = 1000
        self.run.tokens_out = 500
        self.session.commit()
        config = {
            "agents": {
                "agent-a": {
                    "enabled": True,
                    "models": {
                        "m1": {
                            "command": ["python", "-c", "pass"],
                            "input_cost_per_mtok": 3.0,
                            "output_cost_per_mtok": 15.0,
                        }
                    },
                }
            }
        }
        self.assertEqual(estimate_from_tokens(self.run, config=config), 0.0105)

    def test_api_budget(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
            csrf_secret=b"test-secret",
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        token = client.get("/api/csrf").json()["token"]
        response = client.post(
            f"/api/runs/{self.run.run_id}/budget",
            json={"estimated_cost_eur": 2.0},
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["run"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
