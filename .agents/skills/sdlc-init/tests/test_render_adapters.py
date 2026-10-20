#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `scripts/render_adapters.py` (skill `sdlc-init`, lot 10).

Couvre : insertion du bloc délimité `sdlc-claude` dans un `CLAUDE.md` existant,
idempotence, création quand `CLAUDE.md` est absent, et inscription des
adaptateurs (fichiers créés + entrées ajoutées aux fichiers fusionnés) dans
`.sdlc/manifest.json`.

Lancement :
    python3 -m unittest discover -s .agents/skills/sdlc-init/tests

Les mini-projets de test sont créés sous `tests/tmp/` (dans le dépôt) puis
supprimés à la fin de chaque test.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(TESTS)
SCRIPT = os.path.join(SKILL, "scripts", "render_adapters.py")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SKILL)))
TEMPLATES = os.path.join(REPO_ROOT, "templates", "adapters")
TMP = os.path.join(TESTS, "tmp")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(root):
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            full = os.path.join(dirpath, name)
            out[os.path.relpath(full, root)] = sha256(full)
    return out


def config(enable_opencode=False):
    opencode = "true" if enable_opencode else "false"
    return (
        "version: 1\n"
        'project:\n  name: "Atlas"\n'
        "agents:\n"
        "  claude:\n    enabled: true\n    cli: \"claude -p\"\n"
        "    models:\n      think: opus\n      build: sonnet\n      light: haiku\n"
        "  codex:\n    enabled: false\n    cli: \"codex exec\"\n"
        "  opencode:\n    enabled: %s\n    cli: \"opencode run\"\n" % opencode
    )


class Base(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(TMP, ignore_errors=True)
        os.makedirs(TMP, exist_ok=True)
        self.proj = os.path.join(TMP, "projet")
        os.makedirs(self.proj, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(TMP, ignore_errors=True)

    def path(self, *parts):
        return os.path.join(self.proj, *parts)

    def render(self, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, self.proj, "--templates", TEMPLATES, *args],
            capture_output=True, text=True)

    def write_config(self, enable_opencode=False):
        write(self.path("sdlc.config.yaml"), config(enable_opencode))

    def manifest(self):
        return json.loads(read(self.path(".sdlc", "manifest.json")))


class BlocClaudeMdTest(Base):
    def test_bloc_insere_apres_agents_md_et_contenu_intact(self):
        original = "# Maison\n\nMa consigne personnelle.\n"
        write(self.path("CLAUDE.md"), original)
        self.write_config()

        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)

        content = read(self.path("CLAUDE.md"))
        self.assertTrue(content.startswith("@AGENTS.md\n\n<!-- sdlc-claude:begin v0.1.0 -->"))
        self.assertIn("<!-- sdlc-claude:end -->", content)
        # La directive @AGENTS.md n'est pas dupliquée.
        self.assertEqual(content.count("@AGENTS.md"), 2)  # directive + mention dans le corps
        self.assertEqual(content.count("<!-- sdlc-claude:begin"), 1)
        # Le contenu de l'humain est conservé, après le bloc.
        self.assertEqual(content.count(original), 1)
        self.assertLess(content.index("<!-- sdlc-claude:end -->"),
                        content.index("# Maison"))
        self.assertTrue(content.rstrip("\n").endswith("Ma consigne personnelle."))

    def test_deuxieme_passage_n_ecrit_rien(self):
        write(self.path("CLAUDE.md"), "# Maison\n")
        self.write_config()

        self.assertEqual(self.render().returncode, 0)
        before = snapshot(self.proj)

        second = self.render()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("0 fichier(s) écrit(s)", second.stdout)
        self.assertNotIn("[créé]", second.stdout)
        self.assertNotIn("[fusionné]", second.stdout)
        self.assertNotIn("[bloc ", second.stdout)
        self.assertEqual(snapshot(self.proj), before)

    def test_claude_md_absent_cree_avec_le_bloc(self):
        self.write_config()

        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)

        content = read(self.path("CLAUDE.md"))
        self.assertTrue(content.startswith("@AGENTS.md\n\n<!-- sdlc-claude:begin v0.1.0 -->"))
        self.assertIn("<!-- sdlc-claude:end -->", content)

        adapters = self.manifest()["adapters"]
        self.assertTrue(adapters["claude_md_block"])
        self.assertIn("CLAUDE.md", adapters["files"])
        self.assertEqual(adapters["files"]["CLAUDE.md"]["sha256"],
                         sha256(self.path("CLAUDE.md")))

    def test_bloc_remplace_si_la_version_change(self):
        write(self.path(".sdlc", "VERSION"), "1.0.0\n")
        original = "# Maison\n"
        write(self.path("CLAUDE.md"), original)
        self.write_config()

        self.assertEqual(self.render().returncode, 0)
        self.assertIn("<!-- sdlc-claude:begin v1.0.0 -->",
                      read(self.path("CLAUDE.md")))

        write(self.path(".sdlc", "VERSION"), "2.0.0\n")
        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)

        content = read(self.path("CLAUDE.md"))
        self.assertIn("<!-- sdlc-claude:begin v2.0.0 -->", content)
        self.assertNotIn("v1.0.0", content)
        self.assertEqual(content.count("<!-- sdlc-claude:begin"), 1)
        self.assertIn(original, content)


