"""Tests des décisions humaines et de leur audit."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import AuditEvent, Base
from sdlc_console.services.decisions import (
    DecisionError,
    create_decision,
    list_decisions,
)
from sdlc_console.services.projects import create_project
from sdlc_console.services.review_package import build_review_package
from sdlc_console.services.review_report import build_review_report


class DecisionsTest(unittest.TestCase):
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
        package = build_review_package(
            self.session,
            self.project,
            task_key="3.8",
            spec_paths=["spec.md"],
            diff="diff --git a/a.py b/a.py\n+ok\n",
            root=self.root,
        ).record
        self.session.commit()
        self.report = build_review_report(
            self.session,
            self.project,
            package,
            verdict="warn",
            confidence=0.8,
            findings=[],
            root=self.root,
        ).record
        self.session.commit()

    def test_approbation_conditionnelle_et_audit(self) -> None:
        record = create_decision(
            self.session,
            self.project,
            subject_type="review_report",
            subject_id=str(self.report.id),
            decision="approve_with_conditions",
            reason="accord sous réserve",
            conditions=["ajouter un test"],
        )
        self.session.commit()
        self.assertEqual(record.decision, "approve_with_conditions")
        self.assertTrue(record.actor_label.startswith("décision depuis"))
        audit = self.session.scalars(select(AuditEvent)).all()
        self.assertEqual(audit[-1].action, "decision.recorded")
        self.assertEqual(len(list_decisions(self.session, self.project)), 1)
        self.assertIn("non authentifiée", audit[-1].actor_label)

    def test_conditions_obligatoires(self) -> None:
        with self.assertRaises(DecisionError):
            create_decision(
                self.session,
                self.project,
                subject_type="review_report",
                subject_id=str(self.report.id),
                decision="approve_with_conditions",
                reason="sans condition",
            )

    def test_api_decision(self) -> None:
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
            f"/api/reviews/{self.report.id}/decision",
            json={
                "decision": "reject",
                "reason": "non conforme",
                "conditions": [],
            },
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["decision"]["decision"], "reject")
        listing = client.get(f"/api/projects/{self.project.id}/decisions")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["total"], 1)

        invalid = client.post(
            f"/api/reviews/{self.report.id}/decision",
            json={"decision": "approve_with_conditions", "reason": "x"},
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(invalid.status_code, 409)


if __name__ == "__main__":
    unittest.main()
