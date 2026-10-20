"""Tests du gate de tests : JUnit, échecs, ignorés modifiés et quarantaine."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, GateFinding, utc_now
from sdlc_console.services.gate_tests import (
    QuarantineEntry,
    parse_junit,
    run_tests_gate,
)
from sdlc_console.services.gates import GateError
from sdlc_console.services.projects import create_project


class GateTestsTest(unittest.TestCase):
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
        self.junit_dir = self.root / "reports" / "junit"
        self.junit_dir.mkdir(parents=True)

    def _junit(self, body: str, name: str = "unit.xml") -> Path:
        path = self.junit_dir / name
        path.write_text(body, encoding="utf-8")
        return path

    def _run(self, **kwargs):
        return run_tests_gate(
            self.session,
            self.project,
            root=self.root,
            **kwargs,
        )

    def test_succes_avec_preuve_junit(self) -> None:
        self._junit(
            "<testsuites><testsuite name='unit'>"
            "<testcase classname='tests.test_app' name='test_ok' "
            "file='tests/test_app.py' time='0.12'/>"
            "</testsuite></testsuites>"
        )
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "pass")
        self.assertFalse(result.evaluation.blocks)
        self.assertEqual(result.evaluation.controls[0]["verdict"], "pass")
        self.assertTrue((self.root / "reports" / "gates" / "tests.json").is_file())
        payload = json.loads(
            (self.root / "reports" / "gates" / "tests.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["verdict"], "pass")
        self.assertEqual(payload["gate"]["name"], "Tests")

    def test_echec_de_test_bloque(self) -> None:
        self._junit(
            "<testsuites><testsuite name='unit'>"
            "<testcase classname='tests.test_app' name='test_boom' "
            "file='tests/test_app.py'>"
            "<failure message='assertion échouée'>trace</failure>"
            "</testcase></testsuite></testsuites>"
        )
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertTrue(result.evaluation.blocks)
        self.assertGreaterEqual(len(result.evaluation.findings), 1)
        self.assertEqual(
            self.session.scalar(select(func.count(GateFinding.id))),
            1,
        )
        self.assertEqual(result.run.verdict, "fail")
        self.assertIn("test_boom", json.dumps(result.evaluation.findings, ensure_ascii=False))

    def test_ignore_sur_code_modifie(self) -> None:
        self._junit(
            "<testsuites><testsuite name='unit'>"
            "<testcase classname='tests.test_app' name='test_skip' "
            "file='tests/test_app.py'>"
            "<skipped message='temporaire'/>"
            "</testcase></testsuite></testsuites>"
        )
        result = self._run(changed_files=["tests/test_app.py"])
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertTrue(result.evaluation.blocks)
        self.assertEqual(result.evaluation.findings[0]["key"], "tests.test_app::test_skip")

        self.junit_dir.joinpath("unit.xml").write_text(
            "<testsuites><testsuite name='unit'>"
            "<testcase classname='tests.test_other' name='test_skip' "
            "file='tests/test_other.py'>"
            "<skipped/>"
            "</testcase></testsuite></testsuites>",
            encoding="utf-8",
        )
        # Le résultat précédent est réévalué : le second run repart d'un état propre.
        second = self._run(changed_files=["src/app.py"])
        self.assertEqual(second.evaluation.verdict, "pass")

    def test_quarantaine_active_et_expiree(self) -> None:
        self._junit(
            "<testsuites><testsuite name='unit'>"
            "<testcase classname='tests.test_app' name='test_boom' "
            "file='tests/test_app.py'>"
            "<failure message='instable'/>"
            "</testcase></testsuite></testsuites>"
        )
        active = self._run(
            quarantine=[
                QuarantineEntry(
                    test="tests.test_app::test_boom",
                    ticket="QA-42",
                    expires_at=utc_now() + timedelta(days=2),
                    reason="instabilité connue",
                )
            ]
        )
        self.assertEqual(active.evaluation.verdict, "warn")
        self.assertFalse(active.evaluation.blocks)
        self.assertIn("QA-42", json.dumps(active.evaluation.findings, ensure_ascii=False))
        self.assertEqual(active.quarantined, ("tests.test_app::test_boom",))

        expired = self._run(
            quarantine=[
                QuarantineEntry(
                    test="tests.test_app::test_boom",
                    ticket="QA-42",
                    expires_at=utc_now() - timedelta(days=1),
                )
            ]
        )
        self.assertEqual(expired.evaluation.verdict, "fail")
        self.assertTrue(expired.evaluation.blocks)

    def test_test_instable_sans_quarantaine_alerte(self) -> None:
        self._junit(
            "<testsuites><testsuite name='unit'>"
            "<testcase classname='tests.test_app' name='test_ok' "
            "file='tests/test_app.py'/>"
            "</testsuite></testsuites>"
        )
        result = self._run(flaky_tests=["tests.test_app::test_ok"])
        self.assertEqual(result.evaluation.verdict, "warn")
        self.assertFalse(result.evaluation.blocks)
        self.assertIn(
            "test instable",
            json.dumps(result.evaluation.findings, ensure_ascii=False),
        )

    def test_absence_de_preuve_et_xml_invalide(self) -> None:
        missing = self._run()
        self.assertEqual(missing.evaluation.verdict, "not_run")
        self.assertTrue(missing.evaluation.blocks)

        bad = self.junit_dir / "bad.xml"
        bad.write_text("<testsuite>", encoding="utf-8")
        with self.assertRaises(GateError):
            parse_junit(bad, root=self.root)

    def test_parse_junit_normalise_les_cas(self) -> None:
        path = self._junit(
            "<testsuites><testsuite name='unit'>"
            "<testcase classname='A' name='ok' file='a.py'/>"
            "<testcase classname='A' name='skip'><skipped/></testcase>"
            "<testcase classname='A' name='fail'><error message='boom'/></testcase>"
            "</testsuite></testsuites>"
        )
        tests = parse_junit(path, root=self.root)
        self.assertEqual(len(tests), 3)
        self.assertEqual([test.status for test in tests], ["pass", "skipped", "fail"])
        self.assertEqual(tests[2].key, "A::fail")


if __name__ == "__main__":
    unittest.main()
