"""Tests de redaction des secrets."""

from __future__ import annotations

import unittest

from sdlc_console.redaction import redact


class RedactionTest(unittest.TestCase):
    def test_jeton_github(self) -> None:
        self.assertEqual(redact("ghp_abcdefghijklmnopqrstuvwxyz0123456789"), "***")

    def test_jeton_gitlab(self) -> None:
        self.assertEqual(redact("glpat-abcdefghijklmnopqrstuvwxyz"), "***")

    def test_bearer(self) -> None:
        self.assertEqual(redact("Authorization: Bearer abc.def.ghi"), "Authorization: Bearer ***")

    def test_paire_cle_valeur(self) -> None:
        self.assertEqual(redact("token=abc123, ok"), "token=***, ok")
        self.assertEqual(redact("password: hunter2"), "password=***")

    def test_cle_aws(self) -> None:
        self.assertEqual(redact("AKIAABCDEFGHIJKLMNOP"), "***")

    def test_texte_propre_inchange(self) -> None:
        self.assertEqual(redact("build réussi en 42 s"), "build réussi en 42 s")

    def test_plusieurs_secrets(self) -> None:
        result = redact("ghp_abcdefghijklmnopqrstuvwxyz0123456789 et token=abc")
        self.assertNotIn("ghp_", result)
        self.assertNotIn("abc", result)


if __name__ == "__main__":
    unittest.main()
