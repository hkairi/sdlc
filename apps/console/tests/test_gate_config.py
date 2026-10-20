"""Tests des seuils de configuration, empreintes et invalidation du cache."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.gate_config import (
    coverage_thresholds,
    data_config,
    performance_thresholds,
    security_config,
)
from sdlc_console.services.gate_coverage import run_coverage_gate
from sdlc_console.services.gates import config_fingerprint, latest_gate_runs
from sdlc_console.services.projects import create_project


class GateConfigTest(unittest.TestCase):
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
        self.coverage_dir = self.root / "reports" / "coverage"
        self.coverage_dir.mkdir(parents=True)
        (self.coverage_dir / "coverage.xml").write_text(
            "<coverage><packages><package><classes>"
            "<class filename='src/app.py'><lines>"
            "<line number='1' hits='1'/><line number='2' hits='1'/>"
            "<line number='3' hits='1'/><line number='4' hits='1'/>"
            "<line number='5' hits='1'/><line number='6' hits='0'/>"
            "</lines></class></classes></package></packages></coverage>",
            encoding="utf-8",
        )

    def test_lecture_des_seuils_quality(self) -> None:
        config = {
            "quality": {
                "coverage": {
                    "global_min": 83,
                    "changed_lines_min": 91,
                    "per_file_min": 84,
                },
                "performance": {
                    "regression_percent": 12,
                    "warning_percent": 6,
                    "budget_warning_ratio": 0.85,
                    "p95_ms": 300,
                    "bundle_kb": 250,
                },
                "security": {"block_on": ["critical"], "reachability": False},
                "data": {"retention_days": 365, "encrypted": True},
            }
        }
        self.assertEqual(
            coverage_thresholds(config),
            {"global": 83.0, "changed": 91.0, "file": 84.0},
        )
        performance = performance_thresholds(config)
        self.assertEqual(performance["regression_percent"], 12.0)
        self.assertEqual(performance["default_p95_ms"], 300.0)
        self.assertEqual(performance["default_bundle_kb"], 250.0)
        self.assertEqual(security_config(config)["block_on"], ("critical",))
        self.assertFalse(security_config(config)["reachability"])
        self.assertEqual(data_config(config)["retention_days"], 365)
        self.assertTrue(data_config(config)["encrypted"])

    def test_fingerprint_change_marque_recalcul(self) -> None:
        config_a = {"quality": {"coverage": {"global_min": 80}}}
        config_b = {"quality": {"coverage": {"global_min": 85}}}
        fingerprint_a = config_fingerprint(config_a)
        fingerprint_b = config_fingerprint(config_b)
        self.assertNotEqual(fingerprint_a, fingerprint_b)

        run_coverage_gate(
            self.session,
            self.project,
            config=config_a,
            root=self.root,
        )
        self.session.commit()
        latest = latest_gate_runs(
            self.session,
            self.project,
            current_fingerprint=fingerprint_a,
        )
        self.assertFalse(latest[0]["recalculate_required"])
        stale = latest_gate_runs(
            self.session,
            self.project,
            current_fingerprint=fingerprint_b,
        )
        self.assertTrue(stale[0]["recalculate_required"])

        second = run_coverage_gate(
            self.session,
            self.project,
            config=config_b,
            root=self.root,
        )
        self.session.commit()
        self.assertEqual(second.thresholds["global"], 85.0)
        self.assertEqual(second.evaluation.config_fingerprint, fingerprint_b)

    def test_api_expose_recalcul_requis(self) -> None:
        config_a = {"quality": {"coverage": {"global_min": 80}}}
        run_coverage_gate(
            self.session,
            self.project,
            config=config_a,
            root=self.root,
        )
        self.session.commit()
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
            config_fingerprint=config_fingerprint({"quality": {"coverage": {"global_min": 85}}}),
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/gates")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["gates"][0]["recalculate_required"])


if __name__ == "__main__":
    unittest.main()
