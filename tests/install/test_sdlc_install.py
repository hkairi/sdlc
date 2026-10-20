#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de l'installateur ``bin/sdlc-install`` (tâches 9.1, 9.2, 9.3).

Les projets cibles sont créés dans ``tests/install/tmp/`` puis supprimés : tout
accès hors du dépôt est refusé dans cet environnement.

Lancement : ``python3 tests/install/test_sdlc_install.py`` (ou ``-m unittest``).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
INSTALL = os.path.join(REPO_ROOT, "bin", "sdlc-install")
EXAMPLE_CONFIG = os.path.join(REPO_ROOT, "sdlc.config.example.yaml")
TMP_ROOT = os.path.join(HERE, "tmp")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def snapshot(root):
    """Empreinte de l'arborescence : fichiers, dossiers et liens symboliques."""
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if os.path.islink(full):
                snap[rel] = ("lien", os.readlink(full))
            elif os.path.isdir(full):
                snap[rel] = ("dossier", None)
            else:
                snap[rel] = ("fichier", sha256(full))
    return snap


class BaseInstallTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(TMP_ROOT, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        try:
            if not os.listdir(TMP_ROOT):
                os.rmdir(TMP_ROOT)
        except OSError:
            pass

    def setUp(self):
        self.proj = tempfile.mkdtemp(prefix="projet-", dir=TMP_ROOT)

    def tearDown(self):
        shutil.rmtree(self.proj, ignore_errors=True)

    def path(self, *parts):
        return os.path.join(self.proj, *parts)

    def run_install(self, *args):
        result = subprocess.run(
            [sys.executable, INSTALL, "--target", self.proj, *args],
            capture_output=True, text=True)
        return result

    def test_framework_version_readable(self):
        self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, "VERSION")))
        self.assertEqual(read(os.path.join(REPO_ROOT, "VERSION")).strip(),
                         "0.1.0")


class ProjetVideTest(BaseInstallTest):
    def test_installation_complete(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)

        # Espace .sdlc/
        self.assertEqual(read(self.path(".sdlc", "VERSION")).strip(), "0.1.0")
        self.assertTrue(os.path.isfile(self.path(".sdlc", "workflow-sdlc.md")))
        self.assertTrue(os.path.isfile(
            self.path(".sdlc", "templates", "docs", "brief.md")))

        manifest = json.loads(read(self.path(".sdlc", "manifest.json")))
        self.assertEqual(manifest["framework_version"], "0.1.0")
        self.assertIn(".sdlc/VERSION", manifest["files"])
        self.assertIn(".agents/skills/adr/SKILL.md", manifest["files"])
        self.assertEqual(
            manifest["files"][".sdlc/VERSION"]["sha256"],
            sha256(self.path(".sdlc", "VERSION")))

        # Skills et lien .claude/skills
        self.assertTrue(os.path.isfile(
            self.path(".agents", "skills", "adr", "SKILL.md")))
        link = self.path(".claude", "skills")
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.readlink(link), "../.agents/skills")

        # AGENTS.md, CLAUDE.md, .gitignore
        agents = read(self.path("AGENTS.md"))
        self.assertTrue(agents.startswith("<!-- sdlc:begin v0.1.0 -->"))
        self.assertIn("<!-- sdlc:end -->", agents)
        self.assertEqual(read(self.path("CLAUDE.md")), "@AGENTS.md\n")
        gitignore = read(self.path(".gitignore"))
        for line in ("/reports/", "__pycache__/", "*.py[cod]"):
            self.assertIn(line, gitignore)

    def test_projet_existant_non_detruit(self):
        write(self.path("AGENTS.md"), "# AGENTS a moi\n\ndes regles\n")
        write(self.path("CLAUDE.md"), "# CLAUDE a moi\n")
        write(self.path(".gitignore"), "node_modules/\n")
        write(self.path("README.md"), "# README a moi\n")
        write(self.path("templates", "own.md"), "gabarit a moi\n")

        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)

        # Rien de ce qui appartient au projet n'est perdu
        self.assertEqual(read(self.path("README.md")), "# README a moi\n")
        self.assertEqual(read(self.path("templates", "own.md")), "gabarit a moi\n")

        agents = read(self.path("AGENTS.md"))
        self.assertTrue(agents.startswith("<!-- sdlc:begin v0.1.0 -->"))
        self.assertTrue(agents.rstrip("\n").endswith("des regles"))
        self.assertIn("# AGENTS a moi", agents)

        claude = read(self.path("CLAUDE.md"))
        self.assertTrue(claude.startswith("@AGENTS.md"))
        self.assertIn("# CLAUDE a moi", claude)

        gitignore = read(self.path(".gitignore"))
        self.assertIn("node_modules/", gitignore)
        self.assertIn("/reports/", gitignore)

    def test_conflit_de_skill(self):
        write(self.path(".agents", "skills", "adr", "SKILL.md"),
              "skill differente de l'humain\n")

        result = self.run_install()

        self.assertIn("conflit", result.stdout)
        self.assertIn(".agents/skills/adr", result.stdout)
        self.assertEqual(
            read(self.path(".agents", "skills", "adr", "SKILL.md")),
            "skill differente de l'humain\n")
        # Les autres skills sont bien copiées
        self.assertTrue(os.path.isfile(
            self.path(".agents", "skills", "tdd", "SKILL.md")))

    def test_claude_skills_dossier_reel(self):
        os.makedirs(self.path(".claude", "skills"))
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        link = self.path(".claude", "skills", "adr")
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.readlink(link), "../../.agents/skills/adr")
        # Le dossier réel n'est pas remplacé
        self.assertTrue(os.path.isdir(self.path(".claude", "skills")))

    def test_idempotence(self):
        first = self.run_install()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = snapshot(self.proj)

        second = self.run_install()
        self.assertEqual(second.returncode, 0, second.stderr)
        after = snapshot(self.proj)

        self.assertEqual(before, after)
        self.assertNotIn("créer", second.stdout)
        self.assertNotIn("remplacer", second.stdout)

    def test_dry_run_n_ecrit_rien(self):
        result = self.run_install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("créer", result.stdout)
        self.assertIn("--dry-run", result.stdout)

        self.assertFalse(os.path.exists(self.path(".sdlc")))
        self.assertFalse(os.path.exists(self.path("AGENTS.md")))
        self.assertFalse(os.path.exists(self.path("CLAUDE.md")))
        self.assertFalse(os.path.exists(self.path(".gitignore")))
        self.assertFalse(os.path.exists(self.path(".agents")))
        self.assertFalse(os.path.exists(self.path(".claude")))
        self.assertEqual(os.listdir(self.proj), [])


