#!/usr/bin/env python3
"""Tests de la skill suivi-taches (état partagé, scripts, rôles, migration, rendu).

Lancement :
    python3 -m unittest discover -s .agents/skills/suivi-taches/tests
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(TESTS), "scripts")
FIXTURES = os.path.join(TESTS, "fixtures")
REPO = os.path.abspath(os.path.join(TESTS, "..", "..", "..", ".."))
# Fixture autonome : un suivi mono réaliste de quelques lots et son tasks.md.
# (Auparavant ce test dépendait de docs/conception/legacy-suivi-taches/, supprimé.)
EXEMPLE_MONO = os.path.join(FIXTURES, "exemple-suivi-mono.html")
EXEMPLE_TASKS = os.path.join(FIXTURES, "exemple-tasks.md")
sys.path.insert(0, SCRIPTS)

import generate        # noqa: E402
import migrate_from_html  # noqa: E402
import phases          # noqa: E402
import render          # noqa: E402
import state_io as sio  # noqa: E402
import tracking        # noqa: E402

TASKS = open(os.path.join(FIXTURES, "tasks-simple.md"), encoding="utf-8").read()

# Suivi mono synthétique : métadonnées (title, h1, eyebrow, sous-titre, sources) et cartes
# d'information (objectif, décisions, sources), plus deux tâches avec note.
LEGACY_MONO_META = """<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><title>Suivi d'avancement — Démo · Projet</title></head>
<body data-file-updated="2026-10-01">
<header class="top">
  <div class="wrap">
    <div class="eyebrow">Projet · Domaine · Suivi d'avancement</div>
    <h1>Démo — fichier de suivi</h1>
    <p>Spec <code>docs/spec.md</code> · 2 tâches · 1 lot</p>
    <p class="extra" style="margin-top:6px;font-size:13px">Dernière mise à jour : <span id="fileUpdated">2026-10-01</span></p>
    <p class="extra" style="margin-top:6px;font-size:13px">Sources : <a href="docs/spec.md">spec</a> · <a href="docs/tasks.md">tasks</a></p>
    <div class="global"><span class="pct">0%</span><div class="track"><span></span></div><span id="globalCount">0 / 2 terminées</span></div>
  </div>
</header>
<div class="wrap">
  <section class="banner card " data-card="objectif" data-label="Objectif du chantier">
    <div class="card-head"><button class="card-toggle"><span class="chev">▾</span><b>Objectif du chantier</b></button><button class="card-close">×</button></div>
    <div class="card-body">Faire <code>X</code> et <b>Y</b>.</div>
  </section>
  <section class="banner card decisions" data-card="decisions" data-label="Décisions">
    <div class="card-head"><button class="card-toggle"><span class="chev">▾</span><b>Décisions</b></button><button class="card-close">×</button></div>
    <div class="card-body"><ul><li>Décision <code>A</code>.</li><li>Décision B.</li></ul></div>
  </section>
  <section class="banner card sources" data-card="sources" data-label="Sources">
    <div class="card-head"><button class="card-toggle"><span class="chev">▾</span><b>Sources</b></button><button class="card-close">×</button></div>
    <div class="card-body"><ul><li><a href="docs/design.md">Design</a></li></ul></div>
  </section>
  <div id="lots">
  <section class="lot" data-lot="L1" data-name="1 · Lot" data-color="#5c6b7a">
    <div class="head"><span class="dot"></span><h2>1 · Lot</h2><span class="mini">0/2</span></div>
    <div class="lbar"><span></span></div>
    <div class="tasks">
      <div class="task" data-id="1.1" data-lot="L1" data-prio="" data-status="done" data-updated="2026-10-01">
        <div class="side"><span class="id">1.1</span></div>
        <div class="main"><h3>Première tâche tronquée…</h3><em class="note">Note 1.</em><div class="obj">Tronqué</div><span class="draft-flag hidden">x</span></div>
      </div>
      <div class="task" data-id="1.2" data-lot="L1" data-prio="" data-status="doing" data-updated="2026-10-01">
        <div class="side"><span class="id">1.2</span></div>
        <div class="main"><h3>Deuxième tâche</h3><em class="note">Note 2.</em><div class="obj">Tronqué</div><span class="draft-flag hidden">x</span></div>
      </div>
    </div>
  </section>
  </div>
