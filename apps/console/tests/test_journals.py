"""Tests d'ingestion de `runs.jsonl` et `deploys.jsonl`."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Deployment, IngestionRun, TaskRun, utc_now
from sdlc_console.services.journals import (
    JournalIngestionError,
    ingest_deploys,
    ingest_journals,
    ingest_runs,
)
from sdlc_console.services.projects import add_repository, create_project


class JournalIngestionTest(unittest.TestCase):
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
        repo_path = self.root / "api"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()
        self.repository = add_repository(
            self.session,
            self.project,
            name="api",
            provider="github",
            url="https://github.com/hm/api",
            local_path=repo_path,
        )
        self.session.commit()

    def _jsonl(self, name: str, records: list[dict[str, object]]) -> Path:
        path = self.root / name
        path.write_text(
            "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
            encoding="utf-8",
        )
        return path

    def test_ingestion_runs_et_idempotence(self) -> None:
        path = self._jsonl(
            "runs.jsonl",
            [
                {
                    "run_id": "run-1",
                    "agent": {"id": "claude", "name": "Claude"},
                    "role": "reviewer",
                    "model": "claude-sonnet",
                    "task": "3.2",
                    "status": "done",
                    "started_at": "2026-01-01T10:00:00Z",
                    "ended_at": "2026-01-01T10:05:00Z",
                    "cost_eur": 0.42,
                    "estimated_cost_eur": 0.5,
                    "budget_eur": 2,
                    "tokens_in": 1200,
                    "tokens_out": 800,
                    "log_path": "logs/run-1.log",
                    "report_path": "reports/run-1.json",
                    "repository": "api",
                }
            ],
        )
        run = ingest_runs(self.session, self.project, path)
        self.session.commit()
        self.assertEqual(run.status, "done")
        stats = json.loads(run.stats_json)
        self.assertEqual(stats["inserted"], 1)

        task_run = self.session.scalars(select(TaskRun)).one()
        self.assertEqual(task_run.run_id, "run-1")
        self.assertEqual(task_run.agent_id, "claude")
        self.assertEqual(task_run.role, "reviewer")
        self.assertEqual(task_run.model, "claude-sonnet")
        self.assertEqual(task_run.task_key, "3.2")
        self.assertEqual(task_run.status, "done")
        self.assertEqual(task_run.cost_eur, 0.42)
        self.assertEqual(task_run.tokens_in, 1200)
        self.assertEqual(task_run.tokens_out, 800)
        self.assertEqual(task_run.primary_repository_id, self.repository.id)
        self.assertEqual(task_run.origin, "ingérée")
        self.assertIsNotNone(task_run.started_at)
        self.assertIsNotNone(task_run.ended_at)

        rerun = ingest_runs(self.session, self.project, path)
        self.session.commit()
        rerun_stats = json.loads(rerun.stats_json)
        self.assertEqual(rerun_stats["inserted"], 0)
        self.assertEqual(rerun_stats["updated"], 1)
        self.assertEqual(len(self.session.scalars(select(TaskRun)).all()), 1)

    def test_valeurs_numeriques_zero_conservees(self) -> None:
        path = self._jsonl(
            "runs.jsonl",
            [
                {
                    "run_id": "run-zero",
                    "agent": "claude",
                    "status": "done",
                    "cost_eur": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "exit_code": 0,
                }
            ],
        )
        ingest_runs(self.session, self.project, path)
        self.session.commit()
        task_run = self.session.scalars(select(TaskRun).where(TaskRun.run_id == "run-zero")).one()
        self.assertEqual(task_run.cost_eur, 0.0)
        self.assertEqual(task_run.tokens_in, 0)
        self.assertEqual(task_run.tokens_out, 0)
        self.assertEqual(task_run.exit_code, 0)

    def test_run_local_non_ecrase_pas(self) -> None:
        local = TaskRun(
            project_id=self.project.id,
            run_id="run-local",
            status="running",
            origin="lancée",
            started_at=utc_now(),
        )
        self.session.add(local)
        self.session.commit()
        path = self._jsonl(
            "runs.jsonl",
            [
                {
                    "run_id": "run-local",
                    "agent": "claude",
                    "role": "executor",
                    "status": "done",
                }
            ],
        )
        run = ingest_runs(self.session, self.project, path)
        self.session.commit()
        stats = json.loads(run.stats_json)
        self.assertEqual(stats["skipped"], 1)
        stored = self.session.scalars(select(TaskRun).where(TaskRun.run_id == "run-local")).one()
        self.assertEqual(stored.origin, "lancée")
        self.assertEqual(stored.status, "running")

    def test_statut_de_run_invalide(self) -> None:
        path = self._jsonl(
            "runs.jsonl",
            [{"run_id": "bad", "agent": "claude", "status": "inconnu"}],
        )
        with self.assertRaises(JournalIngestionError):
            ingest_runs(self.session, self.project, path)
        self.session.commit()
        self.assertEqual(self.session.scalars(select(TaskRun)).all(), [])
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertEqual(run.status, "failed")
        self.assertIn("statut", (run.error or "").lower())

    def test_jsonl_invalide(self) -> None:
        path = self.root / "runs.jsonl"
        path.write_text(
            '{"run_id": "ok", "status": "done"}\n'
            '{"run_id": "bad", "status": }\n',
            encoding="utf-8",
        )
        with self.assertRaises(JournalIngestionError) as raised:
            ingest_runs(self.session, self.project, path)
        self.assertIn("ligne 2", str(raised.exception))
        self.session.commit()
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertEqual(run.status, "failed")

    def test_ingestion_deploys_et_rollback(self) -> None:
        path = self._jsonl(
            "deploys.jsonl",
            [
                {
                    "deploy_id": "dep-1",
                    "env": "prod",
                    "version": "1.2.0",
                    "status": "succeeded",
                    "started_at": "2026-01-01T10:00:00Z",
                    "finished_at": "2026-01-01T10:03:00Z",
                    "by": {"name": "Alice", "email": "alice@example.com"},
                    "repository": "api",
                    "feature": {"key": "F-1"},
                    "note": "release",
                },
                {
                    "deploy_id": "dep-2",
                    "environment": "prod",
                    "version": "1.1.0",
                    "status": "rollback",
                    "started_at": "2026-01-02T10:00:00Z",
                    "finished_at": "2026-01-02T10:02:00Z",
                    "by": "Bob",
                    "rollback_of": "1.2.0",
                    "note": "incident",
                },
            ],
        )
        run = ingest_deploys(self.session, self.project, path)
        self.session.commit()
        self.assertEqual(run.status, "done")
        deployments = self.session.scalars(select(Deployment).order_by(Deployment.deploy_id)).all()
        self.assertEqual(len(deployments), 2)
        first, second = deployments
        self.assertEqual(first.env, "prod")
        self.assertEqual(first.version, "1.2.0")
        self.assertEqual(first.status, "success")
        self.assertEqual(first.by_person.display_name, "Alice")
        self.assertEqual(first.repository_id, self.repository.id)
        self.assertEqual(first.feature_key, "F-1")
        self.assertEqual(second.status, "rollback")
        self.assertTrue(second.is_rollback)
        self.assertEqual(second.rollback_of_version, "1.2.0")
        self.assertEqual(second.by_label, "Bob")
        self.assertIsNone(second.by_person)

        rerun = ingest_deploys(self.session, self.project, path)
        self.session.commit()
        stats = json.loads(rerun.stats_json)
        self.assertEqual(stats["inserted"], 0)
        self.assertEqual(stats["updated"], 2)
        self.assertEqual(len(self.session.scalars(select(Deployment)).all()), 2)

    def test_deploiement_sans_environnement_refuse(self) -> None:
        path = self._jsonl(
            "deploys.jsonl",
            [{"deploy_id": "dep-bad", "version": "1", "status": "success"}],
        )
        with self.assertRaises(JournalIngestionError):
            ingest_deploys(self.session, self.project, path)
        self.session.commit()
        self.assertEqual(self.session.scalars(select(Deployment)).all(), [])
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertEqual(run.status, "failed")

    def test_ingestion_des_deux_journaux(self) -> None:
        runs = self._jsonl(
            "runs.jsonl",
            [{"run_id": "run-2", "agent": "claude", "status": "done"}],
        )
        deploys = self._jsonl(
            "deploys.jsonl",
            [{"deploy_id": "dep-3", "env": "dev", "version": "0.1", "status": "success"}],
        )
        results = ingest_journals(
            self.session,
            self.project,
            runs_path=runs,
            deploys_path=deploys,
        )
        self.session.commit()
        self.assertEqual([result.source for result in results], ["runs.jsonl", "deploys.jsonl"])
        self.assertEqual(len(self.session.scalars(select(TaskRun)).all()), 1)
        self.assertEqual(len(self.session.scalars(select(Deployment)).all()), 1)

    def test_journal_absent(self) -> None:
        with self.assertRaises(JournalIngestionError):
            ingest_runs(self.session, self.project, self.root / "absent.jsonl")
        self.session.commit()
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertEqual(run.status, "failed")


if __name__ == "__main__":
    unittest.main()
