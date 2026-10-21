"""Tests du rapport de revue et de la fiche de décision."""

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
from sdlc_console.services.review_package import build_review_package
from sdlc_console.services.review_report import (
    ReviewReportError,
    build_review_report,
    validate_review_payload,
)


class ReviewReportTest(unittest.TestCase):
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
        (self.root / "spec.md").write_text("# Spec\n", encoding="utf-8")
        self.session.commit()
        self.package = build_review_package(
            self.session,
            self.project,
            task_key="3.8",
            spec_paths=["spec.md"],
            diff="diff --git a/a.py b/a.py\n+ok\n",
            root=self.root,
        ).record
        self.session.commit()

    def _report(self, **kwargs):
        return build_review_report(
            self.session,
            self.project,
            self.package,
            verdict="warn",
            confidence=0.8,
            findings=[
                {
                    "id": "F-1",
                    "category": "spec",
                    "severity": "blocker",
                    "confidence": 0.9,
                    "evidence": "spec.md:3",
                    "impact": "contradiction",
                    "minimal_fix": "préciser",
                }
            ],
            unverified=["test manuel"],
            options=[{"id": "O-1", "label": "corriger", "effort": "1 h", "risk": "faible"}],
            recommendation="Corriger avant merge",
            risks=["retard"],
            questions=["Le cas limite est-il accepté ?"],
            root=self.root,
            **kwargs,
        )

    def test_rapport_valide_et_fiche(self) -> None:
        result = self._report()
        self.assertTrue(result.report_path.is_file())
        self.assertTrue(result.decision_path.is_file())
        report = json.loads(result.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["verdict"], "warn")
        self.assertEqual(report["decision_sheet"]["blockers"], ["F-1"])
        self.assertLessEqual(len(report["decision_sheet"]["blockers"]), 3)
        self.assertIn("Fiche de décision", result.decision_path.read_text(encoding="utf-8"))
        validate_review_payload(report)

    def test_finding_sans_preuve_refuse(self) -> None:
        with self.assertRaises(ReviewReportError):
            build_review_report(
                self.session,
                self.project,
                self.package,
                verdict="fail",
                confidence=0.5,
                findings=[
                    {
                        "id": "F-2",
                        "category": "test",
                        "severity": "major",
                        "confidence": 0.5,
                        "evidence": "",
                        "impact": "inconnu",
                        "minimal_fix": "ajouter",
                    }
                ],
                root=self.root,
            )

    def test_api_rapport(self) -> None:
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
            f"/api/reviews/{self.package.id}/report",
            json={
                "verdict": "pass",
                "confidence": 0.9,
                "findings": [],
                "unverified": [],
                "options": [],
                "recommendation": "ok",
            },
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["report"]["verdict"], "pass")


if __name__ == "__main__":
    unittest.main()
