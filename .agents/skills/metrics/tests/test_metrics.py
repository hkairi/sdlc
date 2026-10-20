#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la skill metrics (analyse des journaux, rendu Markdown, CLI).

Lancement :
    python3 -m unittest discover -s .agents/skills/metrics/tests -v
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import metrics  # noqa: E402

DEMO = TESTS / "fixtures" / "projet-demo"


class AnalyseDemo(unittest.TestCase):
    def setUp(self):
        self.result = metrics.analyze(DEMO)

    def test_taches_par_agent(self):
        self.assertEqual(self.result["tasks_by_agent"], {"claude": 2, "codex": 3})
        self.assertEqual(self.result["runs_total"], 5)

    def test_runs_par_statut(self):
        self.assertEqual(self.result["runs_by_status"], {"done": 4, "blocked": 1})

    def test_part_validee_premiere_revue(self):
        first = self.result["first_review"]
        self.assertEqual(first["reviewed"], 5)
        self.assertEqual(first["validated"], 3)
        self.assertAlmostEqual(first["ratio"], 0.6, places=6)

    def test_escalades(self):
        escalations = self.result["escalations"]
        self.assertEqual(escalations["total"], 2)
        self.assertEqual(escalations["by_reason"]["bloque"], 1)
        self.assertEqual(escalations["by_reason"]["revues"], 1)
        self.assertEqual(escalations["by_reason"]["delai"], 1)

    def test_rollbacks(self):
        self.assertEqual(self.result["rollbacks"], 1)
        self.assertEqual(self.result["deploys_by_result"]["success"], 2)

    def test_delai_spec_production(self):
        self.assertIn("auth-sso", self.result["lead_times"])
        self.assertEqual(self.result["lead_times"]["auth-sso"]["days"], 31.0)
        self.assertEqual(self.result["average_lead_days"], 31.0)

    def test_seuils_lus_dans_config(self):
        self.assertEqual(self.result["thresholds"]["max_review_iterations"], 3)
        self.assertEqual(self.result["thresholds"]["task_timeout_min"], 30)

    def test_rendu_markdown(self):
        text = metrics.render(self.result)
        self.assertIn("# Indicateurs projet", text)
        self.assertIn("60 %", text)
        self.assertIn("31.0", text)
        self.assertIn("fichier généré", text.lower())


class CasNonMesure(unittest.TestCase):
    def test_journaux_absents(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = metrics.analyze(tmp)
        self.assertFalse(result["sources"]["runs"])
        self.assertIsNone(result["first_review"]["ratio"])
        self.assertEqual(result["lead_times"], {})
        text = metrics.render(result)
        self.assertIn("non mesuré", text)


class InterfaceLigneDeCommande(unittest.TestCase):
    def test_help(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "metrics.py"), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Usage", proc.stdout)

    def test_ecriture_fichier(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "docs" / "metrics" / "indicateurs.md"
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "metrics.py"), str(DEMO), "--out", str(out)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(out.is_file())
            self.assertIn("# Indicateurs projet", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
