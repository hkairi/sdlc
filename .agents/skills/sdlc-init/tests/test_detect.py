#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `scripts/detect.sh` (skill `sdlc-init`).

Lancement :
    python3 -m unittest discover -s .agents/skills/sdlc-init/tests

Les mini-projets de test sont créés sous `tests/tmp/` (dans le dépôt) puis
supprimés à la fin de chaque test.
"""
import json
import os
import shutil
import subprocess
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
DETECT = os.path.join(os.path.dirname(TESTS), "scripts", "detect.sh")
TMP = os.path.join(TESTS, "tmp")


def run_detect(root):
    """Lance detect.sh sur `root` et renvoie (objet JSON, stderr)."""
    result = subprocess.run(
        ["bash", DETECT, root], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise AssertionError(
            "detect.sh a échoué (code %d) : %s" % (result.returncode, result.stderr)
        )
    # stdout doit être un JSON pur (rien d'autre).
    return json.loads(result.stdout), result.stderr


class Base(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(TMP, ignore_errors=True)
        os.makedirs(TMP, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(TMP, ignore_errors=True)

    def project(self, name):
        path = os.path.join(TMP, name)
        os.makedirs(path, exist_ok=True)
        return path

    def write(self, path, content):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)


class NodeProject(Base):
    def test_detects_npm_scripts(self):
        root = self.project("node")
        self.write(os.path.join(root, "package.json"), json.dumps({
            "name": "mini-node",
            "scripts": {
                "test": "jest",
                "lint": "eslint .",
                "coverage": "jest --coverage",
            },
        }))
        payload, _ = run_detect(root)
        self.assertEqual(payload["project"]["kind"], "existing")
        self.assertIn("node", payload["project"]["stack"])
        self.assertEqual(payload["commands"]["test"], "npm test")
        self.assertEqual(payload["commands"]["lint"], "npm run lint")
        self.assertEqual(payload["commands"]["coverage"], "npm run coverage")
        self.assertEqual(payload["env"]["SDLC_TEST_CMD"], "npm test")
        self.assertEqual(payload["env"]["SDLC_LINT_CMD"], "npm run lint")
        self.assertEqual(payload["env"]["SDLC_COVERAGE_CMD"], "npm run coverage")


class PythonProject(Base):
    def test_detects_pytest_and_coverage(self):
        root = self.project("python")
        self.write(os.path.join(root, "pyproject.toml"),
                   "[tool.pytest.ini_options]\naddopts = \"-q\"\n"
                   "[tool.coverage.run]\nbranch = true\n")
        os.makedirs(os.path.join(root, "tests"), exist_ok=True)
        self.write(os.path.join(root, "tests", "test_smoke.py"),
                   "def test_ok():\n    assert True\n")
        self.write(os.path.join(root, ".coveragerc"), "[run]\nbranch = True\n")
        payload, _ = run_detect(root)
        self.assertEqual(payload["project"]["kind"], "existing")
        self.assertIn("python", payload["project"]["stack"])
        self.assertEqual(payload["commands"]["test"], "python3 -m pytest")
        self.assertTrue(payload["commands"]["coverage"].startswith("python3 -m coverage"))
        self.assertEqual(payload["env"]["SDLC_TEST_CMD"], "python3 -m pytest")
        self.assertIn("SDLC_COVERAGE_CMD", payload["env"])


class EmptyProject(Base):
    def test_new_project_has_no_commands(self):
        root = self.project("vide")
        payload, _ = run_detect(root)
        self.assertEqual(payload["project"]["kind"], "new")
        self.assertEqual(payload["commands"], {"test": None, "lint": None, "coverage": None})
        self.assertEqual(payload["env"], {})


if __name__ == "__main__":
    unittest.main()
