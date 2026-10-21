"""Tests du paquet de revue aveugle."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.projects import create_project
from sdlc_console.services.review_package import (
    ReviewPackageError,
    build_review_package,
)


class ReviewPackageTest(unittest.TestCase):
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
        (self.root / "spec.md").write_text("# Spec\ncontenu\n", encoding="utf-8")
        (self.root / "adr.md").write_text("# ADR\n", encoding="utf-8")
        (self.root / "gate.json").write_text('{"verdict":"pass"}', encoding="utf-8")
        self.session.commit()

    def _build(self, **kwargs):
        return build_review_package(
            self.session,
            self.project,
            task_key="3.8",
            spec_paths=["spec.md"],
            evidence_paths=["gate.json"],
            adr_paths=["adr.md"],
            diff="diff --git a/a.py b/a.py\n+ok\n",
            root=self.root,
            **kwargs,
        )

    def test_paquet_aveugle_empreinte_et_fichier(self) -> None:
        first = self._build()
        second = self._build()
        self.assertEqual(first.record.fingerprint, second.record.fingerprint)
        payload = first.payload
        self.assertTrue(payload["blind"])
        self.assertNotIn("récit de l'auteur", payload["diff"]["content"])
        self.assertEqual(payload["spec"][0]["path"], "spec.md")
        self.assertEqual(payload["adrs"][0]["path"], "adr.md")
        self.assertEqual(payload["evidence"][0]["path"], "gate.json")
        self.assertIn("diff --git", payload["diff"]["content"])
        self.assertTrue(first.path.is_file())
        stored = json.loads(first.path.read_text(encoding="utf-8"))
        self.assertEqual(stored["fingerprint"], first.record.fingerprint)

    def test_diff_invalide_et_chemin_refuse(self) -> None:
        with self.assertRaises(ReviewPackageError):
            build_review_package(
                self.session,
                self.project,
                task_key="1",
                diff="pas un diff",
                root=self.root,
            )
        with self.assertRaises(ReviewPackageError):
            build_review_package(
                self.session,
                self.project,
                task_key="1",
                spec_paths=["../secret"],
                root=self.root,
            )

    def test_api_paquet(self) -> None:
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
            f"/api/projects/{self.project.id}/reviews",
            json={
                "task_key": "3.8",
                "feature_key": "console-sdlc",
                "spec_paths": ["spec.md"],
                "evidence_paths": ["gate.json"],
                "adr_paths": ["adr.md"],
                "diff": "diff --git a/a.py b/a.py\n+ok\n",
            },
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("fingerprint", response.json()["package"])
        listing = client.get(f"/api/projects/{self.project.id}/review-packages")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["total"], 1)


if __name__ == "__main__":
    unittest.main()
