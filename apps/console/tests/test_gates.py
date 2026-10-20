"""Tests du moteur de gates, des verdicts et des rapports JSON."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, GateFinding, GateRun, utc_now
from sdlc_console.services.gates import (
    ControlResult,
    Evidence,
    Finding,
    GateWaiver,
    config_fingerprint,
    evaluate_gate,
    gate_run_history,
    latest_gate_runs,
    persist_gate_run,
)
from sdlc_console.services.projects import create_project


class GatesTest(unittest.TestCase):
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
        self.evidence = self.root / "reports" / "junit.xml"
        self.evidence.parent.mkdir(parents=True)
        self.evidence.write_text("<testsuite failures='0'/>", encoding="utf-8")

    def _evaluation(self, *, verdict: str = "pass", waiver: GateWaiver | None = None):
        return evaluate_gate(
            "tests",
            [
                ControlResult(
                    key="unit",
                    verdict=verdict,
                    reason="suite unitaire",
                    evidence=(Evidence("reports/junit.xml", "junit", "résultats"),),
                )
            ],
            gate_name="Tests",
            waiver=waiver,
            config={"threshold": 80},
            root=self.root,
        )

    def test_pass_avec_preuve_et_rapport(self) -> None:
        evaluation = self._evaluation()
        self.assertEqual(evaluation.verdict, "pass")
        self.assertFalse(evaluation.blocks)
        self.assertTrue(evaluation.evidence[0]["exists"])
        self.assertIsNotNone(evaluation.evidence[0]["sha256"])
        self.assertEqual(
            evaluation.config_fingerprint,
            config_fingerprint({"threshold": 80}),
        )

        run = persist_gate_run(
            self.session,
            self.project,
            evaluation,
            reports_dir="reports/gates",
            config={"threshold": 80},
            root=self.root,
        )
        self.session.commit()
        latest = self.root / "reports" / "gates" / "tests.json"
        archive = self.root / "reports" / "gates" / f"tests-{run.id}.json"
        self.assertTrue(latest.is_file())
        self.assertTrue(archive.is_file())
        self.assertEqual(run.report_path, str(latest.resolve()))
        payload = json.loads(latest.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "pass")
        self.assertFalse(payload["blocks"])
        self.assertEqual(payload["notice"], "Fichier généré, ne pas modifier.")
        self.assertEqual(payload["controls"][0]["key"], "unit")
        self.assertEqual(payload["config_fingerprint"], evaluation.config_fingerprint)
        self.assertEqual(
            self.session.scalar(select(func.count(GateRun.id))),
            1,
        )
        self.assertEqual(
            self.session.scalar(select(func.count(GateFinding.id))),
            0,
        )
        latest_payload = latest_gate_runs(self.session, self.project)
        self.assertEqual(latest_payload[0]["gate_key"], "tests")
        self.assertEqual(latest_payload[0]["verdict"], "pass")

        from sdlc_console.services.overview import build_overview

        overview = build_overview(self.session, self.project)
        gates_kpi = next(item for item in overview["kpis"] if item["key"] == "gates")
        self.assertEqual(gates_kpi["value"], 0)
        self.assertEqual(gates_kpi["source"], "reports/gates/*.json")

    def test_pass_sans_preuve_devient_not_run_et_bloque(self) -> None:
        evaluation = evaluate_gate(
            "coverage",
            [ControlResult(key="global", verdict="pass", reason="sans artefact")],
            gate_name="Couverture",
            root=self.root,
        )
        self.assertEqual(evaluation.verdict, "not_run")
        self.assertTrue(evaluation.blocks)
        self.assertEqual(evaluation.controls[0]["verdict"], "not_run")
        self.assertIn("preuve absente", evaluation.controls[0]["reason"])

    def test_fail_warn_et_derogation(self) -> None:
        failed = evaluate_gate(
            "security",
            [
                ControlResult(
                    key="cve",
                    verdict="fail",
                    reason="CVE haute",
                    evidence=(Evidence("reports/junit.xml", "junit"),),
                    findings=(
                        Finding(
                            key="CVE-2026-0001",
                            severity="critical",
                            message="CVE critique atteignable",
                            file="requirements.txt",
                            line=12,
                            evidence="reports/junit.xml",
                        ),
                    ),
                )
            ],
            root=self.root,
            config={"threshold": "high"},
        )
        self.assertEqual(failed.verdict, "fail")
        self.assertTrue(failed.blocks)
        self.assertEqual(failed.findings[0]["severity"], "critical")

        valid = evaluate_gate(
            "security",
            [ControlResult(key="cve", verdict="fail")],
            waiver=GateWaiver(
                reason="CVE non atteignable",
                approver="Alice",
                expires_at=utc_now() + timedelta(days=1),
            ),
            root=self.root,
        )
        self.assertEqual(valid.verdict, "waived")
        self.assertFalse(valid.blocks)
        self.assertTrue(valid.waiver["valid"])

        expired = evaluate_gate(
            "security",
            [ControlResult(key="cve", verdict="fail")],
            waiver=GateWaiver(
                reason="ancienne dérogation",
                approver="Alice",
                expires_at=utc_now() - timedelta(days=1),
            ),
            root=self.root,
        )
        self.assertEqual(expired.verdict, "fail")
        self.assertTrue(expired.blocks)
        self.assertFalse(expired.waiver["valid"])

        warned = evaluate_gate(
            "performance",
            [ControlResult(key="p95", verdict="warn", reason="sous le seuil")],
            root=self.root,
        )
        self.assertEqual(warned.verdict, "warn")
        self.assertFalse(warned.blocks)

    def test_not_run_hors_tier_devient_not_applicable(self) -> None:
        evaluation = evaluate_gate(
            "coverage",
            [ControlResult(key="sql", verdict="not_run", expected=False)],
            root=self.root,
        )
        self.assertEqual(evaluation.verdict, "not_applicable")
        self.assertFalse(evaluation.blocks)
        self.assertEqual(evaluation.controls[0]["verdict"], "not_applicable")

    def test_api_gates_et_historique(self) -> None:
        first = self._evaluation()
        persist_gate_run(
            self.session,
            self.project,
            first,
            config={"threshold": 80},
            root=self.root,
        )
        second = evaluate_gate(
            "tests",
            [ControlResult(key="unit", verdict="fail", reason="échec")],
            gate_name="Tests",
            root=self.root,
        )
        persist_gate_run(self.session, self.project, second, root=self.root)
        self.session.commit()

        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/gates")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["gates"][0]["verdict"], "fail")
        history = client.get(f"/api/projects/{self.project.id}/gates/tests/runs")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["total"], 2)
        self.assertEqual(
            gate_run_history(self.session, self.project, "tests")[0]["verdict"],
            "fail",
        )


if __name__ == "__main__":
    unittest.main()
