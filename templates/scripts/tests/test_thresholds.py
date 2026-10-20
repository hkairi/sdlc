#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests unitaires de check_thresholds.py (bibliothèque standard uniquement).

Lancement depuis n'importe quel répertoire :

    python3 -m unittest discover -s .sdlc/templates/scripts/tests -v

ou, depuis .sdlc/templates/scripts :

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Rend `check_thresholds` importable quel que soit le répertoire courant.
SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_thresholds as ct  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
COVERAGE = FIXTURES / "coverage"
SECURITY = FIXTURES / "security"


class TestCouverture(unittest.TestCase):
    def test_cobertura(self):
        self.assertAlmostEqual(ct.parse_cobertura(COVERAGE / "cobertura.xml"), 87.5, places=3)

    def test_jacoco(self):
        # Compteur LINE de premier niveau : 80 / (80 + 20).
        self.assertAlmostEqual(ct.parse_jacoco(COVERAGE / "jacoco.xml"), 80.0, places=3)

    def test_lcov(self):
        # LH=75, LF=100.
        self.assertAlmostEqual(ct.parse_lcov(COVERAGE / "lcov.info"), 75.0, places=3)

    def test_coverage_json(self):
        self.assertAlmostEqual(ct.parse_coverage_json(COVERAGE / "coverage.json"), 91.5, places=3)

    def test_priorite_du_dossier(self):
        # Les quatre formats coexistent : Cobertura gagne (priorité documentée).
        pct, source = ct.find_coverage(COVERAGE)
        self.assertAlmostEqual(pct, 87.5, places=3)
        self.assertEqual(source.name, "cobertura.xml")

    def test_dossier_absent(self):
        pct, source = ct.find_coverage(FIXTURES / "inexistant")
        self.assertIsNone(pct)
        self.assertIsNone(source)


class TestSarif(unittest.TestCase):
    def test_comptage_par_severite(self):
        # security-severity : 9,8 -> critique ; 7,1 -> haute ; 5,0 -> moyenne ; 2,0 -> basse.
        # niveaux (sans security-severity) : error -> haute ; warning -> moyenne ; note -> basse.
        counts = ct.parse_sarif(SECURITY / "example.sarif")
        self.assertEqual(
            counts,
            {"critique": 1, "haute": 2, "moyenne": 2, "basse": 2},
        )

    def test_rattachement_controle(self):
        self.assertEqual(ct.control_for_sarif("semgrep.sarif"), "sast")
        self.assertEqual(ct.control_for_sarif("trivy-fs.sarif"), "deps")
        self.assertEqual(ct.control_for_sarif("osv.sarif"), "deps")
        self.assertEqual(ct.control_for_sarif("gitleaks.sarif"), "secrets")
        self.assertEqual(ct.control_for_sarif("autre.sarif"), "sast")

    def test_collecte_dossier(self):
        counts = ct.collect_vulns(SECURITY)
        total = {sev: counts["sast"][sev] for sev in ct.SEVERITIES}
        self.assertEqual(total["critique"], 1)
        self.assertEqual(total["haute"], 2)


class TestSeuils(unittest.TestCase):
    def test_normalisation_faible_vers_basse(self):
        self.assertEqual(ct.normalize_block_on("critique, haute, faible"), {"critique", "haute", "basse"})

    def test_separateurs_espaces_et_virgules(self):
        # ci.sh transmet les valeurs séparées par des espaces.
        self.assertEqual(ct.normalize_block_on("critique haute"), {"critique", "haute"})
        self.assertEqual(ct.normalize_block_on("critique;haute"), {"critique", "haute"})

    def test_valeurs_inconnues_ignorees(self):
        self.assertEqual(ct.normalize_block_on("critique, inconnu"), {"critique"})

    def test_couverture_sous_seuil_bloque(self):
        report = ct.build_report(str(COVERAGE), str(SECURITY), 90.0, "critique,haute")
        # Cobertura = 87,5 % < 90 %.
        self.assertTrue(report["coverage_measured"])
        self.assertFalse(report["coverage_ok"])
        self.assertTrue(report["thresholds_blocking"])

    def test_couverture_au_dessus_ne_bloque_pas(self):
        report = ct.build_report(str(COVERAGE), str(SECURITY), 80.0, "critique")
        self.assertTrue(report["coverage_ok"])
        # Une seule vulnérabilité critique dans le SARIF.
        self.assertTrue(report["control_blocking"]["sast"])

    def test_severite_non_bloquante(self):
        # block_on = moyenne : le SARIF contient des vulnérabilités moyennes -> bloque.
        report = ct.build_report(str(COVERAGE), str(SECURITY), 0.0, "moyenne")
        self.assertTrue(report["control_blocking"]["sast"])
        # block_on = basse uniquement, mais la couverture est mesurée -> ok.
        report2 = ct.build_report(str(COVERAGE), str(SECURITY), 0.0, "basse")
        self.assertTrue(report2["control_blocking"]["sast"])

    def test_aucune_mesure_ne_bloque_pas(self):
        report = ct.build_report(str(FIXTURES / "inexistant"), str(FIXTURES / "inexistant"), 80.0, "critique")
        self.assertIsNone(report["coverage_pct"])
        self.assertFalse(report["coverage_measured"])
        self.assertFalse(report["thresholds_blocking"])

    def test_sortie_machine(self):
        report = ct.build_report(str(COVERAGE), str(SECURITY), 90.0, "critique,haute")
        machine = ct.render_machine(report)
        self.assertIn("coverage_pct=87.5", machine)
        self.assertIn("vulns_critique=1", machine)
        self.assertIn("thresholds_blocking=true", machine)


class TestMain(unittest.TestCase):
    def test_exit_1_si_bloquant(self):
        code = ct.main(
            [
                "--coverage-dir", str(COVERAGE),
                "--sarif-dir", str(SECURITY),
                "--coverage-min", "99",
                "--block-on", "critique",
            ]
        )
        self.assertEqual(code, 1)

    def test_vulnerabilite_bloquante_bloque_meme_si_couverture_ok(self):
        code = ct.main(
            [
                "--coverage-dir", str(COVERAGE),
                "--sarif-dir", str(SECURITY),
                "--coverage-min", "50",
                "--block-on", "critique",
            ]
        )
        # Seuil de couverture franchi, mais une vulnérabilité critique existe -> bloque.
        self.assertEqual(code, 1)

    def test_seuils_espaces_depuis_ci(self):
        # ci.sh transmet `--block-on "critique haute"` (séparé par un espace).
        code = ct.main(
            [
                "--coverage-dir", str(COVERAGE),
                "--sarif-dir", str(SECURITY),
                "--coverage-min", "50",
                "--block-on", "critique haute",
            ]
        )
        self.assertEqual(code, 1)

    def test_exit_0_sans_vulnerabilite_bloquante(self):
        code = ct.main(
            [
                "--coverage-dir", str(COVERAGE),
                "--sarif-dir", str(FIXTURES / "inexistant"),
                "--coverage-min", "50",
                "--block-on", "critique",
            ]
        )
        self.assertEqual(code, 0)

    def test_json_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "thresholds.json"
            ct.main(
                [
                    "--coverage-dir", str(COVERAGE),
                    "--sarif-dir", str(SECURITY),
                    "--coverage-min", "50",
                    "--block-on", "critique",
                    "--json-out", str(out),
                ]
            )
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertAlmostEqual(data["coverage_pct"], 87.5, places=3)
            self.assertEqual(data["vulns"]["critique"], 1)


if __name__ == "__main__":
    unittest.main()
