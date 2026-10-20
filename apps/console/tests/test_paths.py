"""Tests du confinement des chemins d'ingestion."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from sdlc_console.paths import PathSecurityError, resolve_within


class ResolveWithinTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "reports").mkdir()
        (self.root / "reports" / "junit.xml").write_text("<testsuite/>", encoding="utf-8")

    def test_chemin_interne(self) -> None:
        resolved = resolve_within(self.root, "reports/junit.xml")
        self.assertEqual(resolved, (self.root / "reports" / "junit.xml").resolve())

    def test_chemin_absolu_interne(self) -> None:
        absolute = (self.root / "reports" / "junit.xml").resolve()
        self.assertEqual(resolve_within(self.root, absolute), absolute)

    def test_traversee_parent_refusee(self) -> None:
        with self.assertRaises(PathSecurityError):
            resolve_within(self.root, "../outside.txt")

    def test_chemin_absolu_externe_refuse(self) -> None:
        with self.assertRaises(PathSecurityError):
            resolve_within(self.root, "/etc/passwd")

    def test_secret_refuse(self) -> None:
        for name in (".env", ".env.local", "server.pem", "id_rsa.key"):
            with self.subTest(name=name), self.assertRaises(PathSecurityError):
                resolve_within(self.root, name, allow_missing=True)

    def test_dossier_secrets_refuse(self) -> None:
        with self.assertRaises(PathSecurityError):
            resolve_within(self.root, "secrets/github.txt", allow_missing=True)

    @unittest.skipIf(os.name == "nt", "liens symboliques non fiables sous Windows")
    def test_lien_symbolique_hors_perimetre_refuse(self) -> None:
        outside = self.root.parent / "outside-secret.txt"
        outside.write_text("secret", encoding="utf-8")
        self.addCleanup(outside.unlink)
        link = self.root / "lien"
        link.symlink_to(outside)
        with self.assertRaises(PathSecurityError):
            resolve_within(self.root, "lien")

    def test_fichier_absent(self) -> None:
        with self.assertRaises(FileNotFoundError):
            resolve_within(self.root, "absent.txt")

    def test_allow_missing(self) -> None:
        resolved = resolve_within(self.root, "nouveau.txt", allow_missing=True)
        self.assertEqual(resolved, (self.root / "nouveau.txt").resolve())


if __name__ == "__main__":
    unittest.main()
