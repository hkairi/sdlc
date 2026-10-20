"""Tests du gate de sécurité : SARIF, secrets, atteignabilité et SBOM."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, GateFinding
from sdlc_console.services.gate_security import (
    parse_sarif,
    parse_sbom,
    run_security_gate,
)
from sdlc_console.services.projects import create_project


class GateSecurityTest(unittest.TestCase):
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
        self.security_dir = self.root / "reports" / "security"
        self.security_dir.mkdir(parents=True)

    def _sarif(self, results: list[dict], *, name: str = "sast.sarif") -> Path:
        path = self.security_dir / name
        path.write_text(
            json.dumps(
                {
                    "version": "2.1.0",
                    "runs": [
                        {
                            "tool": {
                                "driver": {
                                    "rules": [
                                        {
                                            "id": "CVE-2026-0001",
                                            "properties": {
                                                "security-severity": "8.1",
                                                "tags": ["security"],
                                            },
                                        },
                                        {
                                            "id": "IAC-001",
                                            "properties": {
                                                "security-severity": "5.0",
                                                "tags": ["iac"],
                                            },
                                        },
                                    ]
                                }
                            },
                            "results": results,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def _sbom(self, *, components: int = 1, name: str = "sbom.json") -> Path:
        path = self.security_dir / name
        path.write_text(
            json.dumps(
                {
                    "bomFormat": "CycloneDX",
                    "specVersion": "1.5",
                    "components": [{"name": f"pkg-{i}"} for i in range(components)],
                }
            ),
            encoding="utf-8",
        )
        return path

    def _run(self, **kwargs):
        return run_security_gate(
            self.session,
            self.project,
            root=self.root,
            **kwargs,
        )

    def test_vulnerabilite_haute_atteignable_bloque(self) -> None:
        self._sarif(
            [
                {
                    "ruleId": "CVE-2026-0001",
                    "level": "error",
                    "message": {"text": "CVE haute atteignable"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "src/app.py"},
                                "region": {"startLine": 12},
                            }
                        }
                    ],
                    "properties": {"reachable": True},
                }
            ]
        )
        self._sbom()
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertTrue(result.evaluation.blocks)
        self.assertIn("atteignable", json.dumps(result.evaluation.findings, ensure_ascii=False))
        self.assertEqual(
            self.session.scalar(select(func.count(GateFinding.id))),
            1,
        )
        report = self.root / "reports" / "gates" / "security.json"
        self.assertTrue(report.is_file())
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["verdict"], "fail")

        from sdlc_console.services.overview import build_overview

        overview = build_overview(self.session, self.project)
        vulnerability_kpi = next(
            item for item in overview["kpis"] if item["key"] == "vulnerabilities"
        )
        self.assertEqual(vulnerability_kpi["value"], 1)
        self.assertEqual(vulnerability_kpi["source"], "reports/security")

    def test_vulnerabilite_non_atteignable_alerte(self) -> None:
        self._sarif(
            [
                {
                    "ruleId": "IAC-001",
                    "level": "warning",
                    "message": {"text": "configuration IaC"},
                    "properties": {"reachable": False},
                }
            ]
        )
        self._sbom()
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "warn")
        self.assertFalse(result.evaluation.blocks)
        self.assertIn("non atteignable", json.dumps(result.evaluation.findings, ensure_ascii=False))

    def test_secret_bloque(self) -> None:
        (self.security_dir / "secrets.json").write_text(
            json.dumps(
                {
                    "findings": [
                        {
                            "id": "secret-1",
                            "file": "src/config.py",
                            "line": 4,
                            "message": "jeton en clair",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self._sbom()
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertIn("jeton", json.dumps(result.evaluation.findings, ensure_ascii=False))
        self.assertEqual(result.evaluation.controls[1]["key"], "secrets")
        self.assertEqual(result.evaluation.controls[1]["verdict"], "fail")

    def test_sbom_absent_alerte_sans_bloquer(self) -> None:
        self._sarif([])
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "warn")
        self.assertFalse(result.evaluation.blocks)
        self.assertIn("SBOM absent", json.dumps(result.evaluation.findings, ensure_ascii=False))

    def test_sans_preuve_not_run(self) -> None:
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "not_run")
        self.assertTrue(result.evaluation.blocks)

    def test_sarif_propre_et_sbom_passent(self) -> None:
        self._sarif([])
        self._sbom(components=2)
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "pass")
        self.assertFalse(result.evaluation.blocks)
        self.assertEqual(result.sbom.components, 2)
        self.assertEqual(result.evaluation.controls[2]["verdict"], "pass")

    def test_parse_sarif_et_sbom(self) -> None:
        path = self._sarif([])
        findings = parse_sarif(path, root=self.root)
        self.assertEqual(findings, ())
        spdx = self.security_dir / "spdx.json"
        spdx.write_text(
            json.dumps({"spdxVersion": "SPDX-2.3", "packages": [{"name": "a"}]}),
            encoding="utf-8",
        )
        info = parse_sbom(spdx, root=self.root)
        self.assertEqual(info.format, "spdx")
        self.assertEqual(info.components, 1)


if __name__ == "__main__":
    unittest.main()