</div>
<script type="application/json" id="phase-data">{"phases":[{"id":"cadrage","name":"Cadrage","items":[{"id":"proposal","label":"Proposition","status":"done"}]}]}</script>
</body>
</html>
"""

# tasks.md correspondant au suivi synthétique (texte complet + titre court).
LEGACY_MONO_TASKS = """# Tâches démo

## 1. Lot
- [ ] 1.1 Texte complet de la première tâche (`code`)
- [x] 1.2 Deuxième tâche complète
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="suivi-taches-")
        self._cwd = os.getcwd()
        os.chdir(self.root)
        os.makedirs(os.path.join(self.root, "openspec", "changes", "auth-sso"))
        with open(os.path.join(self.root, "openspec", "changes", "auth-sso", "tasks.md"),
                  "w", encoding="utf-8") as fh:
            fh.write(TASKS)
        shutil.copy(os.path.join(FIXTURES, "sdlc.config.yaml"), os.path.join(self.root, "sdlc.config.yaml"))

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.root, ignore_errors=True)

    def tasks_path(self):
        return os.path.join("openspec", "changes", "auth-sso", "tasks.md")

    def generate(self, out="docs/suivi-auth-sso.html"):
        args = ["--out", out, "--tasks", self.tasks_path(),
                "--title", "Suivi — Auth", "--h1", "Auth — fichier de suivi"]
        generate.main(args)
        return os.path.join(self.root, "docs", "suivi", "state.json")

    def load_state(self):
        return sio.load_state(os.path.join(self.root, "docs", "suivi", "state.json"))

    def write_state(self, state):
        sio.save_state(os.path.join(self.root, "docs", "suivi", "state.json"), state)


class Generation(Base):
    def test_generate_builds_state_and_html(self):
        self.generate()
        state = self.load_state()
        self.assertEqual(state["schema"], 1)
        self.assertEqual(len(state["features"]), 1)
        feature = state["features"][0]
        self.assertEqual(feature["id"], "auth-sso")
        self.assertEqual(len(feature["tasks"]), 3)
        self.assertEqual(len(feature["lots"]), 2)
        self.assertEqual([p["id"] for p in feature["phases"]],
                         ["cadrage", "plan", "impl", "validation", "deploy", "cloture"])
        # La phase impl est dérivée des tâches : 1 terminée → doing.
        self.assertEqual(next(p for p in feature["phases"] if p["id"] == "impl")["status"], "doing")
        html = open(os.path.join(self.root, "docs", "suivi-auth-sso.html"), encoding="utf-8").read()
        self.assertIn("généré par la skill suivi-taches, ne pas modifier", html)
        self.assertIn('id="state-data"', html)

    def test_checkbox_forces_done(self):
        self.generate()
        state = self.load_state()
        state["features"][0]["tasks"][1]["status"] = "todo"  # 1.2 coché dans tasks.md
        self.write_state(state)
        # régénérer ne doit pas perdre la case cochée
        self.generate()
        state = self.load_state()
        done = [t for t in state["features"][0]["tasks"] if t["id"] == "1.2"][0]
        self.assertEqual(done["status"], "done")

    def test_merge_without_loss(self):
        self.generate()
        state = self.load_state()
        task = state["features"][0]["tasks"][0]
        task["status"] = "done"
        task["note"] = "Fait ; 12 tests, 0 échec."
        task["executor"] = "codex"
        task["reviewer"] = "claude"
        task["history"] = [{"date": "2026-10-09", "status": "doing", "note": "Délégué."}]
        task["files"] = ["app/models/session.rb"]
        task["ready_to_commit"] = True
        task["commit_message"] = "feat(auth): session"
        self.write_state(state)
        self.generate()
        merged = self.load_state()["features"][0]["tasks"][0]
        # 1.1 n'est pas coché : l'état conservé (done, note, rôles…) est préservé.
        self.assertEqual(merged["status"], "done")
        self.assertEqual(merged["note"], "Fait ; 12 tests, 0 échec.")
        self.assertEqual(merged["executor"], "codex")
        self.assertEqual(merged["reviewer"], "claude")
        self.assertEqual(merged["history"], [{"date": "2026-10-09", "status": "doing", "note": "Délégué."}])
        self.assertEqual(merged["files"], ["app/models/session.rb"])
        self.assertTrue(merged["ready_to_commit"])
        self.assertEqual(merged["commit_message"], "feat(auth): session")

    def test_merge_keeps_other_features(self):
        self.generate()
        state = self.load_state()
        state["features"].append({"id": "autre", "name": "Autre", "tasks": [], "lots": []})
        self.write_state(state)
        self.generate()
        ids = [f["id"] for f in self.load_state()["features"]]
        self.assertIn("autre", ids)
        self.assertIn("auth-sso", ids)


