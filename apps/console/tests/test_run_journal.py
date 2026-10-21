"""Tests du journal unifié des runs et du taux d'indépendance."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import AuditEvent, Base, HumanNotification, TaskRun, utc_now
from sdlc_console.services.projects import create_project
from sdlc_console.services.run_journal import (
    build_independence,
    build_run_journal,
    deduplicate_runs,
    record_independence_alert,
)


class RunJournalTest(unittest.TestCase):
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
        self.now = datetime.now(UTC)

    def _run(
        self,
        run_id: str,
        *,
        task_key: str,
        role: str,
        model: str,
        origin: str = "lancée",
        status: str = "done",
        agent_id: str = "agent-a",
        cost: float | None = 0.42,
        tokens_in: int | None = 100,
        tokens_out: int | None = 50,
        minutes: int = 5,
    ) -> TaskRun:
        started = self.now - timedelta(days=1, minutes=minutes)
        run = TaskRun(
            project_id=self.project.id,
            run_id=run_id,
            task_key=task_key,
            agent_id=agent_id,
            role=role,
            model=model,
            status=status,
            origin=origin,
            cost_eur=cost,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            started_at=started,
            ended_at=started + timedelta(minutes=minutes),
            imported_at=utc_now(),
        )
        self.session.add(run)
        self.session.commit()
        return run

    def test_journal_filtres_et_union(self) -> None:
        self._run("run-1", task_key="1.1", role="executor", model="m1")
        self._run("run-2", task_key="1.1", role="reviewer", model="m2", origin="ingérée")
        self._run("run-3", task_key="1.2", role="reviewer", model="m1", status="failed")
        result = build_run_journal(self.session, self.project, now=self.now)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["runs"][0]["origin"] in {"lancée", "ingérée"}, True)
        self.assertIsNotNone(result["runs"][0]["duration_seconds"])
        reviewers = build_run_journal(
            self.session,
            self.project,
            role="reviewer",
            now=self.now,
        )
        self.assertEqual(reviewers["total"], 2)
        failed = build_run_journal(
            self.session,
            self.project,
            agent_id="agent-a",
            status="failed",
            now=self.now,
        )
        self.assertEqual(failed["total"], 1)
        self.assertEqual(failed["runs"][0]["cost_eur"], 0.42)
        self.assertEqual(failed["runs"][0]["tokens_in"], 100)

    def test_dedup_priorite_au_run_lance(self) -> None:
        ingested = TaskRun(
            project_id=self.project.id,
            run_id="same",
            origin="ingérée",
            status="done",
            imported_at=utc_now(),
        )
        launched = TaskRun(
            project_id=self.project.id,
            run_id="same",
            origin="lancée",
            status="running",
            imported_at=utc_now(),
        )
        selected = deduplicate_runs([ingested, launched])
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].origin, "lancée")
        self.assertEqual(selected[0].status, "running")

    def test_taux_independance_seuil_et_audit(self) -> None:
        for index in range(10):
            task = f"2.{index}"
            self._run(f"author-{index}", task_key=task, role="executor", model="m1")
            model = "m1" if index == 0 else "m2"
            self._run(f"review-{index}", task_key=task, role="reviewer", model=model)
        summary = build_independence(
            self.session,
            self.project,
            config={"review": {"independence_threshold_percent": 10}},
            now=self.now,
        )
        self.assertEqual(summary["total_reviews"], 10)
        self.assertEqual(summary["degraded_reviews"], 1)
        self.assertEqual(summary["degraded_rate_percent"], 10.0)
        self.assertTrue(summary["decision_required"])
        alert = record_independence_alert(self.session, self.project, summary)
        self.session.commit()
        self.assertIsNotNone(alert)
        alert_again = record_independence_alert(self.session, self.project, summary)
        self.assertFalse(alert_again["created"])
        self.assertEqual(
            len(self.session.scalars(select(HumanNotification)).all()),
            1,
        )
        audits = self.session.scalars(
            select(AuditEvent).where(AuditEvent.action == "review.independence_threshold")
        ).all()
        self.assertEqual(len(audits), 1)

    def test_api_agents_et_independance(self) -> None:
        self._run("run-1", task_key="1.1", role="executor", model="m1")
        self._run("run-2", task_key="1.1", role="reviewer", model="m2")
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
            config_data={"review": {"independence_threshold_percent": 10}},
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/agents?role=reviewer")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertIn("independence", response.json())
        self.assertEqual(response.json()["independence"]["total_reviews"], 1)
        independence = client.get(
            f"/api/projects/{self.project.id}/independence?persist=true"
        )
        self.assertEqual(independence.status_code, 200)
        self.assertEqual(independence.json()["status"], "measured")


if __name__ == "__main__":
    unittest.main()
