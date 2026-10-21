"""Tests de la vue Sécurité : findings, SBOM, licences, dérogations et agents."""

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
from sdlc_console.models import Base, GateFinding
from sdlc_console.services.audit import append_audit
from sdlc_console.services.gate_security import run_security_gate
from sdlc_console.services.projects import create_project
from sdlc_console.services.security_view import build_security_view
from sdlc_console.services.waivers import create_waiver


class SecurityViewTest(unittest.TestCase):
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
        self.security_dir = self.root / "reports" / "security"
        self.security_dir.mkdir(parents=True)
        (self.security_dir / "sast.sarif").write_text(
            json.dumps(
                {
                    "version": "2.1.0",
                    "runs": [
                        {
                            "tool": {
                                "driver": {
                                    "rules": [
                                        {
                                            "id": "CVE-2026-4242",
                                            "properties": {"security-severity": "8.2"},
                                        }
                                    ]
                                }
                            },
                            "results": [
                                {
                                    "ruleId": "CVE-2026-4242",
                                    "level": "error",
                                    "message": {"text": "CVE haute atteignable"},
                                    "locations": [
                                        {
                                            "physicalLocation": {
                                                "artifactLocation": {"uri": "src/app.py"},
                                                "region": {"startLine": 42},
                                            }
                                        }
                                    ],
                                    "properties": {"reachable": True},
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (self.security_dir / "sbom.json").write_text(
            json.dumps(
                {
                    "bomFormat": "CycloneDX",
                    "specVersion": "1.5",
                    "components": [
                        {
                            "name": "fastapi",
                            "version": "0.115.0",
                            "licenses": [{"license": {"id": "MIT"}}],
                        },
                        {
                            "name": "internal",
                            "version": "1.0",
                            "licenses": [{"license": {"name": "Propriétaire"}}],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.run = run_security_gate(
            self.session,
            self.project,
            root=self.root,
        ).run
        self.session.commit()

    def test_vue_securite_complete(self) -> None:
        finding = self.session.scalar(select(GateFinding))
        assert finding is not None
        waiver = create_waiver(
            self.session,
            self.project,
            gate_key="security",
            target_type="finding",
            target_id=str(finding.id),
            reason="risque accepté temporairement",
            owner="équipe",
            approver="responsable",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        self.session.commit()
        append_audit(
            self.session,
            project_id=self.project.id,
            action="agent.git_write_refused",
            object_type="run",
            object_id="run-1",
            payload={"command": "git commit"},
        )
        self.session.commit()
        config = {
            "agents": {
                "claude": {
                    "enabled": True,
                    "cli": "claude -p",
                    "models": ["think", "build"],
                }
            }
        }
        view = build_security_view(
            self.session,
            self.project,
            root=self.root,
            config=config,
        )
        self.assertEqual(view["status"], "measured")
        self.assertEqual(view["finding_counts"]["error"], 1)
        self.assertEqual(view["findings"][0]["file"], "src/app.py")
        self.assertTrue(view["findings"][0]["waived"])
        self.assertEqual(len(view["waivers"]), 1)
        self.assertEqual(view["waivers"][0]["id"], waiver.id)
        self.assertEqual(view["sbom"]["format"], "cyclonedx")
        self.assertEqual(view["sbom"]["components"], 2)
        self.assertIn("MIT", view["licenses"]["values"])
        self.assertIn("Propriétaire", view["licenses"]["values"])
        self.assertEqual(view["agent_surface"]["git_write_refused"], 1)
        self.assertEqual(view["agent_surface"]["agents"][0]["id"], "claude")
        self.assertEqual(view["agent_surface"]["surface"], "modèles de commande configurés uniquement")

    def test_api_securite_et_findings(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
            config_data={"agents": {"claude": {"enabled": True, "cli": "claude -p"}}},
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/security")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["finding_counts"]["error"], 1)
        self.assertEqual(body["sbom"]["components"], 2)
        findings = client.get(
            f"/api/projects/{self.project.id}/findings?gate_key=security&severity=error"
        )
        self.assertEqual(findings.status_code, 200)
        self.assertEqual(findings.json()["total"], 1)
        self.assertEqual(findings.json()["findings"][0]["key"], "CVE-2026-4242")


if __name__ == "__main__":
    unittest.main()
