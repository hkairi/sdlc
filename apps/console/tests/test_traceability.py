"""Tests de la matrice de traçabilité exigence → scénario → test → tâche."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sdlc_console.services.traceability import (
    TraceabilityError,
    build_traceability_matrix,
    traceability_to_dict,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


class TraceabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "specs").mkdir()
        (self.root / "tests").mkdir()
        self.spec = self.root / "specs" / "spec.md"
        self.spec.write_text(
            "## ADDED Requirements\n\n"
            "### Requirement: Gestion des utilisateurs\n\n"
            "Le système SHALL gérer les utilisateurs.\n\n"
            "#### Scenario: Création d'un utilisateur\n"
            "- **WHEN** un utilisateur est créé\n"
            "- **THEN** il est enregistré\n\n"
            "#### Scenario: Suppression d'un utilisateur\n"
            "- **WHEN** un utilisateur est supprimé\n"
            "- **THEN** il est retiré\n\n"
            "### Requirement: Export CSV\n\n"
            "Le système SHALL exporter les données en CSV.\n\n"
            "#### Scenario: Export des données\n"
            "- **WHEN** l'utilisateur exporte\n"
            "- **THEN** un fichier CSV est produit\n",
            encoding="utf-8",
        )
        self.tests = self.root / "tests" / "test_users.py"
        self.tests.write_text(
            "import unittest\n\n"
            "class UsersTest(unittest.TestCase):\n"
            "    def test_creation_utilisateur(self):\n"
            "        pass\n\n"
            "class ExportTest(unittest.TestCase):\n"
            "    def test_export_csv(self):\n"
            "        pass\n",
            encoding="utf-8",
        )
        self.tasks = self.root / "tasks.md"
        self.tasks.write_text(
            "## 1. Socle\n"
            "- [x] 1.1 Gérer les utilisateurs\n"
            "- [ ] 1.2 Exporter en CSV\n",
            encoding="utf-8",
        )
        self.manifest = self.root / "traceability.yaml"
        self.manifest.write_text(
            "version: 1\n"
            "requirements:\n"
            '  "Gestion des utilisateurs":\n'
            "    tests:\n"
            "      - tests/test_users.py\n"
            '    tasks: ["1.1"]\n'
            "    scenarios:\n"
            '      "Création d\'un utilisateur":\n'
            '        - "tests/test_users.py::UsersTest.test_creation_utilisateur"\n'
            '  "Export CSV":\n'
            '    tasks: ["1.2"]\n',
            encoding="utf-8",
        )

    def test_matrice_synthetique(self) -> None:
        matrix = build_traceability_matrix(
            spec_paths=[self.spec],
            tasks_paths=[self.tasks],
            manifest_path=self.manifest,
            root=self.root,
        )
        self.assertEqual(matrix.stats["requirements"], 2)
        self.assertEqual(matrix.stats["scenarios"], 3)
        users = next(item for item in matrix.requirements if item.title == "Gestion des utilisateurs")
        export = next(item for item in matrix.requirements if item.title == "Export CSV")
        self.assertTrue(users.has_tests)
        self.assertEqual(len(users.tests), 2)
        self.assertEqual(len(users.tasks), 1)
        self.assertEqual(users.tasks[0].key, "1.1")
        self.assertTrue(users.tasks[0].checked)
        self.assertEqual(users.scenarios[0].title, "Création d'un utilisateur")
        self.assertEqual(len(users.scenarios[0].tests), 1)
        self.assertFalse(export.has_tests)
        self.assertIn(export.id, matrix.unverified_requirements)
        self.assertEqual(export.tasks[0].key, "1.2")
        self.assertEqual(export.tasks[0].checked, False)

        payload = traceability_to_dict(matrix)
        self.assertEqual(payload["stats"]["requirements"], 2)
        json.dumps(payload)

    def test_exigence_inconnue_refusee(self) -> None:
        self.manifest.write_text(
            "requirements:\n"
            '  "Exigence absente":\n'
            "    tasks: []\n",
            encoding="utf-8",
        )
        with self.assertRaises(TraceabilityError):
            build_traceability_matrix(
                spec_paths=[self.spec],
                tasks_paths=[self.tasks],
                manifest_path=self.manifest,
                root=self.root,
            )

    def test_test_absent_refuse(self) -> None:
        self.manifest.write_text(
            "requirements:\n"
            '  "Export CSV":\n'
            "    tests: [tests/absent.py]\n"
            "    tasks: []\n",
            encoding="utf-8",
        )
        with self.assertRaises((TraceabilityError, FileNotFoundError)):
            build_traceability_matrix(
                spec_paths=[self.spec],
                tasks_paths=[self.tasks],
                manifest_path=self.manifest,
                root=self.root,
            )

    def test_tache_absente_refusee(self) -> None:
        self.manifest.write_text(
            "requirements:\n"
            '  "Export CSV":\n'
            "    tests: []\n"
            '    tasks: ["9.9"]\n',
            encoding="utf-8",
        )
        with self.assertRaises(TraceabilityError):
            build_traceability_matrix(
                spec_paths=[self.spec],
                tasks_paths=[self.tasks],
                manifest_path=self.manifest,
                root=self.root,
            )

    def test_matrice_des_fichiers_reels(self) -> None:
        specs = sorted((REPO_ROOT / "openspec/changes/console-sdlc/specs").glob("*/spec.md"))
        tasks = [REPO_ROOT / "openspec/changes/console-sdlc/tasks.md"]
        manifest = REPO_ROOT / "docs/suivi/traceability.yaml"
        matrix = build_traceability_matrix(
            spec_paths=specs,
            tasks_paths=tasks,
            manifest_path=manifest,
            root=REPO_ROOT,
        )
        self.assertEqual(matrix.stats["requirements"], 58)
        self.assertEqual(matrix.stats["scenarios"], 107)
        self.assertGreater(matrix.stats["tests"], 0)
        by_title = {requirement.title: requirement for requirement in matrix.requirements}
        self.assertTrue(by_title["Projet multi-dépôts"].has_tests)
        self.assertTrue(by_title["Fichier de suivi ouvert dès qu'il est prêt"].has_tests)
        self.assertTrue(by_title["Vue d'ensemble"].has_tests)
        self.assertTrue(by_title["Liste et détail des features et tâches"].has_tests)
        self.assertTrue(by_title["Suivi synchrone tâche par tâche"].has_tests)
        self.assertTrue(by_title["Verdict de gate fondé sur des preuves"].has_tests)
        self.assertTrue(by_title["Gate de tests"].has_tests)
        self.assertTrue(by_title["Gate de couverture à trois seuils"].has_tests)
        self.assertTrue(by_title["Gate de sécurité"].has_tests)
        self.assertTrue(by_title["Gate de performance"].has_tests)
        self.assertTrue(by_title["Gate de données"].has_tests)
        self.assertTrue(by_title["Gate i18n"].has_tests)
        self.assertTrue(by_title["Support des langages par tiers"].has_tests)
        self.assertTrue(by_title["Dérogations datées"].has_tests)
        self.assertTrue(by_title["Source unique des seuils"].has_tests)
        self.assertTrue(by_title["Métriques d'équipe"].has_tests)
        self.assertFalse(by_title["Pagination serveur"].has_tests)
        self.assertIn(by_title["Pagination serveur"].id, matrix.unverified_requirements)


if __name__ == "__main__":
    unittest.main()
