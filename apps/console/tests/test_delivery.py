"""Contrôles de livraison : recette, CI et documentation d'exploitation."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class DeliveryTest(unittest.TestCase):
    def test_matrice_de_recette_presente(self) -> None:
        report = ROOT / "docs" / "recette" / "console-sdlc.md"
        self.assertTrue(report.is_file())
        text = report.read_text(encoding="utf-8")
        self.assertIn("Matrice scénario → test → résultat", text)
        self.assertIn("Scénarios", text)

    def test_ci_couvre_les_controles(self) -> None:
        script = ROOT / "scripts" / "ci.sh"
        self.assertTrue(script.is_file())
        text = script.read_text(encoding="utf-8")
        for marker in (
            "ruff",
            "mypy",
            "unittest discover",
            "coverage report --fail-under=80",
            "bandit",
            "pip_audit",
            "gitleaks",
            "npm run build",
            "python",
        ):
            self.assertIn(marker, text, marker)

    def test_documentation_installation_et_runbook(self) -> None:
        installation = (ROOT / "docs" / "installation.md").read_text(encoding="utf-8")
        self.assertIn("WSL2", installation)
        self.assertIn("networkingMode=mirrored", installation)
        runbook = (ROOT / "docs" / "ops" / "runbook.md").read_text(encoding="utf-8")
        self.assertIn("purge_busy", runbook)
        self.assertIn("backup_too_old", runbook)


if __name__ == "__main__":
    unittest.main()
