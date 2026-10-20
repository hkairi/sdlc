#!/usr/bin/env python3
"""Tests de la skill suivi-projet (collecte, formats, génération).

Lancement :
    python3 -m unittest discover -s .agents/skills/suivi-projet/tests
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import collect  # noqa: E402
import generate  # noqa: E402

FIXTURES = TESTS / "fixtures"
DEMO = FIXTURES / "projet-demo"
COV = FIXTURES / "coverage"

TEMPLATE = TESTS.parent / "assets" / "template.html"


class Base(unittest.TestCase):
    def copy_demo(self):
        tmp = tempfile.mkdtemp(prefix="suivi-projet-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        dest = os.path.join(tmp, "projet-demo")
        shutil.copytree(str(DEMO), dest)
        return dest


class CoverageFormats(Base):
    def test_cobertura(self):
        cov, mods = collect._cobertura(str(COV / "cobertura.xml"))
        self.assertEqual(cov, 80.0)
        self.assertTrue(mods)

    def test_jacoco(self):
        cov, mods = collect._jacoco(str(COV / "jacoco.xml"))
        self.assertEqual(cov, 85.0)
        self.assertEqual(mods[0]["coverage"], 90.0)

    def test_lcov(self):
        cov, _ = collect._lcov(str(COV / "lcov.info"))
        self.assertEqual(cov, 70.0)

    def test_coveragepy_json(self):
        cov, mods = collect._coveragepy_json(str(COV / "coverage.json"))
        self.assertEqual(cov, 91.3)
        self.assertEqual(len(mods), 1)          # regroupé par répertoire de premier niveau
        self.assertEqual(mods[0]["name"], "pkg")

    def test_collect_coverage_detects_demo(self):
        cov, mods = collect.collect_coverage(str(DEMO))
        self.assertEqual(cov, 85.0)
        names = {m["name"]: m["coverage"] for m in mods}
        self.assertEqual(names["api"], 92.0)
        self.assertEqual(names["web"], 74.0)


class SarifMapping(Base):
    def test_severity_counts(self):
        sarif = collect.collect_sarif(str(DEMO))
        self.assertIsNotNone(sarif)
        self.assertEqual(sarif["counts"]["critique"], 1)
        self.assertEqual(sarif["counts"]["haute"], 1)
        self.assertEqual(sarif["counts"]["moyenne"], 1)
        self.assertEqual(sarif["counts"]["basse"], 0)

    def test_security_severity_then_level(self):
        sarif = collect.collect_sarif(str(DEMO))
        by_id = {f["id"]: f["sev"] for f in sarif["findings"]}
        self.assertEqual(by_id["py.sql-injection"], "critique")   # security-severity 9.5
        self.assertEqual(by_id["CVE-2026-0001"], "haute")         # security-severity 7.2
        self.assertEqual(by_id["CVE-2026-0002"], "moyenne")       # level warning

    def test_by_source(self):
        sarif = collect.collect_sarif(str(DEMO))
        sources = {s["source"] for s in sarif["bySource"]}
        self.assertIn("Semgrep", sources)
        self.assertIn("Trivy", sources)


class TaskCounting(Base):
    def test_counts(self):
        self.assertEqual(collect.count_tasks(str(DEMO / "openspec/changes/auth-sso/tasks.md")), [3, 5])
        self.assertEqual(collect.count_tasks(str(DEMO / "openspec/changes/notifications/tasks.md")), [2, 4])
        self.assertEqual(collect.count_tasks(str(DEMO / "openspec/changes/archive/catalogue/tasks.md")), [2, 2])

    def test_missing_file(self):
        self.assertIsNone(collect.count_tasks(str(DEMO / "inexistant.md")))


class BuildDemo(Base):
    def test_project_data(self):
        root = self.copy_demo()
        pd, dd, snap = collect.build(root)
        self.assertEqual(pd["project"], "Démo")
        by_id = {f["id"]: f for f in pd["features"]}
        self.assertEqual(by_id["auth-sso"]["tasks"], [3, 5])
        self.assertEqual(by_id["notifications"]["tasks"], [2, 4])
        self.assertEqual(by_id["catalogue"]["tasks"], [2, 2])   # archivé → tout terminé
        self.assertEqual(pd["config"]["coverage_min"], 80)
        self.assertEqual(pd["config"]["block_on"], ["critique", "haute"])
        self.assertEqual(pd["quality"]["tests"]["total"], 12)
        self.assertEqual(pd["quality"]["tests"]["failed"], 1)
        self.assertEqual(pd["quality"]["tests"]["skipped"], 1)
        self.assertEqual(pd["incidents"][0]["id"], "INC-001")
        self.assertEqual(pd["incidents"][0]["status"], "ouvert")
        self.assertEqual(len(pd["deploys"]), 3)
        self.assertIn("auth-sso", [c["feature"] for c in pd["costs"]])

    def test_summary_json_takes_precedence(self):
        root = self.copy_demo()
        summary = {
            "ts": "2026-10-11T11:40:00+02:00",
            "controls": {"lint": "pass", "tests": "pass"},
            "coverage_pct": 77,
            "vulns": {"critique": 0, "haute": 2, "moyenne": 1, "basse": 0},
            "blocking": 2,
        }
        reports = os.path.join(root, "reports")
        os.makedirs(reports, exist_ok=True)
        with open(os.path.join(reports, "summary.json"), "w", encoding="utf-8") as fh:
            json.dump(summary, fh)
        pd, _, snap = collect.build(root)
        self.assertEqual(snap["coverage_pct"], 77)
        self.assertEqual(pd["ci"]["status"], "verte")
        self.assertEqual(snap["vulns"]["haute"], 2)


class MissingDataNoInvention(Base):
    def test_empty_project(self):
        tmp = tempfile.mkdtemp(prefix="suivi-vide-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        pd, dd, snap = collect.build(tmp)
        self.assertEqual(pd["features"], [])
        self.assertEqual(pd["modules"], [])
        self.assertEqual(pd["deploys"], [])
        self.assertEqual(pd["incidents"], [])
        self.assertEqual(pd["agents"], [])
        self.assertIsNone(pd["quality"]["tests"])
        self.assertIsNone(pd["security"])
        self.assertIsNone(pd["config"]["coverage_min"])
        self.assertIsNone(pd["ci"])
        # Aucune valeur par défaut inventée : la couverture manquante reste nulle.
        self.assertIn(snap["coverage_pct"], (None,))
        self.assertEqual(pd["history"]["coverage"], [])
        self.assertEqual(dd["files"], {})


class EmbedLimit(Base):
    def test_limit_reached(self):
        tmp = tempfile.mkdtemp(prefix="suivi-embed-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        base = os.path.join(tmp, "docs")
        os.makedirs(base)
        with open(os.path.join(base, "a.md"), "w", encoding="utf-8") as fh:
            fh.write("# Long\n" + "x" * 5000)
        with open(os.path.join(base, "b.md"), "w", encoding="utf-8") as fh:
            fh.write("# Court\n")
        md = collect.scan_md(tmp)
        docs, dd = collect.build_docs(tmp, "docs/suivi-projet.html", md, 0, True)
        self.assertEqual(set(dd["files"]), set())          # 0 Kio : rien n'est embarqué
        self.assertTrue(dd["warnings"])
        self.assertEqual(len(docs["categories"]), 1)        # les deux fichiers restent listés

    def test_most_recent_first(self):
        tmp = tempfile.mkdtemp(prefix="suivi-embed2-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        base = os.path.join(tmp, "docs")
        os.makedirs(base)
        old = os.path.join(base, "old.md")
        new = os.path.join(base, "new.md")
        open(old, "w", encoding="utf-8").write("# Ancien\n" + "x" * 5000)
        open(new, "w", encoding="utf-8").write("# Récent\n")
        os.utime(old, (1000, 1000))
        os.utime(new, (2000, 2000))
        md = collect.scan_md(tmp)
        docs, dd = collect.build_docs(tmp, "docs/suivi-projet.html", md, 1, True)
        self.assertEqual(list(dd["files"]), ["docs/new.md"])

    def test_embed_disabled(self):
        tmp = tempfile.mkdtemp(prefix="suivi-embed3-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, "docs"))
        open(os.path.join(tmp, "docs", "a.md"), "w", encoding="utf-8").write("# A\n")
        md = collect.scan_md(tmp)
        _, dd = collect.build_docs(tmp, "docs/suivi-projet.html", md, 512, False)
        self.assertEqual(dd["files"], {})
        self.assertTrue(dd["warnings"])


class Generation(Base):
    def test_markers_replaced_and_json_valid(self):
        root = self.copy_demo()
        collect.main([root])
        generate.main([root])
        out = os.path.join(root, "docs", "suivi-projet.html")
        self.assertTrue(os.path.isfile(out))
        html = open(out, encoding="utf-8").read()
        self.assertNotIn("__PROJECT_DATA__", html)
        self.assertNotIn("__DOCS_DATA__", html)
        self.assertIn("ne pas modifier", html)
        m = re.search(r'<script type="application/json" id="project-data">(.*?)</script>', html, re.S)
        self.assertIsNotNone(m)
        data = json.loads(m.group(1))
        self.assertEqual(data["project"], "Démo")
        self.assertEqual(len(data["features"]), 3)
        d = re.search(r'<script type="application/json" id="docs-data">(.*?)</script>', html, re.S)
        docs = json.loads(d.group(1))
        self.assertIn("docs/00-cadrage/brief.md", docs["files"])

    def test_embed_escapes_closing_tag(self):
        serialized = generate.embed({"x": "</script>", "y": "</b>"})
        self.assertNotIn("</", serialized)
        self.assertIn("<\\/", serialized)
        self.assertEqual(json.loads(serialized)["x"], "</script>")

    def test_out_override(self):
        root = self.copy_demo()
        collect.main([root])
        generate.main([root, "--out", "docs/custom.html"])
        self.assertTrue(os.path.isfile(os.path.join(root, "docs", "custom.html")))


class History(Base):
    def test_no_duplicate_same_day(self):
        root = self.copy_demo()
        collect.main([root])
        collect.main([root])
        hist = os.path.join(root, "docs", "metrics", "history.jsonl")
        lines = [line for line in open(hist, encoding="utf-8") if line.strip()]
        self.assertEqual(len(lines), 1)
        snap = json.loads(lines[0])
        self.assertEqual(snap["coverage_pct"], 85.0)


class YamlParser(Base):
    def test_inline_forms(self):
        text = "a: {x: 1, y: [b, c]}\nlist: [1, 2]\nblock:\n  k: v\narr:\n  - z\n  - {p: q}\n"
        parsed = collect.parse_yaml(text)
        self.assertEqual(parsed["a"]["x"], 1)
        self.assertEqual(parsed["a"]["y"], ["b", "c"])
        self.assertEqual(parsed["list"], [1, 2])
        self.assertEqual(parsed["block"]["k"], "v")
        self.assertEqual(parsed["arr"][0], "z")
        self.assertEqual(parsed["arr"][1]["p"], "q")

    def test_example_config(self):
        example = TESTS.parents[3] / "sdlc.config.example.yaml"
        if not example.is_file():
            self.skipTest("sdlc.config.example.yaml absent")
        cfg = collect.parse_yaml(example.read_text(encoding="utf-8"))
        self.assertEqual(cfg["project"]["name"], "Atlas")
        self.assertEqual(cfg["project"]["stack"], ["rails", "angular"])
        self.assertEqual(cfg["ci"]["block_on"], ["critique", "haute"])
        self.assertEqual(cfg["ci"]["coverage_min"], 80)
        self.assertEqual(cfg["deploy"]["targets"][0]["component"], "api")
        self.assertEqual(cfg["deploy"]["targets"][0]["profile"], "vps-compose")
        self.assertFalse(cfg["agents"]["opencode"]["enabled"])


class CurrentValues(Base):
    def test_first_collect_exposes_current_and_history(self):
        # Premier lancement sur un historique vide : la valeur courante est
        # disponible (Cobertura) et la série d'historique compte un point.
        root = self.copy_demo()
        hist = os.path.join(root, "docs", "metrics", "history.jsonl")
        self.assertFalse(os.path.isfile(hist))
        pd, _, snap = collect.build(root)
        self.assertEqual(pd["current"]["coverage_pct"], 85.0)
        self.assertEqual(pd["current"]["vulns"]["critique"], 1)
        self.assertEqual(pd["current"]["tests"], 12)
        self.assertEqual(pd["history"]["coverage"], [85.0])
        self.assertEqual(len(pd["history"]["vulns"]), 1)

    def test_second_collect_same_day_no_duplicate(self):
        root = self.copy_demo()
        collect.main([root])
        pd, _, _ = collect.build(root)
        self.assertEqual(len(pd["history"]["coverage"]), 1)
        self.assertEqual(pd["current"]["coverage_pct"], 85.0)
        hist = os.path.join(root, "docs", "metrics", "history.jsonl")
        lines = [line for line in open(hist, encoding="utf-8") if line.strip()]
        self.assertEqual(len(lines), 1)

    def test_empty_project_no_snapshot_invented(self):
        tmp = tempfile.mkdtemp(prefix="suivi-current-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        pd, _, snap = collect.build(tmp)
        self.assertIsNone(snap["coverage_pct"])
        self.assertEqual(pd["current"], {"coverage_pct": None, "vulns": None, "tests": None})
        self.assertEqual(pd["history"]["coverage"], [])


class DiagramDiscovery(Base):
    def test_discovers_architecture_schema(self):
        root = self.copy_demo()
        md = collect.scan_md(root)
        docs, _ = collect.build_docs(root, "docs/suivi-projet.html", md, 512, True)
        diags = docs["diagrams"]
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["title"], "architecture-demo")
        self.assertEqual(diags[0]["sub"], "docs/architecture/architecture-demo.html")
        self.assertTrue(diags[0]["img"].endswith("architecture-demo.png"))

    def test_ignores_html_outside_architecture(self):
        root = self.copy_demo()
        # Le tableau de bord généré vit dans docs/ et ne doit pas être pris pour un schéma.
        open(os.path.join(root, "docs", "suivi-projet.html"), "w", encoding="utf-8").write("<!doctype html>")
        md = collect.scan_md(root)
        docs, _ = collect.build_docs(root, "docs/suivi-projet.html", md, 512, True)
        subs = [d["sub"] for d in docs["diagrams"]]
        self.assertEqual(subs, ["docs/architecture/architecture-demo.html"])

    def test_no_architecture_directory(self):
        tmp = tempfile.mkdtemp(prefix="suivi-nodoc-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        docs, _ = collect.build_docs(tmp, "docs/suivi-projet.html", {}, 512, True)
        self.assertEqual(docs["diagrams"], [])


class Template(Base):
    def test_template_has_markers(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("__PROJECT_DATA__", html)
        self.assertIn("__DOCS_DATA__", html)
        self.assertIn("par la skill suivi-projet, ne pas modifier", html)


class StatePhaseForms(Base):
    """Le format commun stocke les phases comme objets ; la forme historique (6 chaînes)
    reste acceptée. `collect.py` tolère les deux."""

    def test_objects(self):
        raw = [{"id": i, "status": s} for i, s in zip(
            ["cadrage", "plan", "impl", "validation", "deploy", "cloture"],
            ["done", "done", "doing", "todo", "todo", "todo"])]
        self.assertEqual(collect.normalize_phases(raw),
                         ["done", "done", "doing", "todo", "todo", "todo"])

    def test_strings(self):
        self.assertEqual(collect.normalize_phases(["done"] * 6), ["done"] * 6)

    def test_invalid(self):
        self.assertEqual(collect.normalize_phases("pas une liste"), ["todo"] * 6)
        self.assertEqual(collect.normalize_phases([{"id": "cadrage"}]), ["todo"] * 6)

    def test_build_features_from_object_phases(self):
        root = self.copy_demo()
        path = os.path.join(root, "docs", "suivi", "state.json")
        state = json.load(open(path, encoding="utf-8"))
        state["features"][0]["phases"] = [
            {"id": i, "status": s} for i, s in zip(
                ["cadrage", "plan", "impl", "validation", "deploy", "cloture"],
                ["done", "done", "doing", "todo", "todo", "todo"])]
        json.dump(state, open(path, "w", encoding="utf-8"))
        pd, _, _ = collect.build(root)
        by_id = {f["id"]: f for f in pd["features"]}
        self.assertEqual(by_id["auth-sso"]["phases"],
                         ["done", "done", "doing", "todo", "todo", "todo"])


if __name__ == "__main__":
    unittest.main()
