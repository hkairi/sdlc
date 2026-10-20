"""Tests des dérogations datées et de leur audit."""

from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import AuditEvent, Base, GateWaiverRecord, utc_now
from sdlc_console.services.gates import (
    ControlResult,
    Finding,
    evaluate_gate,
    gate_run_history,
    latest_gate_runs,
    persist_gate_run,
)
from sdlc_console.services.projects import create_project
from sdlc_console.services.waivers import (
    WaiverError,
    create_waiver,
    effective_for_run,
    list_waivers,
    waiver_status,
)


class WaiversTest(unittest.TestCase):
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
        evaluation = evaluate_gate(
            "security",
            [
                ControlResult(
                    key="cve",
                    verdict="fail",
                    reason="CVE",
                    findings=(
                        Finding(
                            key="CVE-2026-0001",
                            severity="critical",
                            message="CVE critique",
                            file="requirements.txt",
                            line=3,
                        ),
                    ),
                )
            ],
            gate_name="Sécurité",
            root=self.root,
        )
        self.run = persist_gate_run(
            self.session,
            self.project,
            evaluation,
            root=self.root,
        )
        self.session.commit()
        self.finding = self.run.findings[0]

    def test_derogation_active_puis_expiree(self) -> None:
        record = create_waiver(
            self.session,
            self.project,
            gate_key="security",
            target_type="gate_run",
            target_id=str(self.run.id),
            reason="CVE non atteignable",
            owner="Alice",
            approver="Bob",
            expires_at=utc_now() + timedelta(days=2),
        )
        self.session.commit()
        self.assertEqual(waiver_status(record), "active")
        effective = effective_for_run(self.session, self.run)
        self.assertEqual(effective["verdict"], "waived")
        self.assertFalse(effective["blocks"])
        self.assertEqual(effective["waiver"]["approver"], "Bob")
        audit = self.session.scalars(select(AuditEvent)).all()
        self.assertEqual(audit[-1].action, "waiver.created")
        latest = latest_gate_runs(self.session, self.project)
        self.assertEqual(latest[0]["verdict"], "waived")
        self.assertFalse(latest[0]["blocks"])

        from sdlc_console.services.overview import build_overview

        gates_kpi = next(
            item
            for item in build_overview(self.session, self.project)["kpis"]
            if item["key"] == "gates"
        )
        self.assertEqual(gates_kpi["value"], 0)

        record.expires_at = utc_now() - timedelta(seconds=1)
        self.session.commit()
        expired = effective_for_run(self.session, self.run)
        self.assertEqual(expired["verdict"], "fail")
        self.assertTrue(expired["blocks"])
        self.assertEqual(expired["waiver"]["status"], "expired")
        latest = latest_gate_runs(self.session, self.project)
        self.assertEqual(latest[0]["verdict"], "fail")
        self.assertTrue(latest[0]["blocks"])

    def test_derogation_sur_finding(self) -> None:
        create_waiver(
            self.session,
            self.project,
            gate_key="security",
            target_type="finding",
            target_id=self.finding.key,
            reason="finding accepté",
            owner="Alice",
            approver="Bob",
            expires_at=utc_now() + timedelta(days=1),
        )
        self.session.commit()
        effective = effective_for_run(self.session, self.run)
        self.assertEqual(effective["verdict"], "waived")
        self.assertEqual(effective["waiver"]["target_type"], "finding")
        self.assertEqual(len(list_waivers(self.session, self.project)), 1)
        history = gate_run_history(self.session, self.project, "security")
        self.assertEqual(history[0]["verdict"], "waived")

    def test_api_creation_et_liste(self) -> None:
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
            f"/api/projects/{self.project.id}/waivers",
            json={
                "gate_key": "security",
                "target_type": "gate_run",
                "target_id": str(self.run.id),
                "reason": "accepté temporairement",
                "owner": "Alice",
                "approver": "Bob",
                "expires_at": (utc_now() + timedelta(days=1)).isoformat(),
            },
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["waiver"]["status"], "active")
        listing = client.get(f"/api/projects/{self.project.id}/waivers")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["total"], 1)

        invalid = client.post(
            f"/api/projects/{self.project.id}/waivers",
            json={
                "gate_key": "security",
                "target_type": "gate_run",
                "target_id": "99999",
                "reason": "x",
                "owner": "Alice",
                "approver": "Bob",
                "expires_at": (utc_now() + timedelta(days=1)).isoformat(),
            },
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(invalid.status_code, 409)
        expired = client.post(
            f"/api/projects/{self.project.id}/waivers",
            json={
                "gate_key": "security",
                "target_type": "gate_run",
                "target_id": str(self.run.id),
                "reason": "x",
                "owner": "Alice",
                "approver": "Bob",
                "expires_at": (utc_now() - timedelta(days=1)).isoformat(),
            },
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(expired.status_code, 409)

    def test_derogation_invalide(self) -> None:
        with self.assertRaises(WaiverError):
            create_waiver(
                self.session,
                self.project,
                gate_key="security",
                target_type="gate_run",
                target_id=str(self.run.id),
                reason="",
                owner="Alice",
                approver="Bob",
                expires_at=utc_now() + timedelta(days=1),
            )
        self.assertEqual(
            self.session.scalars(select(GateWaiverRecord)).all(),
            [],
        )


if __name__ == "__main__":
    unittest.main()
