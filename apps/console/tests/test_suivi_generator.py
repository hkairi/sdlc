"""Tests de génération du suivi HTML/JSON et de ses routes API."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Task, utc_now
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.people import resolve_person
from sdlc_console.services.projects import add_repository, create_project
from sdlc_console.services.suivi_generator import (
    build_suivi_data,
    generate_suivi,
    suivi_status,
)


class SuiviGeneratorTest(unittest.TestCase):
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
        owner = resolve_person(
            self.session,
            self.project,
            email="alice@example.com",
            display_name="Alice",
        )
        reviewer = resolve_person(
            self.session,
            self.project,
            email="bob@example.com",
            display_name="Bob",
        )
        feature = create_feature(
            self.session,
            self.project,
            key="console-sdlc",
            name="Console SDLC",
            status="doing",
            primary_repository=self.repository,
            repository_ids=[self.repository.id],
            owner_person=owner,
            objective="Construire la console",
            spec_path="openspec/changes/console-sdlc/design.md",
        )
        create_task(
            self.session,
            feature,
            key="3.1",
            title="Créer les modèles",
            status="done",
            primary_repository=self.repository,
            repository_ids=[self.repository.id],
            owner_person=owner,
            reviewer_person=reviewer,
            files=["models.py"],
            acceptance="Les tables existent",
            lot="L3",
        )
        create_task(
            self.session,
            feature,
            key="3.2",
            title="Ingérer le suivi",
            status="doing",
            primary_repository=self.repository,
            repository_ids=[self.repository.id],
            owner_person=owner,
            lot="L3",
        )
        create_task(
            self.session,
            feature,
            key="3.3",
            title="<script>alert(1)</script>",
            status="todo",
            primary_repository=self.repository,
            repository_ids=[self.repository.id],
            lot="L3",
        )
        self.session.commit()

    def test_generation_json_et_html(self) -> None:
        html_path = self.root / "docs" / "suivi-atlas.html"
        json_path = self.root / "docs" / "suivi" / "atlas.json"
        document = generate_suivi(
            self.session,
            self.project,
            html_path=html_path,
            json_path=json_path,
        )
        self.assertEqual(html_path.is_file(), True)
        self.assertEqual(json_path.is_file(), True)
        self.assertIn("Console SDLC", document.html)
        self.assertIn("Fichier généré, ne pas modifier", document.html)
        self.assertIn("Créer les modèles", document.html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", document.html)
        self.assertNotIn("<script>alert(1)</script>", document.html)
        self.assertIn('<caption>Tâches de la feature Console SDLC</caption>', document.html)

        stored = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["schema"], 1)
        self.assertEqual(stored["project"]["slug"], "atlas")
        self.assertEqual(stored["summary"]["features"], 1)
        self.assertEqual(stored["summary"]["tasks"], 3)
        self.assertEqual(stored["summary"]["done"], 1)
        self.assertEqual(stored["summary"]["doing"], 1)
        self.assertEqual(stored["summary"]["todo"], 1)
        self.assertEqual(stored["features"][0]["tasks"][0]["key"], "3.1")
        self.assertEqual(stored["features"][0]["repositories"][0]["name"], "api")

    def test_status_avant_et_apres_generation(self) -> None:
        html_path = self.root / "docs" / "suivi-atlas.html"
        json_path = self.root / "docs" / "suivi" / "atlas.json"
        before = suivi_status(
            self.session,
            self.project,
            html_path=html_path,
            json_path=json_path,
        )
        self.assertFalse(before["ready"])
        self.assertIsNone(before["generated_at"])
        self.assertFalse(before["stale"])

        document = generate_suivi(
            self.session,
            self.project,
            html_path=html_path,
            json_path=json_path,
        )
        after = suivi_status(
            self.session,
            self.project,
            html_path=html_path,
            json_path=json_path,
        )
        self.assertTrue(after["ready"])
        self.assertEqual(after["generated_at"], document.data["generated_at"])
        self.assertEqual(after["summary"]["tasks"], 3)
        self.assertFalse(after["stale"])

        task = self.session.scalars(select(Task).where(Task.key == "3.3")).one()
        task.status = "doing"
        task.updated_at = utc_now()
        self.session.commit()
        stale = suivi_status(
            self.session,
            self.project,
            html_path=html_path,
            json_path=json_path,
        )
        self.assertTrue(stale["stale"])

    def test_build_data_sans_ecriture(self) -> None:
        data = build_suivi_data(self.session, self.project)
        self.assertEqual(data["summary"]["tasks"], 3)
        self.assertEqual(len(data["features"]), 1)


class SuiviApiTest(unittest.TestCase):
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
        feature = create_feature(
            self.session,
            self.project,
            key="F-1",
            name="Suivi",
            status="doing",
        )
        create_task(self.session, feature, key="3.4", title="Générer le suivi", status="done")
        self.session.commit()
        self.app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
        )
        self.client = TestClient(self.app, base_url="http://127.0.0.2")

    def test_routes_suivi_json_html_et_status(self) -> None:
        status_before = self.client.get(f"/api/projects/{self.project.id}/suivi/status")
        self.assertEqual(status_before.status_code, 200)
        self.assertFalse(status_before.json()["ready"])

        response = self.client.get(f"/api/projects/{self.project.id}/suivi")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/json"))
        self.assertEqual(response.json()["summary"]["tasks"], 1)
        html_path = self.root / "docs" / "suivi-atlas.html"
        json_path = self.root / "docs" / "suivi" / "atlas.generated.json"
        self.assertTrue(html_path.is_file())
        self.assertTrue(json_path.is_file())

        html_response = self.client.get(f"/api/projects/{self.project.id}/suivi?format=html")
        self.assertEqual(html_response.status_code, 200)
        self.assertTrue(html_response.headers["content-type"].startswith("text/html"))
        self.assertIn("Fichier généré, ne pas modifier", html_response.text)
        self.assertIn("Content-Security-Policy", html_response.headers)

        accept_response = self.client.get(
            f"/api/projects/{self.project.id}/suivi",
            headers={"Accept": "text/html"},
        )
        self.assertTrue(accept_response.headers["content-type"].startswith("text/html"))

        status_after = self.client.get(f"/api/projects/{self.project.id}/suivi/status")
        self.assertEqual(status_after.status_code, 200)
        payload = status_after.json()
        self.assertTrue(payload["ready"])
        self.assertIsNotNone(payload["generated_at"])
        self.assertEqual(payload["html_path"], str(html_path))
        self.assertEqual(payload["json_path"], str(json_path))
        self.assertFalse(payload["stale"])
        self.assertTrue(payload["open_on_ready"])
        self.assertEqual(payload["url"], f"/api/projects/{self.project.id}/suivi?format=html")

        projects = self.client.get("/api/projects")
        self.assertEqual(projects.status_code, 200)
        self.assertEqual(projects.json()[0]["slug"], "atlas")

    def test_ouverture_desactivee(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs-disabled",
            open_suivi_on_ready=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/suivi/status")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["open_on_ready"])
        self.assertEqual(response.json()["url"], f"/api/projects/{self.project.id}/suivi?format=html")

    def test_projet_inconnu(self) -> None:
        response = self.client.get("/api/projects/9999/suivi")
        self.assertEqual(response.status_code, 404)
        response = self.client.get("/api/projects/9999/suivi/status")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