class UpgradeTest(BaseInstallTest):
    def test_upgrade_conserve_fichier_modifie_par_humain(self):
        self.run_install()
        target = self.path(".sdlc", "templates", "docs", "brief.md")
        write(target, "MODIFIE PAR L'HUMAIN\n")

        result = self.run_install("--upgrade")

        self.assertIn("conserver", result.stdout)
        self.assertIn("modifié", result.stdout)
        self.assertEqual(read(target), "MODIFIE PAR L'HUMAIN\n")

    def test_upgrade_remplace_fichier_non_modifie(self):
        self.run_install()
        rel = ".sdlc/templates/docs/brief.md"
        target = self.path(*rel.split("/"))
        # Simulation d'une installation d'une version antérieure du framework :
        # le fichier correspond au manifeste (non modifié) mais diffère du source.
        old = "ANCIENNE VERSION DU GABARIT\n"
        write(target, old)
        manifest_path = self.path(".sdlc", "manifest.json")
        manifest = json.loads(read(manifest_path))
        manifest["files"][rel]["sha256"] = hashlib.sha256(
            old.encode("utf-8")).hexdigest()
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)

        result = self.run_install("--upgrade")

        self.assertIn("remplacer", result.stdout)
        source = os.path.join(REPO_ROOT, "templates", "docs", "brief.md")
        self.assertEqual(read(target), read(source))

    def test_upgrade_force_ecrase_fichier_modifie(self):
        self.run_install()
        target = self.path(".sdlc", "templates", "docs", "brief.md")
        write(target, "MODIFIE PAR L'HUMAIN\n")

        result = self.run_install("--upgrade", "--force")

        self.assertIn("remplacer", result.stdout)
        source = os.path.join(REPO_ROOT, "templates", "docs", "brief.md")
        self.assertEqual(read(target), read(source))

    def test_upgrade_remplace_bloc_delimite(self):
        self.run_install()
        agents = self.path("AGENTS.md")
        content = read(agents).replace("<!-- sdlc:begin v0.1.0 -->",
                                       "<!-- sdlc:begin v0.0.9 -->")
        write(agents, content)

        result = self.run_install("--upgrade")

        self.assertIn("bloc remplacé", result.stdout)
        self.assertIn("<!-- sdlc:begin v0.1.0 -->", read(agents))
        self.assertNotIn("<!-- sdlc:begin v0.0.9 -->", read(agents))