class AtomicWrite(Base):
    def test_no_temp_left_and_content_valid(self):
        path = os.path.join(self.root, "docs", "suivi", "state.json")
        sio.save_state(path, {"schema": 1, "features": [{"id": "x"}]})
        state = json.load(open(path, encoding="utf-8"))
        self.assertEqual(state["features"][0]["id"], "x")
        leftovers = [f for f in os.listdir(os.path.dirname(path)) if f.startswith(".state-")]
        self.assertEqual(leftovers, [])

    def test_failed_write_keeps_original(self):
        path = os.path.join(self.root, "docs", "suivi", "state.json")
        sio.save_state(path, {"schema": 1, "features": [{"id": "original"}]})
        original = open(path, encoding="utf-8").read()
        real_dump = json.dump

        def boom(*a, **k):
            raise RuntimeError("boom")

        json.dump = boom
        try:
            with self.assertRaises(RuntimeError):
                sio.save_state(path, {"schema": 1, "features": [{"id": "nouveau"}]})
        finally:
            json.dump = real_dump
        self.assertEqual(open(path, encoding="utf-8").read(), original)
        leftovers = [f for f in os.listdir(os.path.dirname(path)) if f.startswith(".state-")]
        self.assertEqual(leftovers, [])


class Roles(Base):
    def test_refuse_reviewer_equals_executor(self):
        task = {"executor": "codex"}
        with self.assertRaises(SystemExit):
            tracking.apply_roles(task, reviewer="codex")

    def test_reviewer_different_ok(self):
        task = {}
        tracking.apply_roles(task, executor="codex", reviewer="claude", iteration=1,
                             commit_message="feat: x", ready_to_commit=True)
        self.assertEqual(task["executor"], "codex")
        self.assertEqual(task["reviewer"], "claude")
        self.assertEqual(task["review_iteration"], 1)
        self.assertEqual(task["commit_message"], "feat: x")
        self.assertTrue(task["ready_to_commit"])

    def test_escalation_beyond_max(self):
        task = {"review_iteration": 3}
        config = os.path.join(self.root, "sdlc.config.yaml")  # max_review_iterations: 2
        self.assertTrue(tracking.apply_escalation(task, config))
        self.assertEqual(task["status"], "blocked")
        self.assertTrue(task["escalated"])
        self.assertIn("Escalade", task["note"])

    def test_no_escalation_within_max(self):
        task = {"review_iteration": 2}
        self.assertFalse(tracking.apply_escalation(task, os.path.join(self.root, "sdlc.config.yaml")))
        self.assertNotIn("status", task)


