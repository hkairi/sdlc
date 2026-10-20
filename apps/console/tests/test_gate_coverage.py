"""Tests du gate de couverture : Cobertura, lcov, JaCoCo et trois seuils."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, GateFinding
from sdlc_console.services.gate_coverage import (
    parse_jacoco,
    parse_lcov,
    run_coverage_gate,
)
from sdlc_console.services.projects import create_project


class GateCoverageTest(unittest.TestCase):
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

    def _cobertura(self, files: dict[str, list[tuple[int, int]]], name: str = "coverage.xml") -> Path:
        classes = []
        for filename, lines in files.items():
            line_xml = "".join(
                f"<line number='{number}' hits='{hits}'/>" for number, hits in lines
            )
            classes.append(
                f"<class filename='{filename}'><lines>{line_xml}</lines></class>"
            )
        path = self.coverage_dir / name
        path.write_text(
            "<coverage><packages><package><classes>"
            + "".join(classes)
            + "</classes></package></packages></coverage>",
            encoding="utf-8",
        )
        return path

    def _run(self, **kwargs):
        return run_coverage_gate(
            self.session,
            self.project,
            root=self.root,
            **kwargs,
        )

    def test_couverture_globale_et_fichier_ok(self) -> None:
        self._cobertura(
            {
                "src/a.py": [(1, 1), (2, 1), (3, 1)],
                "src/b.py": [(1, 1), (2, 1)],
            }
        )
        result = self._run(
            changed_lines={"src/a.py": [1, 2, 3]},
            thresholds={"global": 80, "changed": 90, "file": 80},
        )
        self.assertEqual(result.evaluation.verdict, "pass")
        self.assertFalse(result.evaluation.blocks)
        self.assertEqual(result.metrics["global"]["percent"], 100.0)
        self.assertEqual(result.metrics["changed"]["percent"], 100.0)
        report = self.root / "reports" / "gates" / "coverage.json"
        self.assertTrue(report.is_file())
        payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "pass")
        self.assertEqual(payload["controls"][0]["details"]["threshold"], 80.0)

        from sdlc_console.services.overview import build_overview

        overview = build_overview(self.session, self.project)
        coverage_kpi = next(
            item for item in overview["kpis"] if item["key"] == "coverage"
        )
        self.assertEqual(coverage_kpi["value"], 100.0)
        self.assertEqual(coverage_kpi["source"], "reports/coverage")

    def test_couverture_globale_insuffisante(self) -> None:
        self._cobertura({"src/a.py": [(1, 1), (2, 0), (3, 0)]})
        result = self._run(thresholds={"global": 80, "changed": 90, "file": 0})
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertTrue(result.evaluation.blocks)
        self.assertEqual(result.metrics["global"]["percent"], 33.33)
        self.assertIn(
            "couverture globale",
            json.dumps(result.evaluation.findings, ensure_ascii=False),
        )
        self.assertGreaterEqual(
            self.session.scalar(select(GateFinding.id).limit(1)),
            1,
        )

    def test_couverture_lignes_modifiees_insuffisante(self) -> None:
        self._cobertura({"src/a.py": [(1, 1), (2, 1), (3, 0), (4, 0)]})
        result = self._run(
            changed_lines={"src/a.py": [3, 4]},
            thresholds={"global": 50, "changed": 90, "file": 0},
        )
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertEqual(result.metrics["changed"]["percent"], 0.0)
        self.assertIn(
            "lignes modifiées",
            json.dumps(result.evaluation.findings, ensure_ascii=False),
        )

    def test_couverture_fichier_insuffisante(self) -> None:
        self._cobertura(
            {
                "src/good.py": [(1, 1), (2, 1)],
                "src/bad.py": [(1, 1), (2, 0)],
            }
        )
        result = self._run(
            thresholds={"global": 70, "changed": 90, "file": 80},
        )
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertEqual(result.metrics["file"]["below"], ["src/bad.py"])

    def test_formats_lcov_et_jacoco(self) -> None:
        lcov = self.coverage_dir / "lcov.info"
        lcov.write_text(
            "SF:src/app.py\nDA:1,1\nDA:2,1\nend_of_record\n",
            encoding="utf-8",
        )
        lcov_data = parse_lcov(lcov, root=self.root)
        self.assertEqual(lcov_data.percent, 100.0)

        jacoco = self.coverage_dir / "jacoco.xml"
        jacoco.write_text(
            "<report><package name='com/example'>"
            "<sourcefile name='App.java'>"
            "<line nr='1' mi='0' ci='1'/>"
            "<line nr='2' mi='1' ci='0'/>"
            "</sourcefile></package></report>",
            encoding="utf-8",
        )
        jacoco_data = parse_jacoco(jacoco, root=self.root)
        self.assertEqual(jacoco_data.percent, 50.0)
        self.assertIn("com/example/App.java", jacoco_data.files)

    def test_absence_de_preuve(self) -> None:
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "not_run")
        self.assertTrue(result.evaluation.blocks)
        self.assertTrue(
            (self.root / "reports" / "gates" / "coverage.json").is_file()
        )


if __name__ == "__main__":
    unittest.main()
