"""Tests des gates i18n et langages par tier."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.gate_coverage import run_coverage_gate
from sdlc_console.services.gate_i18n import run_i18n_gate
from sdlc_console.services.gate_languages import (
    detect_languages,
    run_languages_gate,
)
from sdlc_console.services.projects import create_project


class GateLanguagesI18nTest(unittest.TestCase):
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
        self.source = self.root / "src"
        self.source.mkdir()
        self.locales = self.root / "locales"
        self.locales.mkdir()

    def test_langage_sans_adaptateur_bloque(self) -> None:
        (self.source / "app.py").write_text("print('ok')\n", encoding="utf-8")
        (self.source / "App.kt").write_text("fun main() {}\n", encoding="utf-8")
        result = run_languages_gate(
            self.session,
            self.project,
            detected=detect_languages(root=self.root),
            config={
                "quality": {
                    "languages": {
                        "python": {"adapter": "pytest", "tier": 1},
                    }
                }
            },
            root=self.root,
        )
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertTrue(result.evaluation.blocks)
        self.assertEqual(
            {item.language for item in result.languages if not item.supported},
            {"kotlin"},
        )
        self.assertIn(
            "unsupported_language:kotlin",
            json.dumps(result.evaluation.findings, ensure_ascii=False),
        )

    def test_langages_supportes_et_controles_par_tier(self) -> None:
        (self.source / "app.py").write_text("print('ok')\n", encoding="utf-8")
        (self.source / "schema.sql").write_text("select 1;\n", encoding="utf-8")
        result = run_languages_gate(
            self.session,
            self.project,
            detected=detect_languages(root=self.root),
            config={
                "quality": {
                    "languages": {
                        "python": {"adapter": "pytest", "tier": 1},
                        "sql": {"adapter": "sqlfluff", "tier": 2},
                    }
                }
            },
            root=self.root,
        )
        self.assertEqual(result.evaluation.verdict, "pass")
        by_language = {item.language: item for item in result.languages}
        self.assertEqual(
            by_language["python"].expected_controls,
            ("tests", "coverage", "sca", "sast", "performance", "data"),
        )
        self.assertEqual(by_language["sql"].expected_controls, ("tests", "sca"))
        self.assertNotIn("coverage", by_language["sql"].expected_controls)

    def test_couverture_not_applicable_pour_tier_2(self) -> None:
        result = run_coverage_gate(
            self.session,
            self.project,
            languages={"sql": {"adapter": "sqlfluff", "tier": 2}},
            root=self.root,
        )
        self.assertEqual(result.evaluation.verdict, "not_applicable")
        self.assertFalse(result.evaluation.blocks)

    def test_aucun_langage_not_run(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        result = run_languages_gate(
            self.session,
            self.project,
            detected=detect_languages(root=empty),
            root=self.root,
        )
        self.assertEqual(result.evaluation.verdict, "not_run")
        self.assertTrue(result.evaluation.blocks)

    def _locale(self, name: str, payload: dict) -> Path:
        path = self.locales / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_parite_i18n_manquante_et_orpheline(self) -> None:
        self._locale("fr", {"hello": "Bonjour", "nested": {"a": "x"}})
        self._locale("en", {"hello": "Hello", "extra": "Extra"})
        result = run_i18n_gate(
            self.session,
            self.project,
            root=self.root,
        )
        self.assertEqual(result.evaluation.verdict, "warn")
        self.assertFalse(result.evaluation.blocks)
        details = json.dumps(result.evaluation.findings, ensure_ascii=False)
        self.assertIn("nested.a", details)
        self.assertIn("extra", details)
        self.assertEqual(result.evaluation.controls[0]["details"]["rates"]["en"], 50.0)

    def test_chaines_en_dur_et_une_seule_locale(self) -> None:
        self._locale("fr", {"hello": "Bonjour"})
        self._locale("en", {"hello": "Hello"})
        result = run_i18n_gate(
            self.session,
            self.project,
            hardcoded=[
                {
                    "key": "welcome",
                    "message": "chaîne en dur dans le composant",
                    "file": "src/app.py",
                    "line": 12,
                }
            ],
            root=self.root,
        )
        self.assertEqual(result.evaluation.verdict, "warn")
        self.assertIn("chaîne en dur", json.dumps(result.evaluation.findings, ensure_ascii=False))

        single = self.root / "single"
        single.mkdir()
        (single / "fr.json").write_text(json.dumps({"a": "b"}), encoding="utf-8")
        second = run_i18n_gate(
            self.session,
            self.project,
            locale_paths=[single / "fr.json"],
            reference="fr",
            root=self.root,
        )
        self.assertEqual(second.evaluation.verdict, "not_applicable")

    def test_aucune_locale_not_run(self) -> None:
        empty = self.root / "empty-i18n"
        empty.mkdir()
        result = run_i18n_gate(
            self.session,
            self.project,
            locale_paths=[],
            evidence_root=empty,
            root=self.root,
        )
        self.assertEqual(result.evaluation.verdict, "not_run")
        self.assertTrue(result.evaluation.blocks)


if __name__ == "__main__":
    unittest.main()
