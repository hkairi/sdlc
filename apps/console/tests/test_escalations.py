"""Tests des escalades après rejets et dépassement de délai."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import AuditEvent, Base, HumanNotification
from sdlc_console.services.decisions import create_decision
from sdlc_console.services.escalations import escalate_timed_out_tasks
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.projects import create_project
from sdlc_console.services.review_package import build_review_package
from sdlc_console.services.review_report import build_review_report


class EscalationTest(unittest.TestCase):
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
            key="atlas",
            name="Atlas",
            change="atlas",
        )
        self.task = create_task(
            self.session,
            self.feature,
            key="1.1",
            title="Tâche",
            status="doing",
        )
        (self.root / "spec.md").write_text("# Spec\n", encoding="utf-8")
        package = build_review_package(
            self.session,
            self.project,
            task_key=self.task.key,
            feature_key=self.feature.key,
            spec_paths=["spec.md"],
            diff="diff --git a/a.py b/a.py\n+ok\n",
            root=self.root,
        ).record
        self.session.commit()
        self.report = build_review_report(
            self.session,
            self.project,
            package,
            verdict="fail",
            confidence=0.9,
            findings=[],
            root=self.root,
        ).record
        self.session.commit()
        self.config = {"organisation": {"max_review_iterations": 3, "task_timeout_min": 60}}

    def _reject(self) -> None:
        create_decision(
            self.session,
            self.project,
            subject_type="review_report",
            subject_id=str(self.report.id),
            decision="reject",
            reason="à revoir",
            config=self.config,
        )
        self.session.commit()

    def test_trois_rejets_bloquent_et_notifient(self) -> None:
        self._reject()
        self._reject()
        self.session.refresh(self.task)
        self.assertEqual(self.task.status, "doing")
        self.assertEqual(
            self.session.scalars(select(HumanNotification)).all(),
            [],
        )
        self._reject()
        self.session.refresh(self.task)
        self.assertEqual(self.task.status, "blocked")
        notifications = self.session.scalars(select(HumanNotification)).all()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].kind, "review_escalation")
        payload = json.loads(notifications[0].payload_json)
        self.assertEqual(len(payload["rejections"]), 3)
        audit = self.session.scalars(
            select(AuditEvent).where(AuditEvent.action == "task.escalated")
        ).one()
        audit_payload = json.loads(audit.payload_json)
        self.assertEqual(audit_payload["reason"], "review_rejections")
        self.assertEqual(len(audit_payload["iterations"]), 3)

    def test_timeout_bloque_et_notifie(self) -> None:
        self.task.updated_at = datetime.now(UTC) - timedelta(hours=2)
        self.session.commit()
        escalated = escalate_timed_out_tasks(
            self.session,
            self.project,
            config=self.config,
            now=datetime.now(UTC),
        )
        self.session.commit()
        self.assertEqual(len(escalated), 1)
        self.session.refresh(self.task)
        self.assertEqual(self.task.status, "blocked")
        notification = self.session.scalars(select(HumanNotification)).one()
        self.assertEqual(notification.kind, "task_timeout")
        self.assertEqual(
            self.session.scalars(
                select(AuditEvent).where(AuditEvent.action == "task.escalated")
            ).one().object_id,
            str(self.task.id),
        )

    def test_api_notifications_et_acquittement(self) -> None:
        self._reject()
        self._reject()
        self._reject()
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
            csrf_secret=b"test-secret",
            config_data=self.config,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        token = client.get("/api/csrf").json()["token"]
        listing = client.get(f"/api/projects/{self.project.id}/notifications?pending=true")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["total"], 1)
        notification_id = listing.json()["notifications"][0]["id"]
        ack = client.post(
            f"/api/notifications/{notification_id}/ack",
            json={"actor_label": "humain local"},
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(ack.status_code, 200)
        self.assertFalse(ack.json()["notification"]["pending"])


if __name__ == "__main__":
    unittest.main()