class TrackCli(Base):
    def _run_track(self, argv):
        old = sys.argv
        sys.argv = ["track.py"] + argv
        try:
            tracking.task_update_main("test")
        finally:
            sys.argv = old

    def test_track_doing_then_done_with_roles(self):
        self.generate()
        self._run_track(["--file", "docs/suivi-auth-sso.html", "--executor", "codex",
                         "--reviewer", "claude", "--iteration", "1", "1.1", "doing", "Délégué."])
        state = self.load_state()
        task = [t for t in state["features"][0]["tasks"] if t["id"] == "1.1"][0]
        self.assertEqual(task["status"], "doing")
        self.assertEqual(task["executor"], "codex")
        self.assertEqual(task["reviewer"], "claude")
        self.assertEqual(task["review_iteration"], 1)
        self.assertTrue(task["history"])

        self._run_track(["--file", "docs/suivi-auth-sso.html", "--commit-message",
                         "feat(auth): session", "--ready-to-commit", "1.1", "done", "Fait."])
        state = self.load_state()
        task = [t for t in state["features"][0]["tasks"] if t["id"] == "1.1"][0]
        self.assertEqual(task["status"], "done")
        self.assertTrue(task["ready_to_commit"])
        self.assertEqual(task["commit_message"], "feat(auth): session")
        # case cochée dans tasks.md
        md = open(self.tasks_path(), encoding="utf-8").read()
        self.assertRegex(md, r"- \[x\] 1\.1 ")

    def test_track_escalates_over_max(self):
        self.generate()
        self._run_track(["--file", "docs/suivi-auth-sso.html", "--iteration", "5",
                         "2.1", "doing", "Revue en cours."])
        task = [t for t in self.load_state()["features"][0]["tasks"] if t["id"] == "2.1"][0]
        self.assertEqual(task["status"], "blocked")
        self.assertTrue(task["escalated"])

    def test_phase_update(self):
        self.generate()
        old = sys.argv
        sys.argv = ["track_phase.py", "--file", "docs/suivi-auth-sso.html",
                    "validation.tests", "done", "36 runs, 0 échec."]
        try:
            tracking.phase_update_main("test")
        finally:
            sys.argv = old
        feature = self.load_state()["features"][0]
        phase = [p for p in feature["phases"] if p["id"] == "validation"][0]
        item = [i for i in phase["items"] if i["id"] == "tests"][0]
        self.assertEqual(item["status"], "done")
        self.assertEqual(phase["status"], "doing")


class Migration(Base):
    def test_migrate_mono(self):
        out = os.path.join(self.root, "docs", "suivi", "state.json")
        migrate_from_html.main(["--file", os.path.join(FIXTURES, "suivi-mono.html"),
                                "--state", out, "--id", "auth-sso"])
        state = json.load(open(out, encoding="utf-8"))
        self.assertEqual(len(state["features"]), 1)
        feature = state["features"][0]
        self.assertEqual(feature["id"], "auth-sso")
        self.assertEqual(len(feature["tasks"]), 3)
        by_id = {t["id"]: t for t in feature["tasks"]}
        self.assertEqual(by_id["1.1"]["status"], "doing")
        self.assertEqual(by_id["1.1"]["note"], "Délégué à codex.")
        self.assertEqual(by_id["2.1"]["status"], "blocked")
        self.assertEqual(len(feature["lots"]), 2)
        self.assertTrue(feature["phases"])

    def test_migrate_multi(self):
        out = os.path.join(self.root, "docs", "suivi", "state.json")
        migrate_from_html.main(["--file", os.path.join(FIXTURES, "suivi-multi.html"),
                                "--state", out])
        state = json.load(open(out, encoding="utf-8"))
        self.assertEqual([f["id"] for f in state["features"]], ["bpay", "notif"])
        bpay = state["features"][0]
        task = bpay["tasks"][0]
        self.assertEqual(task["status"], "doing")
        self.assertEqual(task["note"], "En attente identifiants.")
        self.assertEqual(task["files"], ["backend/.env.production"])
        self.assertEqual(task["history"][0]["status"], "doing")

    def test_migrate_is_idempotent_on_new_format(self):
        # génère un HTML nouveau format puis le réimporte
        self.generate()
        html = os.path.join(self.root, "docs", "suivi-auth-sso.html")
        out = os.path.join(self.root, "docs", "suivi", "reimport.json")
        migrate_from_html.main(["--file", html, "--state", out])
        state = json.load(open(out, encoding="utf-8"))
        self.assertEqual([f["id"] for f in state["features"]], ["auth-sso"])


