"""Tests des profils par dépôt, divergences et surcharges de processus."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import AuditEvent, Base
from sdlc_console.services.process_profiles import (
    build_process_inventory,
    create_override,
)
from sdlc_console.services.projects import add_repository, create_project


class ProcessProfilesTest(unittest.TestCase):
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
        self.api = self._repo("api")
        self.web = self._repo("web")
        self.session.commit()

    def _repo(self, name: str):
        path = self.root / name
        path.mkdir()
        (path / ".git").mkdir()
        return add_repository(
            self.session,
            self.project,
            name=name,
            provider="github",
            url=f"https://github.com/hm/{name}",
            local_path=path,
        )

    def _detection(self, key: str, label: str) -> dict:
        return {
            "key": key,
            "label": label,
            "confidence": 0.8,
            "detected": True,
            "signals": [],
            "reasons": [],
            "scores": {},
        }

    def test_divergence_sans_moyenne(self) -> None:
        result = build_process_inventory(
            self.session,
            self.project,
            detections={
                self.api.id: self._detection("github_flow", "GitHub Flow"),
                self.web.id: self._detection("git_flow", "Git Flow"),
            },
        )
        self.assertTrue(result["divergent"])
        self.assertIsNone(result["dominant_profile"])
        self.assertEqual(len(result["divergences"]), 2)
        self.assertEqual(result["status"], "measured")

    def test_profil_dominant_et_surcharge(self) -> None:
        third = self._repo("worker")
        self.session.commit()
        result = build_process_inventory(
            self.session,
            self.project,
            detections={
                self.api.id: self._detection("github_flow", "GitHub Flow"),
                self.web.id: self._detection("github_flow", "GitHub Flow"),
                third.id: self._detection("git_flow", "Git Flow"),
            },
        )
        self.assertTrue(result["divergent"])
        self.assertEqual(result["dominant_profile"]["key"], "github_flow")
        self.assertEqual(result["dominant_profile"]["count"], 2)

        record = create_override(
            self.session,
            self.project,
            repository_id=third.id,
            profile_key="trunk_based",
            reason="migration en cours",
        )
        self.session.commit()
        audit = self.session.scalars(select(AuditEvent)).all()
        self.assertEqual(audit[-1].action, "process.override")
        overridden = build_process_inventory(
            self.session,
            self.project,
            detections={
                self.api.id: self._detection("github_flow", "GitHub Flow"),
                self.web.id: self._detection("github_flow", "GitHub Flow"),
                third.id: self._detection("git_flow", "Git Flow"),
            },
        )
        worker = next(
            item for item in overridden["repositories"] if item["repository_id"] == third.id
        )
        self.assertEqual(worker["profile"], "trunk_based")
        self.assertEqual(worker["source"], "override")
        self.assertEqual(worker["override"]["reason"], "migration en cours")
        self.assertEqual(record.profile_key, "trunk_based")

    def test_api_process_override(self) -> None:
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
        response = client.put(
            f"/api/projects/{self.project.id}/process/override",
            json={
                "repository_id": self.api.id,
                "profile_key": "git_flow",
                "reason": "nouveau flux",
                "actor_label": "tech lead",
            },
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(response.status_code, 200)
        process = client.get(f"/api/projects/{self.project.id}/process")
        self.assertEqual(process.status_code, 200)
        api_profile = next(
            item
            for item in process.json()["repositories"]
            if item["repository_id"] == self.api.id
        )
        self.assertEqual(api_profile["profile"], "git_flow")
        self.assertEqual(api_profile["source"], "override")

    def test_override_invalide_refusee(self) -> None:
        from sdlc_console.services.process_profiles import ProcessError

        with self.assertRaises(ProcessError):
            create_override(
                self.session,
                self.project,
                repository_id=self.api.id,
                profile_key="unknown",
                reason="",
            )


if __name__ == "__main__":
    unittest.main()