class ManifestAdaptateursTest(Base):
    def test_fichiers_crees_et_entrees_fusionnees_inscrits(self):
        original_settings = json.dumps(
            {"permissions": {"allow": ["Bash(ls:*)"]}},
            ensure_ascii=False, indent=2) + "\n"
        write(self.path(".claude", "settings.json"), original_settings)
        original_opencode = json.dumps(
            {"$schema": "https://exemple.test/config.json"},
            ensure_ascii=False, indent=2) + "\n"
        write(self.path("opencode.json"), original_opencode)
        self.write_config(enable_opencode=True)

        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)

        adapters = self.manifest()["adapters"]

        # Fichiers créés : empreinte enregistrée pour la désinstallation.
        for rel in (".claude/agents/implementer.md",
                    ".claude/agents/reviewer.md",
                    ".opencode/agent/implementer.md"):
            self.assertIn(rel, adapters["files"], rel)
            self.assertEqual(adapters["files"][rel]["sha256"],
                             sha256(self.path(*rel.split("/"))), rel)

        # Fichiers fusionnés : seules les entrées ajoutées sont enregistrées.
        settings_ops = adapters["merged"][".claude/settings.json"]
        self.assertTrue(any(op["op"] == "append_list"
                            and op["path"] == ["permissions", "allow"]
                            and "Bash(claude -p:*)" in op["items"]
                            for op in settings_ops))
        self.assertTrue(any(op["op"] == "set_key"
                            and op["path"] == ["permissions", "deny"]
                            for op in settings_ops))
        # L'entrée de l'humain n'est jamais inscrite comme ajoutée.
        self.assertFalse(any(op.get("items") and "Bash(ls:*)" in op["items"]
                             for op in settings_ops))

        opencode_ops = adapters["merged"]["opencode.json"]
        self.assertTrue(any(op["op"] == "set_key"
                            and op["path"] == ["permission"]
                            for op in opencode_ops))
        self.assertFalse(any(op["op"] == "set_key"
                             and op["path"] == ["$schema"]
                             for op in opencode_ops))

        # Les fichiers de l'humain sont conservés.
        merged_settings = json.loads(read(self.path(".claude", "settings.json")))
        self.assertIn("Bash(ls:*)", merged_settings["permissions"]["allow"])
        self.assertIn("Bash(claude -p:*)", merged_settings["permissions"]["allow"])

    def test_manifeste_minimal_si_absent(self):
        # Aucun manifeste : render_adapters en crée un minimal mais lisible.
        self.write_config()
        self.assertEqual(self.render().returncode, 0)
        manifest = self.manifest()
        self.assertIn("adapters", manifest)
        self.assertEqual(manifest["adapters"]["version"], "0.1.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