class MigrationMetadata(Base):
    """Migration mono : métadonnées du HTML (title, h1, eyebrow, sous-titre, sources)."""

    def _migrate(self, html, tasks=None, fid="demo"):
        src = os.path.join(self.root, "legacy.html")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(html)
        out = os.path.join(self.root, "docs", "suivi", "state.json")
        argv = ["--file", src, "--state", out, "--id", fid]
        if tasks:
            argv += ["--tasks", tasks]
        migrate_from_html.main(argv)
        return json.load(open(out, encoding="utf-8"))

    def test_mono_imports_header_metadata_and_cards(self):
        state = self._migrate(LEGACY_MONO_META)
        meta = state["meta"]
        self.assertEqual(meta["title"], "Suivi d'avancement — Démo · Projet")
        self.assertEqual(meta["h1"], "Démo — fichier de suivi")
        self.assertEqual(meta["eyebrow"], "Projet · Domaine · Suivi d'avancement")
        self.assertEqual(meta["subtitle"], "Spec docs/spec.md · 2 tâches · 1 lot")
        feature = state["features"][0]
        self.assertEqual(feature["objective"], "Faire `X` et **Y**.")
        self.assertEqual(feature["decisions"], ["Décision `A`.", "Décision B."])
        # Sources : en-tête (spec, tasks) + carte Sources (Design).
        self.assertEqual(set(feature["sources"]),
                         {"spec", "tasks", "Design"})
        self.assertEqual(feature["sources"]["spec"], "docs/spec.md")

    def test_tasks_option_reloads_text_and_title_keeps_state(self):
        tasks = os.path.join(self.root, "tasks.md")
        with open(tasks, "w", encoding="utf-8") as fh:
            fh.write(LEGACY_MONO_TASKS)
        state = self._migrate(LEGACY_MONO_META, tasks=tasks)
        feature = state["features"][0]
        by_id = {t["id"]: t for t in feature["tasks"]}
        # Texte complet et titre court rechargés depuis le tasks.md…
        self.assertEqual(by_id["1.1"]["text"], "Texte complet de la première tâche (`code`)")
        self.assertTrue(by_id["1.1"]["title"])
        self.assertNotIn("Tronqué", by_id["1.1"]["text"])
        # … sans toucher au statut ni à la note issus du HTML.
        self.assertEqual(by_id["1.1"]["status"], "done")
        self.assertEqual(by_id["1.1"]["note"], "Note 1.")
        self.assertEqual(by_id["1.2"]["status"], "doing")

    def test_real_example_copy_with_tasks(self):
        """Fixture autonome : suivi mono réaliste (4 lots, 12 tâches) + tasks.md associé."""
        from collections import Counter
        src = os.path.join(self.root, "exemple-copie.html")
        shutil.copy(EXEMPLE_MONO, src)
        out = os.path.join(self.root, "docs", "suivi", "state.json")
        migrate_from_html.main(["--file", src, "--state", out, "--id", "framework",
                                "--name", "Construction du framework",
                                "--tasks", EXEMPLE_TASKS])
        state = json.load(open(out, encoding="utf-8"))
        feature = state["features"][0]
        self.assertEqual(feature["id"], "framework")
        self.assertEqual(feature["name"], "Construction du framework")
        self.assertEqual(len(feature["tasks"]), 12)
        counts = Counter(t["status"] for t in feature["tasks"])
        self.assertEqual(counts["done"], 5)
        self.assertEqual(counts["doing"], 2)
        self.assertEqual(counts["todo"], 5)
        self.assertEqual(len(feature["lots"]), 4)
        # Objectif conservé et 3 sources conservées (proposal, tasks, schéma).
        self.assertTrue(feature["objective"])
        self.assertEqual(len(feature["sources"]), 3)
        # Le tasks.md est enregistré pour rattacher les régénérations suivantes.
        self.assertEqual(feature["tasks_file"], EXEMPLE_TASKS)
        # Texte complet et titre court rechargés depuis la fixture tasks.md.
        t11 = next(t for t in feature["tasks"] if t["id"] == "1.1")
        self.assertTrue(t11["text"].startswith("Mettre en place le dépôt"),
                        t11["text"][:60])
        self.assertTrue(t11["title"])


