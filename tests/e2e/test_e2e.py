#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de bout en bout du framework sur deux projets existants simulés (tâche 9.7).

Deux projets sont créés dans des dossiers temporaires **sous** ``tests/e2e/tmp/``
(chemins dans le dépôt, supprimés en fin de test) puis traversent la chaîne réelle
du framework : installation, détection, adaptateurs, ADR, CI, suivi, mise à jour,
désinstallation.

1. **Django** : ``README.md``, ``AGENTS.md`` et ``CLAUDE.md`` maison, ``.gitignore``,
   ``templates/`` de pages HTML, ``requirements.txt``, un test pytest minimal,
   ``.github/workflows/ci.yml`` existant, ``docs/`` d'un autre agencement
   (``docs/decisions/`` pour les ADR).
2. **Node** : ``package.json`` (scripts ``test`` et ``lint``), ``.gitlab-ci.yml``
   existant, ``openspec/`` déjà initialisé avec un change contenant un ``tasks.md``.

Lancement : ``python3 -m unittest discover -s tests/e2e``.
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
TMP_ROOT = os.path.join(HERE, "tmp")
INSTALL = os.path.join(REPO_ROOT, "bin", "sdlc-install")
EXAMPLE_CONFIG = os.path.join(REPO_ROOT, "sdlc.config.example.yaml")


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
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
    """Empreinte de l'arborescence : fichiers, dossiers et liens symboliques.

    Les liens vers des dossiers ne sont pas parcourus (pas de descente).
    """
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


def run(args, cwd=None, env=None):
    full_env = dict(os.environ)
    # Aucun cache __pycache__ ne doit être écrit dans le projet simulé (il
    # empêcherait la désinstallation de nettoyer .agents/).
    full_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        full_env.update(env)
    return subprocess.run(args, cwd=cwd, env=full_env, capture_output=True, text=True)


def run_install(project, *args):
    return run([sys.executable, INSTALL, "--target", project, *args])


FAUX_CONTROLES = '''# -*- coding: utf-8 -*-
"""Émet des rapports JUnit et Cobertura minimaux (simulation de commandes projet)."""
import os
import sys

JUNIT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites tests="2" failures="0" errors="0">
  <testsuite name="demo" tests="2" failures="0" errors="0" skipped="0" time="0.01">
    <testcase classname="demo.tests" name="test_ok" time="0.005"/>
    <testcase classname="demo.tests" name="test_autre" time="0.005"/>
  </testsuite>
</testsuites>
"""

COBERTURA = """<?xml version="1.0" ?>
<coverage line-rate="0.95" branch-rate="0.9" version="7.0" timestamp="0">
  <sources><source>.</source></sources>
  <packages>
    <package name="demo" line-rate="0.95" branch-rate="0.9">
      <classes>
        <class name="demo.core" filename="demo/core.py" line-rate="0.95" branch-rate="0.9">
          <methods/>
          <lines>
            <line number="1" hits="5"/>
            <line number="2" hits="0"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""

kind = sys.argv[1] if len(sys.argv) > 1 else ""
if kind == "junit":
    os.makedirs("reports/junit", exist_ok=True)
    with open("reports/junit/tests.xml", "w", encoding="utf-8") as fh:
        fh.write(JUNIT)
elif kind == "cobertura":
    os.makedirs("reports/coverage", exist_ok=True)
    with open("reports/coverage/cobertura.xml", "w", encoding="utf-8") as fh:
        fh.write(COBERTURA)
else:
    sys.exit("type inconnu : %r" % kind)
'''


