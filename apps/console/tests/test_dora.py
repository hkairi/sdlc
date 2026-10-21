"""Tests des métriques DORA et du MTTR depuis les incidents."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Deployment, utc_now
from sdlc_console.services.dora import build_dora, parse_incident_file
from sdlc_console.services.features import create_feature
from sdlc_console.services.projects import create_project


class DoraTest(unittest.TestCase):
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
        self.feature = create_feature(
            self.session,
            self.project,
            key="F-1",
            name="Feature",
            status="done",
        )
        self.feature.updated_at = datetime(2026, 10, 1, tzinfo=UTC)
        self.session.commit()

    def _deploy(
        self,
        deploy_id: str,
        *,
        env: str = "prod",
        status: str = "success",
        day: int,
        feature_id: int | None = None,
        rollback: bool = False,
    ) -> None:
        moment = datetime(2026, 10, day, 12, tzinfo=UTC)
        self.session.add(
            Deployment(
                project_id=self.project.id,
                deploy_id=deploy_id,
                env=env,
                version=deploy_id,
                status=status,
                started_at=moment,
                finished_at=moment + timedelta(minutes=10),
                feature_id=feature_id,
                is_rollback=rollback,
                imported_at=utc_now(),
            )
        )

    def test_metriques_et_mttr(self) -> None:
        self._deploy("d1", day=2, feature_id=self.feature.id)
        self._deploy("d2", day=5, feature_id=self.feature.id)
        self._deploy("d3", day=10, status="failed", feature_id=self.feature.id)
        self._deploy("d4", day=11, status="rollback", rollback=True)
        self._deploy("dev1", env="dev", day=3)
        self.session.commit()
        incident = self.root / "incident.md"
        incident.write_text(
            "Début : 2026-10-10T10:00:00Z\n"
            "Retour à la normale : 2026-10-10T14:00:00Z\n",
            encoding="utf-8",
        )
        self.assertIsNotNone(parse_incident_file(incident))
        result = build_dora(
            self.session,
            self.project,
            window_days=30,
            incident_paths=[incident],
            now=datetime(2026, 10, 21, tzinfo=UTC),
        )
        metrics = {metric["key"]: metric for metric in result["metrics"]}
        self.assertEqual(metrics["deployment_frequency"]["value"], 0.47)
        self.assertEqual(metrics["change_failure_rate"]["value"], 50.0)
        self.assertIsNotNone(metrics["lead_time"]["value"])
        self.assertEqual(metrics["mttr"]["value"], 4.0)
        self.assertEqual(metrics["mttr"]["source"], "docs/incidents/*.md")
        self.assertEqual(result["deployments"]["prod"], 4)

    def test_sans_donnees_non_mesure(self) -> None:
        result = build_dora(
            self.session,
            self.project,
            window_days=30,
            incidents=[],
            now=datetime(2026, 10, 21, tzinfo=UTC),
        )
        metrics = {metric["key"]: metric for metric in result["metrics"]}
        self.assertEqual(metrics["deployment_frequency"]["status"], "not_measured")
        self.assertEqual(metrics["change_failure_rate"]["status"], "not_measured")
        self.assertEqual(metrics["mttr"]["status"], "not_measured")

    def test_api_dora(self) -> None:
        self._deploy("d1", day=2, feature_id=self.feature.id)
        self.session.commit()
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/dora")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["window_days"], 30)
        self.assertEqual(response.json()["metrics"][0]["key"], "deployment_frequency")


if __name__ == "__main__":
    unittest.main()