class TextReload(Base):
    """generate.py et track*.py avec --tasks : mettre à jour text/title, garder le reste."""

    def test_generate_updates_changed_text_keeps_status_and_history(self):
        self.generate()
        state = self.load_state()
        task = state["features"][0]["tasks"][0]  # 1.1
        task["status"] = "blocked"
        task["note"] = "Note conservée."
        task["history"] = [{"date": "2026-10-09", "status": "doing", "note": "Délégué."}]
        task["executor"] = "codex"
        task["reviewer"] = "claude"
        self.write_state(state)
        # Le texte change dans tasks.md.
        md = open(self.tasks_path(), encoding="utf-8").read()
        md = md.replace("Modèle de session **SSO** (`sessions`)",
                        "Modèle de session **SSO** v2 (`sessions_v2`)")
        with open(self.tasks_path(), "w", encoding="utf-8") as fh:
            fh.write(md)
        self.generate()
        merged = self.load_state()["features"][0]["tasks"][0]
        self.assertIn("sessions_v2", merged["text"])
        self.assertNotIn("(`sessions`)", merged["text"])
        # Statut, note, historique et rôles inchangés.
        self.assertEqual(merged["status"], "blocked")
        self.assertEqual(merged["note"], "Note conservée.")
        self.assertEqual(merged["history"],
                         [{"date": "2026-10-09", "status": "doing", "note": "Délégué."}])
        self.assertEqual(merged["executor"], "codex")

    def test_track_with_tasks_reloads_text_keeps_status(self):
        self.generate()
        md = open(self.tasks_path(), encoding="utf-8").read()
        md = md.replace("Endpoint `/login`", "Endpoint `/login` v2 (`/auth`)")
        with open(self.tasks_path(), "w", encoding="utf-8") as fh:
            fh.write(md)
        old = sys.argv
        sys.argv = ["track.py", "--file", "docs/suivi-auth-sso.html",
                    "--tasks", self.tasks_path(), "2.1", "doing", "En cours."]
        try:
            tracking.task_update_main("test")
        finally:
            sys.argv = old
        task = [t for t in self.load_state()["features"][0]["tasks"] if t["id"] == "2.1"][0]
        self.assertIn("/auth", task["text"])
        self.assertEqual(task["status"], "doing")
        self.assertTrue(task["history"])