# ---------------------------------------------------------------------------
# Base commune aux deux projets existants
# ---------------------------------------------------------------------------
class ProjetExistantE2E:
    """Mixin : la chaîne complète, partagée par les deux projets simulés.

    Ce n'est pas un ``TestCase`` (sinon il serait collecté et échouerait faute de
    fixture) ; les classes concrètes héritent aussi de ``unittest.TestCase``.
    """

    PREFIX = "e2e-"

    # -- cycle de vie --------------------------------------------------------
    @classmethod
    def setUpClass(cls):
        os.makedirs(TMP_ROOT, exist_ok=True)
        cls.proj = tempfile.mkdtemp(prefix=cls.PREFIX, dir=TMP_ROOT)
        cls.info = {}
        cls.build_fixture()
        cls.info["protected"] = cls.protected_hashes()
        cls.info["agents_original"] = read(cls.path("AGENTS.md"))
        cls.info["claude_original"] = read(cls.path("CLAUDE.md"))
        cls.info["gitignore_original"] = read(cls.path(".gitignore"))
        cls.info["settings_original"] = cls.read_if_exists(".claude", "settings.json")

        # 1. Simulation (aucune écriture), puis installation réelle.
        cls.info["listing_before_dry"] = snapshot(cls.proj)
        cls.info["dry_run"] = run_install(cls.proj, "--dry-run")
        cls.info["listing_after_dry"] = snapshot(cls.proj)
        cls.info["install"] = run_install(cls.proj)
        cls.info["protected_after_install"] = cls.protected_hashes()
        # Preuves capturées juste après l'installation (la chaîne se poursuit
        # jusqu'à la désinstallation, qui retire ces fichiers).
        cls.info["install_space"] = {
            "brief": os.path.isfile(cls.path(".sdlc", "templates", "docs", "brief.md")),
            "manifest": os.path.isfile(cls.path(".sdlc", "manifest.json")),
            "skill": os.path.isfile(cls.path(".agents", "skills", "sdlc-init", "SKILL.md")),
            "claude_link": (
                os.path.islink(cls.path(".claude", "skills")),
                os.readlink(cls.path(".claude", "skills"))
                if os.path.islink(cls.path(".claude", "skills")) else None,
            ),
        }
        cls.info["agents_after_install"] = read(cls.path("AGENTS.md"))
        cls.info["claude_after_install"] = read(cls.path("CLAUDE.md"))
        cls.info["gitignore_after_install"] = read(cls.path(".gitignore"))

        # 2. Détection.
        cls.info["detect"] = cls.run_detect()

        # 3. Configuration (sdlc.config.yaml) puis adaptateurs.
        cls.write_config()
        cls.info["render"] = cls.run_render()
        cls.info["claude_after_render"] = read(cls.path("CLAUDE.md"))
        cls.info["adapters"] = cls.collect_adapters()
        # Second passage : aucun fichier ne doit être réécrit (idempotence).
        cls.info["snap_after_render"] = snapshot(cls.proj)
        cls.info["render2"] = cls.run_render()
        cls.info["snap_after_render2"] = snapshot(cls.proj)

        # 4. ADR.
        cls.info["adr"] = cls.run_adr()

        # 5. CI : scripts copiés puis contrôles exécutés.
        cls.info["ci"] = cls.run_ci()

        # 6. Étapes propres au projet (suivi OpenSpec pour Node).
        cls.extra_chain()

        # 7. Idempotence de l'installation.
        cls.info["snap_before_install2"] = snapshot(cls.proj)
        cls.info["install2"] = run_install(cls.proj)
        cls.info["snap_after_install2"] = snapshot(cls.proj)

        # 8. Mise à jour : un fichier humain n'est pas écrasé.
        cls.info["protected_before_upgrade"] = cls.protected_hashes()
        cls.edit_framework_file()
        cls.info["upgrade"] = run_install(cls.proj, "--upgrade")
        cls.info["fw_file_after_upgrade"] = read(
            cls.path(".sdlc", "templates", "docs", "brief.md"))
        cls.info["protected_after_upgrade"] = cls.protected_hashes()
        cls.info["agents_after_upgrade"] = read(cls.path("AGENTS.md"))
        cls.restore_framework_file()

        # 9. Désinstallation.
        cls.info["uninstall"] = run_install(cls.proj, "--uninstall")
        cls.info["agents_after_uninstall"] = cls.read_if_exists("AGENTS.md")
        cls.info["claude_after_uninstall"] = cls.read_if_exists("CLAUDE.md")
        cls.info["gitignore_after_uninstall"] = cls.read_if_exists(".gitignore")
        cls.info["sdlc_after_uninstall"] = os.path.exists(cls.path(".sdlc"))
        cls.info["agents_dir_after_uninstall"] = os.path.exists(cls.path(".agents"))
        cls.info["adapters_after_uninstall"] = {
            "claude_agents": os.path.exists(cls.path(".claude", "agents")),
            "claude_commands": os.path.exists(cls.path(".claude", "commands")),
            "codex": os.path.exists(cls.path(".codex")),
            "opencode": os.path.exists(cls.path(".opencode")),
        }
        cls.info["settings_after_uninstall"] = cls.read_if_exists(
            ".claude", "settings.json")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.proj, ignore_errors=True)
        try:
            if not os.listdir(TMP_ROOT):
                os.rmdir(TMP_ROOT)
        except OSError:
            pass

    # -- helpers -------------------------------------------------------------
    @classmethod
    def path(cls, *parts):
        return os.path.join(cls.proj, *parts)

    @classmethod
    def read_if_exists(cls, *parts):
        full = cls.path(*parts)
        return read(full) if os.path.isfile(full) else None

    @classmethod
    def protected_hashes(cls):
        out = {}
        for rel in cls.PROTECTED:
            full = cls.path(*rel.split("/"))
            if os.path.isfile(full):
                out[rel] = sha256(full)
        return out

    @classmethod
    def run_detect(cls):
        detect = cls.path(".agents", "skills", "sdlc-init", "scripts", "detect.sh")
        result = run(["bash", detect, cls.proj], cwd=cls.proj)
        payload = None
        if result.returncode == 0:
            payload = json.loads(result.stdout)
        return {"result": result, "payload": payload}

    @classmethod
    def run_render(cls):
        script = cls.path(".agents", "skills", "sdlc-init", "scripts", "render_adapters.py")
        return run([sys.executable, script, cls.proj], cwd=cls.proj)

    @classmethod
    def collect_adapters(cls):
        """Contenu des fichiers d'adaptateurs réellement écrits."""
        out = {}
        for base in (".claude", ".codex", ".opencode"):
            root = cls.path(base)
            if not os.path.isdir(root):
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, cls.proj)
                    try:
                        out[rel] = read(full)
                    except (OSError, UnicodeDecodeError):
                        out[rel] = None
        return out

    @classmethod
    def run_adr(cls):
        script = cls.path(".agents", "skills", "adr", "scripts", "new_adr.py")
        return run([sys.executable, script, cls.proj, "--titre",
                    "Cible de déploiement et CI", "--statut", "accepté",
                    "--date", "2026-10-11"], cwd=cls.proj)

    @classmethod
    def run_ci(cls):
        # Copies à l'identique, comme le ferait ci-setup.
        scripts_dir = cls.path("scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        for name in ("ci.sh", "check_thresholds.py"):
            shutil.copy2(cls.path(".sdlc", "templates", "scripts", name),
                         os.path.join(scripts_dir, name))
        os.chmod(os.path.join(scripts_dir, "ci.sh"), 0o755)
        write(cls.path("outils", "faux_controles.py"), FAUX_CONTROLES)

        env = {
            "SDLC_LINT_CMD": "true",
            "SDLC_TEST_CMD": "python3 outils/faux_controles.py junit",
            "SDLC_COVERAGE_CMD": "python3 outils/faux_controles.py cobertura",
            "SDLC_SAST_CMD": "true",
            "SDLC_DEPS_CMD": "true",
            "SDLC_SECRETS_CMD": "true",
            "SDLC_BUILD_CMD": "true",
        }
        result = run(["bash", cls.path("scripts", "ci.sh")], cwd=cls.proj, env=env)
        summary = None
        summary_path = cls.path("reports", "summary.json")
        if os.path.isfile(summary_path):
            summary = json.loads(read(summary_path))
        return {"result": result, "summary": summary}

    @classmethod
    def edit_framework_file(cls):
        cls.info["fw_file_outside"] = "MODIFIÉ PAR L'HUMAIN\n"
        write(cls.path(".sdlc", "templates", "docs", "brief.md"),
              cls.info["fw_file_outside"])

    @classmethod
    def restore_framework_file(cls):
        source = os.path.join(REPO_ROOT, "templates", "docs", "brief.md")
        shutil.copy2(source, cls.path(".sdlc", "templates", "docs", "brief.md"))

    @classmethod
    def extra_chain(cls):
        """Étapes supplémentaires propres à un projet (surchargé par Node)."""

    # -- assertions partagées -------------------------------------------------
    def test_01_dry_run_n_ecrit_rien(self):
        self.assertEqual(self.info["dry_run"].returncode, 0, self.info["dry_run"].stderr)
        self.assertIn("créer", self.info["dry_run"].stdout)
        self.assertIn("--dry-run", self.info["dry_run"].stdout)
        self.assertEqual(self.info["listing_before_dry"], self.info["listing_after_dry"])

    def test_02_installation_cree_lespace_framework(self):
        self.assertEqual(self.info["install"].returncode, 0, self.info["install"].stderr)
        space = self.info["install_space"]
        self.assertTrue(space["brief"], ".sdlc/templates/docs/brief.md absent")
        self.assertTrue(space["manifest"], ".sdlc/manifest.json absent")
        self.assertTrue(space["skill"], ".agents/skills/sdlc-init/SKILL.md absent")
        self.assertEqual(space["claude_link"], (True, "../.agents/skills"))

    def test_03_fichiers_du_projet_intacts(self):
        # L'installation ne touche aucun fichier du projet.
        self.assertEqual(self.info["protected"], self.info["protected_after_install"])
        # La mise à jour non plus (comparaison juste avant / juste après).
        self.assertEqual(self.info["protected_before_upgrade"],
                         self.info["protected_after_upgrade"])

    def test_04_fusion_non_destructive(self):
        agents = self.info["agents_after_install"]
        self.assertTrue(agents.startswith("<!-- sdlc:begin v0.1.0 -->"))
        self.assertIn("<!-- sdlc:end -->", agents)
        self.assertIn(self.info["agents_original"], agents)
        claude = self.info["claude_after_install"]
        self.assertTrue(claude.startswith("@AGENTS.md"))
        self.assertIn(self.info["claude_original"], claude)
        gitignore = self.info["gitignore_after_install"]
        self.assertIn(self.info["gitignore_original"], gitignore)
        self.assertIn("/reports/", gitignore)

    def test_05_detection_du_projet(self):
        detect = self.info["detect"]
        self.assertEqual(detect["result"].returncode, 0, detect["result"].stderr)
        payload = detect["payload"]
        self.assertEqual(payload["project"]["kind"], "existing")
        for item in self.EXPECTED_STACK:
            self.assertIn(item, payload["project"]["stack"])
        self.assertEqual(payload["ci"]["detected"], self.EXPECTED_CI)
        self.assertEqual(payload["commands"]["test"], self.EXPECTED_TEST_CMD)
        self.assertEqual(payload["env"]["SDLC_TEST_CMD"], self.EXPECTED_TEST_CMD)
        if self.EXPECTED_LINT_CMD:
            self.assertEqual(payload["commands"]["lint"], self.EXPECTED_LINT_CMD)
            self.assertEqual(payload["env"]["SDLC_LINT_CMD"], self.EXPECTED_LINT_CMD)
        if self.EXPECTED_COVERAGE:
            self.assertIn("SDLC_COVERAGE_CMD", payload["env"])

    def test_06_adaptateurs_des_outils_actives(self):
        render = self.info["render"]
        self.assertEqual(render.returncode, 0, render.stderr)
        self.assertIn(".claude/agents/implementer.md", self.info["adapters"])
        for rel, content in self.info["adapters"].items():
            self.assertNotIn("{{", content, rel)
        for rel in self.EXPECTED_ADAPTERS:
            self.assertIn(rel, self.info["adapters"])
        for rel in self.ABSENT_ADAPTERS:
            self.assertFalse(os.path.exists(self.path(*rel.split("/"))), rel)
        # Le CLAUDE.md maison n'est jamais écrasé : la directive @AGENTS.md est
        # en tête, le bloc `sdlc-claude` la suit, le contenu d'origine vient après.
        claude = self.info["claude_after_render"]
        self.assertTrue(claude.startswith(
            "@AGENTS.md\n\n<!-- sdlc-claude:begin v0.1.0 -->"), claude[:80])
        self.assertIn("<!-- sdlc-claude:end -->", claude)
        self.assertIn(self.info["claude_original"], claude)
        self.assertLess(claude.index("<!-- sdlc-claude:end -->"),
                        claude.index(self.info["claude_original"]))

    def test_06b_render_idempotent(self):
        render2 = self.info["render2"]
        self.assertEqual(render2.returncode, 0, render2.stderr)
        self.assertIn("0 fichier(s) écrit(s)", render2.stdout)
        self.assertEqual(self.info["snap_after_render"],
                         self.info["snap_after_render2"])

    def test_07_adr_dans_le_bon_dossier(self):
        adr = self.info["adr"]
        self.assertEqual(adr.returncode, 0, adr.stderr)
        self.assertTrue(os.path.isfile(self.info["adr_path"]))
        self.assertTrue(os.path.isfile(self.info["adr_index"]))
        content = read(self.info["adr_path"])
        self.assertIn("Cible de déploiement et CI", content)
        if self.FORBIDDEN_ADR_DIR:
            self.assertFalse(
                os.path.exists(self.path(*self.FORBIDDEN_ADR_DIR.split("/"))),
                "l'ADR a été écrit au mauvais endroit : %s" % self.FORBIDDEN_ADR_DIR)

    def test_08_ci_sh_et_summary(self):
        ci = self.info["ci"]
        self.assertEqual(ci["result"].returncode, 0, ci["result"].stderr)
        summary = ci["summary"]
        self.assertIsNotNone(summary, "reports/summary.json absent")
        controls = summary["controls"]
        for name in ("lint", "tests", "coverage", "sast", "deps", "secrets", "build"):
            self.assertEqual(controls[name], "pass", "%s = %s" % (name, controls[name]))
        self.assertEqual(summary["coverage_pct"], 95)
        self.assertFalse(summary["blocking"])

    def test_09_installation_idempotente(self):
        self.assertEqual(self.info["install2"].returncode, 0, self.info["install2"].stderr)
        self.assertNotIn("créer", self.info["install2"].stdout)
        self.assertNotIn("remplacer", self.info["install2"].stdout)
        self.assertEqual(self.info["snap_before_install2"], self.info["snap_after_install2"])

    def test_10_upgrade_conserve_le_fichier_modifie(self):
        self.assertEqual(self.info["upgrade"].returncode, 0, self.info["upgrade"].stderr)
        self.assertIn("conserver", self.info["upgrade"].stdout)
        self.assertEqual(self.info["fw_file_after_upgrade"], self.info["fw_file_outside"])
        # Les règles maison restent présentes après mise à jour.
        self.assertIn(self.info["agents_original"], self.info["agents_after_upgrade"])

    def test_11_uninstall_restaure_le_projet(self):
        self.assertEqual(self.info["uninstall"].returncode, 0, self.info["uninstall"].stderr)
        self.assertEqual(self.info["agents_after_uninstall"], self.info["agents_original"])
        self.assertEqual(self.info["claude_after_uninstall"], self.info["claude_original"])
        self.assertEqual(self.info["gitignore_after_uninstall"], self.info["gitignore_original"])
        self.assertFalse(self.info["sdlc_after_uninstall"], ".sdlc/ subsiste")
        self.assertFalse(self.info["agents_dir_after_uninstall"], ".agents/ subsiste")

        # Adaptateurs générés retirés, fichiers de l'humain restaurés.
        for name, present in self.info["adapters_after_uninstall"].items():
            self.assertFalse(present, "%s généré subsiste" % name)
        if self.info["settings_original"] is None:
            self.assertIsNone(self.info["settings_after_uninstall"],
                              ".claude/settings.json créé devrait être retiré")
        else:
            self.assertEqual(self.info["settings_after_uninstall"],
                             self.info["settings_original"])


# ---------------------------------------------------------------------------
# Projet 1 : Django
# ---------------------------------------------------------------------------
class ProjetDjango(ProjetExistantE2E, unittest.TestCase):
    PREFIX = "e2e-django-"
    EXPECTED_STACK = ("python", "django")
    EXPECTED_CI = "github-actions"
    EXPECTED_TEST_CMD = "python3 -m pytest"
    EXPECTED_LINT_CMD = None
    EXPECTED_COVERAGE = True  # requirements.txt déclare coverage
    EXPECTED_ADAPTERS = (".claude/agents/implementer.md", ".codex/config.toml")
    ABSENT_ADAPTERS = (".opencode",)
    PROTECTED = (
        "README.md", "requirements.txt", "manage.py",
        "templates/pages/index.html", "templates/pages/base.html",
        ".github/workflows/ci.yml", "docs/decisions/contexte.md",
        "tests/test_smoke.py",
    )
    FORBIDDEN_ADR_DIR = "docs/architecture"

    @classmethod
    def build_fixture(cls):
        write(cls.path("README.md"),
              "# DjangoShop\n\nBoutique en ligne (Django).\n")
        write(cls.path("AGENTS.md"),
              "# Règles maison — DjangoShop\n\n"
              "- Lancer les tests avec pytest avant chaque commit.\n"
              "- Ne jamais committer de secret.\n")
        write(cls.path("CLAUDE.md"),
              "# Notes Claude — DjangoShop\n\nCe projet suit nos conventions internes.\n")
        write(cls.path(".gitignore"), "db.sqlite3\n.venv/\n")
        # Fichier `.claude/settings.json` de l'humain : `render_adapters.py` le
        # fusionne sans écraser ses entrées, et `--uninstall` le restaure.
        write(cls.path(".claude", "settings.json"),
              json.dumps({"permissions": {"allow": ["Bash(ls:*)"]}},
                         ensure_ascii=False, indent=2) + "\n")
        write(cls.path("templates", "pages", "index.html"),
              "<!doctype html>\n<html lang=\"fr\"><body><h1>Accueil</h1></body></html>\n")
        write(cls.path("templates", "pages", "base.html"),
              "<!doctype html>\n<html lang=\"fr\"><body>{% block contenu %}{% endblock %}</body></html>\n")
        write(cls.path("requirements.txt"), "Django>=4.2\npytest>=7.0\ncoverage>=7.0\n")
        write(cls.path("manage.py"), "#!/usr/bin/env python\n\"\"\"manage.py minimal.\"\"\"\n")
        write(cls.path("tests", "test_smoke.py"),
              "def test_smoke():\n    assert True\n")
        write(cls.path(".github", "workflows", "ci.yml"),
              "name: ci\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
              "    steps:\n      - uses: actions/checkout@v4\n"
              "      - run: python3 -m pip install -r requirements.txt\n"
              "      - run: python3 -m pytest\n")
        write(cls.path("docs", "decisions", "contexte.md"),
              "# Contexte du projet\n\nOrganisation documentaire existante.\n")
        # Emplacement attendu de l'ADR : docs/decisions (paths.adr).
        cls.info["adr_path"] = cls.path("docs", "decisions", "ADR-001.md")
        cls.info["adr_index"] = cls.path("docs", "decisions", "README.md")

    @classmethod
    def write_config(cls):
        text = read(EXAMPLE_CONFIG)
        text = text.replace('name: "Atlas"', 'name: "DjangoShop"')
        text = text.replace("kind: new", "kind: existing")
        text = text.replace("stack: [rails, angular]", "stack: [python, django]")
        text = text.replace("tool: gitlab-ci", "tool: github-actions")
        text = text.replace("adr: docs/architecture/adr", "adr: docs/decisions")
        write(cls.path("sdlc.config.yaml"), text)


# ---------------------------------------------------------------------------
# Projet 2 : Node
# ---------------------------------------------------------------------------
class ProjetNode(ProjetExistantE2E, unittest.TestCase):
    PREFIX = "e2e-node-"
    EXPECTED_STACK = ("node",)
    EXPECTED_CI = "gitlab-ci"
    EXPECTED_TEST_CMD = "npm test"
    EXPECTED_LINT_CMD = "npm run lint"
    EXPECTED_COVERAGE = False
    EXPECTED_ADAPTERS = (".claude/agents/implementer.md", ".claude/settings.json")
    ABSENT_ADAPTERS = (".codex", ".opencode")
    PROTECTED = (
        "README.md", "package.json", ".gitlab-ci.yml",
        "openspec/changes/ajout-auth/tasks.md",
        "openspec/changes/ajout-auth/proposal.md",
        "src/index.js",
    )
    FORBIDDEN_ADR_DIR = None

    CHANGE_ID = "ajout-auth"

    @classmethod
    def build_fixture(cls):
        write(cls.path("README.md"), "# NodeApi\n\nAPI Node existante.\n")
        write(cls.path("AGENTS.md"),
              "# Règles maison — NodeApi\n\n"
              "- Exécuter `npm test` et `npm run lint` avant chaque commit.\n")
        write(cls.path("CLAUDE.md"),
              "# Notes Claude — NodeApi\n\nConventions internes de l'équipe.\n")
        write(cls.path(".gitignore"), "node_modules/\ndist/\n")
        write(cls.path("package.json"), json.dumps({
            "name": "node-api",
            "version": "1.0.0",
            "scripts": {"test": "node --test", "lint": "eslint ."},
        }, indent=2) + "\n")
        write(cls.path(".gitlab-ci.yml"),
              "stages: [test]\n\nlint:\n  stage: test\n  script:\n    - npm run lint\n\n"
              "test:\n  stage: test\n  script:\n    - npm test\n")
        write(cls.path("src", "index.js"), "module.exports = {};\n")
        write(cls.path("openspec", "changes", cls.CHANGE_ID, "proposal.md"),
              "# Proposition — Ajout de l'authentification\n\nAjouter un login.\n")
        write(cls.path("openspec", "changes", cls.CHANGE_ID, "tasks.md"),
              "# Tâches — Ajout de l'authentification\n\n"
              "## 1. Préparation\n"
              "- [ ] 1.1 Créer le modèle utilisateur (`user`)\n"
              "- [ ] 1.2 Ajouter la route `/login`\n\n"
              "## 2. Livraison\n"
              "- [ ] 2.1 Écrire les tests de bout en bout\n"
              "- [ ] 2.2 Documenter l'API\n")
        # Emplacement attendu de l'ADR : chemin par défaut (paths.adr non modifié).
        cls.info["adr_path"] = cls.path("docs", "architecture", "adr", "ADR-001.md")
        cls.info["adr_index"] = cls.path("docs", "architecture", "adr", "README.md")

    @classmethod
    def write_config(cls):
        text = read(EXAMPLE_CONFIG)
        text = text.replace('name: "Atlas"', 'name: "NodeApi"')
        text = text.replace("kind: new", "kind: existing")
        text = text.replace("stack: [rails, angular]", "stack: [node]")
        # Un seul agent activé : Claude (ni Codex ni OpenCode).
        text = text.replace("  codex:\n    enabled: true", "  codex:\n    enabled: false")
        text = text.replace("executors: [codex, claude]", "executors: [claude]")
        write(cls.path("sdlc.config.yaml"), text)

    @classmethod
    def extra_chain(cls):
        """Suivi tâche par tâche puis tableau de bord projet (Node)."""
        tasks_rel = "openspec/changes/%s/tasks.md" % cls.CHANGE_ID
        gen = cls.path(".agents", "skills", "suivi-taches", "scripts", "generate.py")
        track = cls.path(".agents", "skills", "suivi-taches", "scripts", "track.py")
        collect = cls.path(".agents", "skills", "suivi-projet", "scripts", "collect.py")
        dash = cls.path(".agents", "skills", "suivi-projet", "scripts", "generate.py")

        gen_result = run([sys.executable, gen, "--out", "docs/suivi-node.html",
                          "--tasks", tasks_rel, "--title", "Suivi — Ajout auth",
                          "--h1", "Ajout auth — fichier de suivi"], cwd=cls.proj)
        track_result = run([sys.executable, track, "--file", "docs/suivi-node.html",
                            "--executor", "claude", "--reviewer", "codex",
                            "--commit-message", "feat(auth): modele utilisateur",
                            "--ready-to-commit", "1.1", "done", "Fait ; relu."], cwd=cls.proj)
        collect_result = run([sys.executable, collect, cls.proj], cwd=cls.proj)
        dash_result = run([sys.executable, dash, cls.proj], cwd=cls.proj)

        state_path = cls.path("docs", "suivi", "state.json")
        state = json.loads(read(state_path)) if os.path.isfile(state_path) else None
        project_data_path = cls.path("docs", "suivi", "project-data.json")
        docs_data_path = cls.path("docs", "suivi", "docs-data.json")
        cls.info["suivi"] = {
            "generate": gen_result,
            "track": track_result,
            "collect": collect_result,
            "dashboard": dash_result,
            "state": state,
            "project_data": json.loads(read(project_data_path)) if os.path.isfile(project_data_path) else None,
            "docs_data": json.loads(read(docs_data_path)) if os.path.isfile(docs_data_path) else None,
            "html": read(cls.path("docs", "suivi-node.html")) if os.path.isfile(cls.path("docs", "suivi-node.html")) else None,
            "dashboard_html": read(cls.path("docs", "suivi-projet.html")) if os.path.isfile(cls.path("docs", "suivi-projet.html")) else None,
        }

    def test_12_suivi_taches_generer_et_tracker(self):
        suivi = self.info["suivi"]
        self.assertEqual(suivi["generate"].returncode, 0, suivi["generate"].stderr)
        self.assertEqual(suivi["track"].returncode, 0, suivi["track"].stderr)
        self.assertIn("1 feature(s), 4 tâche(s)", suivi["generate"].stdout)
        self.assertIn("généré par la skill suivi-taches, ne pas modifier", suivi["html"])
        state = suivi["state"]
        self.assertEqual(state["schema"], 1)
        self.assertEqual([f["id"] for f in state["features"]], [self.CHANGE_ID])
        task = [t for t in state["features"][0]["tasks"] if t["id"] == "1.1"][0]
        self.assertEqual(task["status"], "done")
        self.assertTrue(task["ready_to_commit"])
        self.assertEqual(task["commit_message"], "feat(auth): modele utilisateur")

    def test_13_suivi_projet_collecte_et_genere(self):
        suivi = self.info["suivi"]
        self.assertEqual(suivi["collect"].returncode, 0, suivi["collect"].stderr)
        self.assertEqual(suivi["dashboard"].returncode, 0, suivi["dashboard"].stderr)
        self.assertIsInstance(suivi["project_data"], dict)
        self.assertIsInstance(suivi["docs_data"], dict)
        ids = [f["id"] for f in suivi["project_data"]["features"]]
        self.assertIn(self.CHANGE_ID, ids)
        self.assertNotIn("__PROJECT_DATA__", suivi["dashboard_html"])
        self.assertNotIn("__DOCS_DATA__", suivi["dashboard_html"])
        self.assertIn("généré par la skill suivi-projet, ne pas modifier",
                      suivi["dashboard_html"])
        self.assertTrue(os.path.isfile(self.path("docs", "metrics", "history.jsonl")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
