"""Tests du gate de performance : budgets, régressions et signaux statiques."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, GateFinding
from sdlc_console.services.gate_performance import (
    StaticSignal,
    parse_perf_file,
    run_performance_gate,
)
from sdlc_console.services.gates import GateError
from sdlc_console.services.projects import create_project


class GatePerformanceTest(unittest.TestCase):
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
        self.perf_dir = self.root / "reports" / "perf"
        self.perf_dir.mkdir(parents=True)

    def _perf(self, payload: dict, name: str = "search.json") -> Path:
        path = self.perf_dir / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _run(self, **kwargs):
        return run_performance_gate(
            self.session,
            self.project,
            root=self.root,
            **kwargs,
        )

    def test_regression_observee_bloque(self) -> None:
        self._perf(
            {
                "case": "/search",
                "p50_ms": 200,
                "p95_ms": 312,
                "p99_ms": 400,
                "budget_ms": 300,
                "commit": "abc",
                "window": "2026-10-20",
                "tool": "k6",
            }
        )
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertTrue(result.evaluation.blocks)
        self.assertIn("/search", json.dumps(result.evaluation.findings, ensure_ascii=False))
        self.assertEqual(
            self.session.scalar(select(func.count(GateFinding.id))),
            2,
        )  # p95 et p99 dépassent le budget
        report = self.root / "reports" / "gates" / "performance.json"
        self.assertTrue(report.is_file())
        payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "fail")
        self.assertEqual(payload["controls"][0]["details"]["cases"][0]["case"], "/search")

    def test_budget_respecte_passe(self) -> None:
        self._perf({"case": "/health", "p95_ms": 120, "budget_ms": 300})
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "pass")
        self.assertFalse(result.evaluation.blocks)

    def test_proche_du_budget_alerte(self) -> None:
        self._perf({"case": "/search", "p95_ms": 290, "budget_ms": 300})
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "warn")
        self.assertFalse(result.evaluation.blocks)
        self.assertIn("proche du budget", json.dumps(result.evaluation.findings))

    def test_regression_par_rapport_au_baseline(self) -> None:
        self._perf(
            {
                "case": "/search",
                "p95_ms": 312,
                "budget_ms": 400,
                "previous_p95_ms": 280,
            }
        )
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertIn("référence", json.dumps(result.evaluation.findings, ensure_ascii=False))

    def test_signal_statique_alerte_sans_bloquer(self) -> None:
        self._perf({"case": "/health", "p95_ms": 100, "budget_ms": 300})
        result = self._run(
            static_signals=[
                StaticSignal(
                    kind="unbounded_query",
                    message="requête non bornée",
                    file="src/repo.py",
                    line=42,
                )
            ]
        )
        self.assertEqual(result.evaluation.verdict, "warn")
        self.assertFalse(result.evaluation.blocks)
        self.assertIn("requête non bornée", json.dumps(result.evaluation.findings, ensure_ascii=False))

    def test_signal_statique_sans_preuve_observee(self) -> None:
        result = self._run(
            static_signals=[
                StaticSignal(kind="sync_io", message="I/O synchrones", file="a.py")
            ]
        )
        self.assertEqual(result.evaluation.verdict, "warn")
        self.assertFalse(result.evaluation.blocks)

    def test_absence_de_preuve_et_json_invalide(self) -> None:
        missing = self._run()
        self.assertEqual(missing.evaluation.verdict, "not_run")
        self.assertTrue(missing.evaluation.blocks)

        bad = self.perf_dir / "bad.json"
        bad.write_text("{", encoding="utf-8")
        with self.assertRaises(GateError):
            parse_perf_file(bad, root=self.root)

    def test_parse_cas_et_signaux(self) -> None:
        path = self._perf(
            {
                "cases": [{"case": "a", "p95_ms": 10, "budget_ms": 20}],
                "signals": [{"kind": "n_plus_one", "message": "N+1", "file": "x.py", "line": 2}],
            },
            name="combined.json",
        )
        cases, signals = parse_perf_file(path, root=self.root)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].name, "a")
        self.assertEqual(signals[0].kind, "n_plus_one")
        self.assertEqual(signals[0].line, 2)


if __name__ == "__main__":
    unittest.main()
