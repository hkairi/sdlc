"""Tests de la vue d'ensemble : KPI, décisions, pipeline et risques."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Deployment, TaskRun, utc_now
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.overview import build_overview
from sdlc_console.services.projects import create_project


class OverviewTest(unittest.TestCase):
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

    def _seed(self) -> None:
        feature = create_feature(
            self.session,
            self.project,
            key="F-1",
            name="Console",
            status="doing",
            objective="Construire",
            spec_path="design.md",
        )
        feature.blocked = True
        feature.phases_json = json.dumps(
            [
                {"id": "cadrage", "name": "Cadrage", "order": 1, "items": [{"status": "done"}]},
                {"id": "impl", "name": "Implémentation", "order": 3, "items": []},
                {"id": "validation", "name": "Validation", "order": 4, "items": [{"status": "todo"}]},
                {"id": "deploy", "name": "Déploiement", "order": 5, "items": [{"status": "todo"}]},
            ]
        )
        create_task(self.session, feature, key="1.1", title="Fait", status="done")
        create_task(self.session, feature, key="1.2", title="En cours", status="doing")
        blocked = create_task(
            self.session,
            feature,
            key="1.3",
            title="Bloquée",
            status="blocked",
            note="Décision humaine attendue",
        )
        self.session.add(
            TaskRun(
                project_id=self.project.id,
                run_id="run-1",
                status="done",
                cost_eur=0.5,
                started_at=utc_now(),
                origin="ingérée",
            )
        )
        self.session.add(
            TaskRun(
                project_id=self.project.id,
                run_id="run-2",
                status="done",
                cost_eur=0.25,
                started_at=utc_now(),
                origin="ingérée",
            )
        )
        self.session.add(
            Deployment(
                project_id=self.project.id,
                deploy_id="dep-1",
                env="prod",
                version="1.0.0",
                status="failed",
                started_at=utc_now(),
                imported_at=utc_now(),
            )
        )
        self.session.commit()
        self.feature = feature
        self.blocked = blocked

    def test_kpis_avec_source_et_non_mesure(self) -> None:
        self._seed()
        overview = build_overview(self.session, self.project)
        kpis = {item["key"]: item for item in overview["kpis"]}
        self.assertEqual(kpis["progress"]["value"], 33)
        self.assertEqual(kpis["progress"]["status"], "measured")
        self.assertEqual(kpis["progress"]["source"], "state.json")
        self.assertIsNone(kpis["gates"]["value"])
        self.assertEqual(kpis["gates"]["status"], "not_measured")
        self.assertIsNone(kpis["coverage"]["value"])
        self.assertIsNone(kpis["vulnerabilities"]["value"])
        self.assertEqual(kpis["ai_cost"]["value"], 0.75)
        self.assertEqual(kpis["ai_cost"]["status"], "measured")
        self.assertIsNone(kpis["lead_time"]["value"])
        self.assertEqual(kpis["lead_time"]["status"], "not_measured")

    def test_decisions_pipeline_et_risques(self) -> None:
        self._seed()
        overview = build_overview(self.session, self.project)
        self.assertGreaterEqual(len(overview["pending_decisions"]), 2)
        self.assertTrue(all(decision["blocking"] for decision in overview["pending_decisions"]))
        self.assertTrue(all("link" in decision for decision in overview["pending_decisions"]))
        self.assertEqual(
            set(overview["risk_categories"]),
            {"données", "sécurité", "performance", "tests", "projet", "déploiement"},
        )
        stages = {stage["id"]: stage for stage in overview["pipeline"]}
        self.assertEqual(stages["cadrage"]["status"], "done")
        self.assertEqual(stages["impl"]["status"], "doing")
        self.assertEqual(stages["validation"]["status"], "todo")
        self.assertEqual(stages["validation"]["source"], "state.json")
        categories = {risk["category"] for risk in overview["risks"]}
        self.assertIn("projet", categories)
        self.assertIn("déploiement", categories)

    def test_projet_vide(self) -> None:
        overview = build_overview(self.session, self.project)
        kpis = {item["key"]: item for item in overview["kpis"]}
        self.assertIsNone(kpis["progress"]["value"])
        self.assertEqual(kpis["progress"]["status"], "not_measured")
        self.assertEqual(overview["summary"]["features"], 0)
        self.assertEqual(overview["pending_decisions"], [])
        self.assertEqual(overview["risks"], [])
        self.assertGreaterEqual(len(overview["pipeline"]), 5)

    def test_route_overview(self) -> None:
        self._seed()
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/overview")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["project"]["slug"], "atlas")
        self.assertEqual(len(payload["kpis"]), 6)
        self.assertEqual(client.get("/api/projects/9999/overview").status_code, 404)


if __name__ == "__main__":
    unittest.main()