class Rendering(Base):
    def _check_html(self, path):
        html = open(path, encoding="utf-8").read()
        self.assertIn("généré par la skill suivi-taches, ne pas modifier", html)
        self.assertNotIn("__PROJECT_DATA__", html)
        self.assertEqual(re.findall(r"\{\{[A-Z0-9_]+\}\}", html), [])
        # JSON embarqué valide et « </ » échappé
        for block in ("state-data", "docs-data"):
            m = re.search(r'<script type="application/json" id="%s">(.*?)</script>' % block, html, re.S)
            self.assertIsNotNone(m, block)
            payload = m.group(1)
            self.assertNotIn("</", payload)
            json.loads(payload)  # doit être valide
        return html

    def test_render_mono(self):
        self.generate()
        self._check_html(os.path.join(self.root, "docs", "suivi-auth-sso.html"))

    def test_mono_restores_focus_cards_url_hash_and_export(self):
        """Régression : le gabarit mono doit rétablir focus, hash d'URL, cartes, export/import."""
        self.generate()
        html = open(os.path.join(self.root, "docs", "suivi-auth-sso.html"),
                    encoding="utf-8").read()
        needles = [
            'id="restoreCards"',           # « Cartes masquées »
            'id="cards"',                  # cartes Objectif / Décisions / Procédure / Sources
            'card-toggle', 'card-close',   # réductible (▾) / fermable (×)
            'data-card',
            'id="activeFilter"',           # bandeau du filtre actif
            'focus-tag',                   # libellé « Mode focus »
            'Mode focus',
            'id="emptyResult"',
            'id="export"', 'id="importBtn"', 'id="importFile"',   # export / import JSON
            'writeHash', 'readHash',       # vue partageable dans l'URL
            "lot='+encodeURIComponent", "statut='+encodeURIComponent",
            'keydown', 'Escape',           # Échap quitte le focus
            'renderCards', 'renderActiveFilter',
        ]
        for needle in needles:
            self.assertIn(needle, html, needle)

    def test_mono_header_wrap_has_no_extra_padding(self):
        """Régression : l'en-tête mono ne doit plus hériter du padding bas de .wrap."""
        self.generate()
        html = open(os.path.join(self.root, "docs", "suivi-auth-sso.html"),
                    encoding="utf-8").read()
        self.assertIn("header.top .wrap{max-width:1120px;margin:0 auto;padding:0}", html)

    def test_render_multi(self):
        os.makedirs(os.path.join(self.root, "openspec", "changes", "notifications"))
        with open(os.path.join(self.root, "openspec", "changes", "notifications", "tasks.md"),
                  "w", encoding="utf-8") as fh:
            fh.write("## 1. Envoi\n- [ ] 1.1 File d'attente\n")
        generate.main(["--out", "docs/suivi-multi.html",
                       "--tasks", self.tasks_path(),
                       "--tasks", "openspec/changes/notifications/tasks.md"])
        html = self._check_html(os.path.join(self.root, "docs", "suivi-multi.html"))
        self.assertIn('id="globalReady"', html)
        self.assertIn('id="reader"', html)

    def test_multi_keeps_rail_overview_group_drawer_density(self):
        """Régression : le gabarit multi garde rail sticky, sélection, vue d'ensemble, etc."""
        os.makedirs(os.path.join(self.root, "openspec", "changes", "notifications"))
        with open(os.path.join(self.root, "openspec", "changes", "notifications", "tasks.md"),
                  "w", encoding="utf-8") as fh:
            fh.write("## 1. Envoi\n- [ ] 1.1 File d'attente\n")
        generate.main(["--out", "docs/suivi-multi.html",
                       "--tasks", self.tasks_path(),
                       "--tasks", "openspec/changes/notifications/tasks.md"])
        html = open(os.path.join(self.root, "docs", "suivi-multi.html"),
                    encoding="utf-8").read()
        for needle in ['id="railList"', 'id="railSynth"', 'selectAll', 'selectNone',
                       'id="overview"', 'data-group', 'data-scroll', 'data-view',
                       'id="drawer"', 'id="backdrop"', 'role-badges',
                       'writeHash', 'readHash', 'localStorage']:
            self.assertIn(needle, html, needle)

    def test_render_uses_multi_template_for_two_features(self):
        state = sio.default_state()
        state["features"] = [{"id": "a", "name": "A", "tasks": [], "lots": []},
                             {"id": "b", "name": "B", "tasks": [], "lots": []}]
        out = os.path.join(self.root, "docs", "multi.html")
        render.render(state=state, out=out, root=self.root)
        html = open(out, encoding="utf-8").read()
        self.assertIn("railList", html)  # spécifique au gabarit multi

    def test_render_reads_sources(self):
        proposal = os.path.join(self.root, "openspec", "changes", "auth-sso", "proposal.md")
        with open(proposal, "w", encoding="utf-8") as fh:
            fh.write("# Proposition\n\nTexte.\n")
        generate.main(["--out", "docs/suivi-auth-sso.html", "--tasks", self.tasks_path(),
                       "--source", "proposal=openspec/changes/auth-sso/proposal.md"])
        html = open(os.path.join(self.root, "docs", "suivi-auth-sso.html"), encoding="utf-8").read()
        m = re.search(r'<script type="application/json" id="docs-data">(.*?)</script>', html, re.S)
        docs = json.loads(m.group(1))
        self.assertIn("openspec/changes/auth-sso/proposal.md", docs["files"])

    def _node_check(self, path):
        node = shutil.which("node")
        if not node:
            self.skipTest("node absent")
        html = open(path, encoding="utf-8").read()
        blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
        self.assertTrue(blocks)
        for i, block in enumerate(blocks):
            js = os.path.join(self.root, "%s-block%d.js" % (os.path.basename(path), i))
            with open(js, "w", encoding="utf-8") as fh:
                fh.write(block)
            result = subprocess.run([node, "--check", js], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, "node --check a échoué : %s" % result.stderr)

    def test_extracted_js_is_syntactically_valid(self):
        self.generate()
        self._node_check(os.path.join(self.root, "docs", "suivi-auth-sso.html"))

    def test_multi_extracted_js_is_syntactically_valid(self):
        os.makedirs(os.path.join(self.root, "openspec", "changes", "notifications"))
        with open(os.path.join(self.root, "openspec", "changes", "notifications", "tasks.md"),
                  "w", encoding="utf-8") as fh:
            fh.write("## 1. Envoi\n- [ ] 1.1 File d'attente\n")
        generate.main(["--out", "docs/suivi-multi.html",
                       "--tasks", self.tasks_path(),
                       "--tasks", "openspec/changes/notifications/tasks.md"])
        self._node_check(os.path.join(self.root, "docs", "suivi-multi.html"))


