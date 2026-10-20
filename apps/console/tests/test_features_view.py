"""Tests des vues Features & tâches : filtres, détail et incohérences."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, SuiviInconsistency
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.features_view import (
    build_feature_detail,
    build_features_view,
    build_task_report,
    get_task_view,
    list_tasks_view,
)
from sdlc_console.services.projects import create_project


class FeaturesViewTest(unittest.TestCase):
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
        self._seed()

    def _seed(self) -> None:
        first = create_feature(
            self.session,
            self.project,
            key="F-1",
            name="Console",
            status="doing",
            objective="Construire",
            spec_path="design.md",
        )
        first.phases_json = json.dumps(
            [
                {"id": "cadrage", "name": "Cadrage", "order": 1, "items": [{"status": "done"}]},
                {"id": "impl", "name": "Implémentation", "order": 2, "items": []},
                {"id": "validation", "name": "Validation", "order": 3, "items": [{"status": "todo"}]},
            ]
        )
        self.done_task = create_task(
            self.session,
            first,
            key="1.1",
            title="Implémenter",
            status="done",
            lot="L1",
            files=["apps/console/app.py"],
            acceptance="Le détail s'ouvre",
            note="Rapport de fin de tâche",
            executor_label="Alice",
            reviewer_label="Bob",
        )
        create_task(
            self.session,
            first,
            key="1.2",
            title="Tester",
            status="doing",
            executor_label="Alice",
            reviewer_label="Bob",
        )

        second = create_feature(
            self.session,
            self.project,
            key="F-2",
            name="Suivi",
            status="done",
            delivered=True,
        )
        second.phases_json = json.dumps(
            [
                {"id": "cadrage", "name": "Cadrage", "order": 1, "items": [{"status": "done"}]},
                {"id": "validation", "name": "Validation", "order": 3, "items": [{"status": "done"}]},
            ]
        )
        create_task(
            self.session,
            second,
            key="2.1",
            title="Livrer",
            status="done",
        )
        self.session.add(
            SuiviInconsistency(
                project_id=self.project.id,
                feature_key="F-1",
                task_key="1.1",
                kind="etat_done_case_vide",
                message="state.json indique done mais tasks.md n'est pas coché",
                state_status="done",
                tasks_md_checked=False,
            )
        )
        self.session.commit()

    def test_liste_avec_phase_gate_et_incoherences(self) -> None:
        view = build_features_view(self.session, self.project)
        self.assertEqual(view["total"], 2)
        first = next(feature for feature in view["features"] if feature["key"] == "F-1")
        self.assertEqual(first["phase"]["id"], "impl")
        self.assertEqual(first["phase"]["status"], "doing")
        self.assertEqual(first["phase_id"], "impl")
        self.assertEqual(first["spec_path"], "design.md")
        self.assertEqual(first["coverage"]["status"], "not_measured")
        self.assertEqual(first["gate"]["label"], "non mesuré")
        self.assertEqual(first["task_summary"]["done"], 1)
        self.assertEqual(first["task_summary"]["doing"], 1)
        self.assertEqual(first["executors"], ["Alice"])
        self.assertEqual(first["reviewers"], ["Bob"])
        self.assertEqual(len(first["inconsistencies"]), 1)
        self.assertEqual(view["inconsistencies"][0]["feature_key"], "F-1")
        self.assertEqual(view["available_phases"][0]["id"], "impl")
        self.assertEqual(view["available_gates"][0]["id"], "non_mesure")
        self.assertEqual(view["available_gates"][0]["source"], "reports/gates")

    def test_filtres_phase_et_gate(self) -> None:
        impl = build_features_view(self.session, self.project, phase="Implémentation")
        self.assertEqual([feature["key"] for feature in impl["features"]], ["F-1"])
        validation = build_features_view(self.session, self.project, phase="validation")
        self.assertEqual([feature["key"] for feature in validation["features"]], ["F-2"])
        non_mesure = build_features_view(self.session, self.project, gate="non_mesure")
        self.assertEqual(non_mesure["total"], 2)
        security = build_features_view(self.session, self.project, gate="security")
        self.assertEqual(security["total"], 0)

    def test_detail_feature_et_tache(self) -> None:
        detail = build_feature_detail(self.session, self.project, "F-1")
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["feature"]["key"], "F-1")
        self.assertIsNone(build_feature_detail(self.session, self.project, "inconnue"))

        task = get_task_view(self.session, self.project, self.done_task.id)
        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task["files"], ["apps/console/app.py"])
        self.assertEqual(task["acceptance"], "Le détail s'ouvre")
        self.assertEqual(task["note"], "Rapport de fin de tâche")
        self.assertEqual(task["executor"], "Alice")
        self.assertEqual(task["reviewer"], "Bob")
        self.assertTrue(task["report_available"])
        self.assertEqual(
            task["report_url"],
            f"/api/projects/{self.project.id}/tasks/{self.done_task.id}/report",
        )
        report = build_task_report(self.session, self.project, self.done_task.id)
        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual(report["schema"], 1)
        self.assertEqual(report["task"]["key"], "1.1")
        self.assertIsNone(build_task_report(self.session, self.project, 99999))

    def test_liste_des_taches_filtree(self) -> None:
        all_tasks = list_tasks_view(self.session, self.project)
        self.assertEqual(all_tasks["total"], 3)
        done = list_tasks_view(self.session, self.project, status="done")
        self.assertEqual(done["total"], 2)
        first_feature = list_tasks_view(self.session, self.project, feature_key="F-1")
        self.assertEqual(first_feature["total"], 2)
        self.assertEqual(first_feature["tasks"][0]["feature_key"], "F-1")
        self.assertEqual(first_feature["tasks"][0]["phase"]["id"], "impl")

    def test_routes_api_features_et_taches(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
        )
        client = TestClient(app, base_url="http://127.0.0.2")

        response = client.get(f"/api/projects/{self.project.id}/features")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)

        filtered = client.get(
            f"/api/projects/{self.project.id}/features",
            params={"phase": "impl", "gate": "non_mesure"},
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual([item["key"] for item in filtered.json()["features"]], ["F-1"])

        empty = client.get(
            f"/api/projects/{self.project.id}/features",
            params={"gate": "securite"},
        )
        self.assertEqual(empty.json()["total"], 0)

        detail = client.get(f"/api/projects/{self.project.id}/features/F-1")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["feature"]["key"], "F-1")
        self.assertEqual(
            client.get(f"/api/projects/{self.project.id}/features/inconnue").status_code,
            404,
        )

        tasks = client.get(f"/api/projects/{self.project.id}/tasks")
        self.assertEqual(tasks.status_code, 200)
        self.assertEqual(tasks.json()["total"], 3)
        selected = client.get(
            f"/api/projects/{self.project.id}/tasks",
            params={"feature_key": "F-1", "status": "done"},
        )
        self.assertEqual(selected.json()["total"], 1)
        self.assertEqual(
            client.get(f"/api/projects/{self.project.id}/tasks/{self.done_task.id}").status_code,
            200,
        )
        report = client.get(
            f"/api/projects/{self.project.id}/tasks/{self.done_task.id}/report"
        )
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json()["task"]["key"], "1.1")
        self.assertEqual(
            client.get(f"/api/projects/{self.project.id}/tasks/99999").status_code,
            404,
        )
        self.assertEqual(
            client.get(f"/api/projects/{self.project.id}/tasks/99999/report").status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
