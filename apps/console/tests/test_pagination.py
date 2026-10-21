"""Tests de la pagination serveur et de la dégradation gracieuse."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.pagination import PageParams, PaginationError, paginate
from sdlc_console.services.projects import create_project


class PaginationUnitTest(unittest.TestCase):
    def test_pages_et_derniere_page_partielle(self) -> None:
        items = list(range(120))
        first = paginate(items, PageParams(limit=50, offset=0))
        self.assertEqual(len(first.items), 50)
        self.assertEqual(first.total, 120)
        self.assertTrue(first.has_more)
        self.assertEqual(first.next_offset, 50)
        middle = paginate(items, PageParams(limit=50, offset=50))
        self.assertEqual(middle.items[0], 50)
        self.assertTrue(middle.has_more)
        last = paginate(items, PageParams(limit=50, offset=100))
        self.assertEqual(len(last.items), 20)
        self.assertFalse(last.has_more)
        beyond = paginate(items, PageParams(limit=50, offset=500))
        self.assertEqual(beyond.items, [])
        self.assertEqual(beyond.total, 120)
        self.assertFalse(beyond.has_more)

    def test_bornes_refusees(self) -> None:
        with self.assertRaises(PaginationError):
            PageParams(limit=201)
        with self.assertRaises(PaginationError):
            PageParams(limit=0)
        with self.assertRaises(PaginationError):
            PageParams(offset=-1)


class PaginationApiTest(unittest.TestCase):
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
        feature = create_feature(self.session, self.project, key="atlas", name="Atlas")
        for index in range(120):
            create_feature(
                self.session,
                self.project,
                key=f"f-{index:03d}",
                name=f"Feature {index}",
            )
            create_task(
                self.session,
                feature,
                key=f"t-{index:03d}",
                title=f"Tâche {index}",
            )
        self.session.commit()
        self.app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        self.client = TestClient(self.app, base_url="http://127.0.0.2")

    def test_features_paginees(self) -> None:
        response = self.client.get(f"/api/projects/{self.project.id}/features")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 121)
        self.assertEqual(len(body["features"]), 50)
        self.assertTrue(body["has_more"])
        self.assertEqual(body["next_offset"], 50)
        last = self.client.get(
            f"/api/projects/{self.project.id}/features?limit=50&offset=100"
        )
        self.assertEqual(len(last.json()["features"]), 21)
        self.assertFalse(last.json()["has_more"])
        beyond = self.client.get(
            f"/api/projects/{self.project.id}/features?limit=50&offset=500"
        )
        self.assertEqual(beyond.status_code, 200)
        self.assertEqual(beyond.json()["features"], [])
        self.assertEqual(beyond.json()["total"], 121)

    def test_tasks_paginees(self) -> None:
        response = self.client.get(f"/api/projects/{self.project.id}/tasks?limit=100")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["tasks"]), 100)
        self.assertEqual(response.json()["total"], 120)
        next_page = self.client.get(
            f"/api/projects/{self.project.id}/tasks?limit=100&offset=100"
        )
        self.assertEqual(len(next_page.json()["tasks"]), 20)
        self.assertFalse(next_page.json()["has_more"])

    def test_bornes_invalides_retournent_400(self) -> None:
        for query in ("limit=201", "limit=0", "offset=-1"):
            response = self.client.get(
                f"/api/projects/{self.project.id}/features?{query}"
            )
            self.assertEqual(response.status_code, 400, query)
            detail = response.json()["detail"].lower()
            self.assertTrue("limit" in detail or "offset" in detail)
        response = self.client.get(
            f"/api/projects/{self.project.id}/findings?limit=201"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("200", response.json()["detail"])
        runs = self.client.get(
            f"/api/projects/{self.project.id}/agents?offset=-1"
        )
        self.assertEqual(runs.status_code, 400)


if __name__ == "__main__":
    unittest.main()