class PhasesModel(unittest.TestCase):
    def test_refresh_statuses(self):
        ph = phases.build_phases()
        tasks = [{"status": "done"}, {"status": "done"}]
        phases.refresh_statuses(ph, tasks)
        impl = [p for p in ph if p["id"] == "impl"][0]
        self.assertEqual(impl["status"], "done")
        self.assertEqual([p["status"] for p in ph if p["id"] != "impl"],
                         ["todo"] * 5)


class TasksFileAttachment(Base):
    """Correctifs : `migrate --tasks` enregistre `tasks_file` ; `generate` rattache un
    tasks.md à la feature existante dont `tasks_file` correspond (avant de déduire un id
    du chemin), et `--id` force le rattachement."""

    def _legacy(self):
        # Suivi mono nommé suivi-demo.html → id déduit « demo ».
        src = os.path.join(self.root, "suivi-demo.html")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(LEGACY_MONO_META)
        tasks = os.path.join(self.root, "tasks.md")
        with open(tasks, "w", encoding="utf-8") as fh:
            fh.write(LEGACY_MONO_TASKS)
        return src, tasks

    def test_migrate_tasks_sets_tasks_file(self):
        src, tasks = self._legacy()
        out = os.path.join(self.root, "docs", "suivi", "state.json")
        migrate_from_html.main(["--file", src, "--state", out, "--tasks", tasks])
        state = json.load(open(out, encoding="utf-8"))
        self.assertEqual(state["features"][0]["tasks_file"], tasks)

    def test_generate_reattaches_by_tasks_file(self):
        src, tasks = self._legacy()
        state_path = os.path.join(self.root, "docs", "suivi", "state.json")
        migrate_from_html.main(["--file", src, "--state", state_path, "--tasks", tasks])
        # Un nouveau lot est ajouté au tasks.md.
        with open(tasks, "a", encoding="utf-8") as fh:
            fh.write("\n## 2. Nouveau lot\n- [ ] 2.1 Tâche ajoutée\n")
        generate.main(["--out", "docs/suivi-demo.html", "--tasks", tasks,
                       "--state", state_path])
        state = json.load(open(state_path, encoding="utf-8"))
        # Une seule feature (rattachée par tasks_file, pas d'id déduit du chemin).
        self.assertEqual(len(state["features"]), 1)
        feature = state["features"][0]
        self.assertEqual(feature["id"], "demo")
        by_id = {t["id"]: t for t in feature["tasks"]}
        self.assertIn("2.1", by_id)          # la nouvelle tâche est ajoutée
        self.assertIn("1.1", by_id)          # rien n'est perdu
        # Statut et note issus du HTML conservés pour la tâche non cochée.
        self.assertEqual(by_id["1.1"]["status"], "done")
        self.assertEqual(by_id["1.1"]["note"], "Note 1.")
        # La case [x] de 1.2 force « done ».
        self.assertEqual(by_id["1.2"]["status"], "done")

    def test_generate_id_forces_attachment(self):
        self.generate()  # crée la feature auth-sso
        state_path = os.path.join(self.root, "docs", "suivi", "state.json")
        other_dir = os.path.join(self.root, "ailleurs")
        os.makedirs(other_dir)
        other = os.path.join(other_dir, "tasks.md")
        with open(other, "w", encoding="utf-8") as fh:
            fh.write(TASKS)
        # Sans --id, un id serait déduit du chemin (« ailleurs »).
        generate.main(["--out", "docs/suivi-auth-sso.html", "--tasks", other,
                       "--id", "auth-sso", "--state", state_path])
        state = json.load(open(state_path, encoding="utf-8"))
        self.assertEqual([f["id"] for f in state["features"]], ["auth-sso"])


if __name__ == "__main__":
    unittest.main()
