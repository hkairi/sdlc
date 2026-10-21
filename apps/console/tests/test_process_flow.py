"""Tests du flux de processus avec gates."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.gates import (
    ControlResult,
    Evidence,
    evaluate_gate,
    persist_gate_run,
)
from sdlc_console.services.process_flow import build_process_flow
from sdlc_console.services.projects import create_project


class ProcessFlowTest(unittest.TestCase):
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
        (self.root / "reports").mkdir()
        (self.root / "reports" / "junit.xml").write_text("<testsuite/>", encoding="utf-8")
        self.session.commit()

    def _gate(self, key: str, label: str) -> None:
        evaluation = evaluate_gate(
            key,
            [
                ControlResult(
                    key="control",
                    verdict="pass",
                    evidence=(Evidence("reports/junit.xml", "junit"),),
                )
            ],
            gate_name=label,
            root=self.root,
        )
        persist_gate_run(
            self.session,
            self.project,
            evaluation,
            root=self.root,
            reports_dir="reports/gates",
        )
        self.session.commit()

    def test_flux_et_liens(self) -> None:
        self._gate("recette", "Recette")
        self._gate("go_no_go", "Go / no-go")
        self._gate("tests", "Tests")
        self._gate("security", "Sécurité")
        result = build_process_flow(self.session, self.project)
        flows = {flow["id"]: flow for flow in result["flows"]}
        self.assertEqual(set(flows), {"feature", "release", "hotfix"})
        release_gates = {
            step["gate_key"]: step
            for step in flows["release"]["steps"]
            if step["type"] == "gate"
        }
        self.assertEqual(release_gates["recette"]["status"], "pass")
        self.assertTrue(release_gates["go_no_go"]["evidence"].endswith("go_no_go.json"))
        hotfix_gates = {
            step["gate_key"]: step
            for step in flows["hotfix"]["steps"]
            if step["type"] == "gate"
        }
        self.assertEqual(hotfix_gates["tests"]["status"], "pass")
        self.assertEqual(hotfix_gates["security"]["status"], "pass")

    def test_sans_gate_not_measured(self) -> None:
        result = build_process_flow(self.session, self.project)
        release = next(flow for flow in result["flows"] if flow["id"] == "release")
        self.assertEqual(
            next(step for step in release["steps"] if step.get("gate_key") == "recette")["status"],
            "not_measured",
        )

    def test_api_flux(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/process/flow")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["flows"]), 3)


if __name__ == "__main__":
    unittest.main()