class UninstallTest(BaseInstallTest):
    def test_uninstall_restaure_les_fichiers_du_projet(self):
        original_agents = "# AGENTS a moi\n\ndes regles\n"
        original_claude = "# CLAUDE a moi\n"
        original_gitignore = "node_modules/\n"
        write(self.path("AGENTS.md"), original_agents)
        write(self.path("CLAUDE.md"), original_claude)
        write(self.path(".gitignore"), original_gitignore)

        self.run_install()
        result = self.run_install("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)

        self.assertEqual(read(self.path("AGENTS.md")), original_agents)
        self.assertEqual(read(self.path("CLAUDE.md")), original_claude)
        self.assertEqual(read(self.path(".gitignore")), original_gitignore)

        self.assertFalse(os.path.exists(self.path(".sdlc")))
        self.assertFalse(os.path.exists(self.path(".agents")))
        self.assertFalse(os.path.exists(self.path(".claude")))
        self.assertFalse(os.path.exists(self.path(".gitignore") + ".orig"))

    def test_uninstall_supprime_les_fichiers_crees(self):
        self.run_install()
        self.run_install("--uninstall")
        self.assertFalse(os.path.exists(self.path("AGENTS.md")))
        self.assertFalse(os.path.exists(self.path("CLAUDE.md")))
        self.assertFalse(os.path.exists(self.path(".gitignore")))

    def test_uninstall_liste_les_fichiers_modifies(self):
        self.run_install()
        target = self.path(".sdlc", "templates", "docs", "brief.md")
        write(target, "MODIFIE\n")

        result = self.run_install("--uninstall")

        self.assertIn("à retirer à la main", result.stdout.lower())
        self.assertTrue(os.path.isfile(target))


class AdaptateursInstallTest(BaseInstallTest):
    """Installation + `render_adapters.py` + `--uninstall` (lot 10).

    Vérifie que la désinstallation retire les adaptateurs non modifiés, les
    entrées ajoutées aux fichiers fusionnés, le bloc `sdlc-claude` de
    `CLAUDE.md` et les dossiers devenus vides, sans toucher au contenu de
    l'humain.
    """

    SETTINGS_ORIGINAL = json.dumps(
        {"permissions": {"allow": ["Bash(ls:*)"]}},
        ensure_ascii=False, indent=2) + "\n"
    OPENCODE_ORIGINAL = json.dumps(
        {"$schema": "https://exemple.test/config.json"},
        ensure_ascii=False, indent=2) + "\n"
    CLAUDE_ORIGINAL = "# Notes maison\n\nMes propres consignes.\n"

    def write_config(self):
        text = read(EXAMPLE_CONFIG)
        text = text.replace("  opencode:\n    enabled: false",
                            "  opencode:\n    enabled: true")
        write(self.path("sdlc.config.yaml"), text)

    def run_render(self, *args):
        script = self.path(".agents", "skills", "sdlc-init", "scripts",
                           "render_adapters.py")
        return subprocess.run(
            [sys.executable, script, self.proj, *args],
            capture_output=True, text=True)

    def write_human_files(self):
        write(self.path("CLAUDE.md"), self.CLAUDE_ORIGINAL)
        write(self.path(".claude", "settings.json"), self.SETTINGS_ORIGINAL)
        write(self.path("opencode.json"), self.OPENCODE_ORIGINAL)

    def prepare(self):
        self.write_human_files()
        self.write_config()
        self.assertEqual(self.run_install().returncode, 0)
        result = self.run_render()
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_render_insere_le_bloc_claude(self):
        self.prepare()
        content = read(self.path("CLAUDE.md"))
        self.assertTrue(content.startswith(
            "@AGENTS.md\n\n<!-- sdlc-claude:begin v0.1.0 -->"))
        self.assertIn("<!-- sdlc-claude:end -->", content)
        self.assertIn(self.CLAUDE_ORIGINAL, content)

        manifest = json.loads(read(self.path(".sdlc", "manifest.json")))
        adapters = manifest["adapters"]
        self.assertTrue(adapters["claude_md_block"])
        self.assertIn(".claude/agents/implementer.md", adapters["files"])
        self.assertIn(".codex/config.toml", adapters["files"])
        self.assertIn(".opencode/agent/implementer.md", adapters["files"])
        self.assertIn(".claude/settings.json", adapters["merged"])

    def test_render_distribue_le_plugin_ai_sdlc_tracker(self):
        """Le plugin de suivi part dans `.opencode/plugins/` (copie récursive)."""
        self.prepare()

        plugin = self.path(".opencode", "plugins", "ai-sdlc-tracker")
        for rel in ("index.ts", "core.ts", "tools/check.ts", "hooks/commit-guard.ts",
                    "package.json", "GUIDE.md"):
            self.assertTrue(os.path.isfile(os.path.join(plugin, *rel.split("/"))), rel)

        manifest = json.loads(read(self.path(".sdlc", "manifest.json")))
        files = manifest["adapters"]["files"]
        self.assertIn(".opencode/plugins/ai-sdlc-tracker/index.ts", files)
        self.assertIn(".opencode/plugins/ai-sdlc-tracker/GUIDE.md", files)

        # Ni les tests du dépôt d'origine (fixtures propres), ni node_modules.
        self.assertFalse(os.path.exists(os.path.join(plugin, "tests")))
        self.assertFalse(os.path.exists(os.path.join(plugin, "node_modules")))

    def test_render_deuxieme_passage_sans_ecriture(self):
        self.prepare()
        before = snapshot(self.proj)
        second = self.run_render()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("0 fichier(s) écrit(s)", second.stdout)
        self.assertEqual(snapshot(self.proj), before)

    def test_render_dry_run_n_ecrit_rien(self):
        self.write_human_files()
        self.write_config()
        self.assertEqual(self.run_install().returncode, 0)
        before = snapshot(self.proj)
        claude_before = read(self.path("CLAUDE.md"))

        result = self.run_render("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(snapshot(self.proj), before)
        self.assertFalse(os.path.exists(self.path(".claude", "agents")))
        self.assertFalse(os.path.exists(self.path(".codex")))
        self.assertEqual(read(self.path("CLAUDE.md")), claude_before)

    def test_uninstall_restaure_le_projet(self):
        self.prepare()
        result = self.run_install("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)

        for rel in (".claude/agents", ".claude/commands", ".codex", ".opencode"):
            self.assertFalse(os.path.exists(self.path(*rel.split("/"))), rel)
        self.assertEqual(read(self.path("CLAUDE.md")), self.CLAUDE_ORIGINAL)
        self.assertEqual(read(self.path(".claude", "settings.json")),
                         self.SETTINGS_ORIGINAL)
        self.assertEqual(read(self.path("opencode.json")), self.OPENCODE_ORIGINAL)

    def test_uninstall_dry_run_restaure_sans_ecrire(self):
        self.prepare()
        before = snapshot(self.proj)
        result = self.run_install("--uninstall", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(snapshot(self.proj), before)
        self.assertIn("--dry-run", result.stdout)

    def test_uninstall_conserve_et_liste_un_adaptateur_modifie(self):
        self.prepare()
        target = self.path(".claude", "agents", "implementer.md")
        write(target, "MODIFIÉ PAR L'HUMAIN\n")

        result = self.run_install("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.path.isfile(target))
        self.assertEqual(read(target), "MODIFIÉ PAR L'HUMAIN\n")
        self.assertIn(".claude/agents/implementer.md", result.stdout)
        self.assertIn("à retirer à la main", result.stdout.lower())
        # Les autres adaptateurs non modifiés sont bien retirés.
        self.assertFalse(os.path.exists(self.path(".codex")))


class RefusTest(BaseInstallTest):
    def test_refus_dans_le_depot_du_framework(self):
        result = subprocess.run(
            [sys.executable, INSTALL, "--target", REPO_ROOT],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("refus", result.stderr.lower())

    def test_refus_chemin_inexistant(self):
        missing = self.path("n-existe-pas")
        result = subprocess.run(
            [sys.executable, INSTALL, "--target", missing],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("inexistant", result.stderr.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
