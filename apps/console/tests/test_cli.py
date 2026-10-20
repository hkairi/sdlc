"""Tests de la CLI (version, sécurité, configuration, schéma)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path

from sdlc_console.cli import DEFAULT_HOST, main

HAS_CONFIG_DEPS = (
    importlib.util.find_spec("yaml") is not None
    and importlib.util.find_spec("jsonschema") is not None
)
HAS_DB_DEPS = (
    importlib.util.find_spec("alembic") is not None
    and importlib.util.find_spec("sqlalchemy") is not None
)

MINIMAL_YAML = """\
version: 1
project:
  name: Atlas
  kind: new
  stack: [python]
agents:
  claude:
    enabled: true
    cli: "claude -p"
    models:
      build: sonnet
orchestrator: claude
executors: [claude]
confidentiality: client
ci:
  tool: github-actions
  mode: integrate
  coverage_min: 80
  block_on: [critique, haute]
deploy:
  decided_at: conception
  targets:
    - component: api
      profile: vps-compose
organisation:
  parallelism: sequential
  commit_cadence: feature
  max_review_iterations: 3
  task_timeout_min: 30
gates:
  default: toi
  spec_freeze: client-po
  recette: client-po
  go_no_go: toi
dashboard:
  file: docs/suivi-projet.html
  reports_dir: reports/
  embed_markdown: true
  embed_max_kb: 2048
  publish: none
paths:
  templates: .sdlc/templates
  spec: .sdlc/workflow-sdlc.md
  docs: docs
  reports: reports
  ci_script: scripts/ci.sh
"""


def _write_config(content: str) -> Path:
    descriptor, name = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)
    return Path(name)


class CliTest(unittest.TestCase):
    def test_version(self) -> None:
        out = io.StringIO()
        with self.assertRaises(SystemExit) as exc, contextlib.redirect_stdout(out):
            main(["--version"])
        self.assertEqual(exc.exception.code, 0)
        self.assertIn("sdlc-console", out.getvalue())

    def test_serve_refuse_un_bind_non_loopback(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main(["serve", "--host", "0.0.0.0"])
        self.assertEqual(code, 2)
        self.assertIn("refus", err.getvalue())

    def test_commande_inconnue_affiche_l_aide(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([])
        self.assertEqual(code, 0)
        self.assertIn("sdlc-console", out.getvalue())

    @unittest.skipUnless(HAS_DB_DEPS, "alembic/sqlalchemy non installés")
    def test_init_et_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp) / 'db.sqlite3'}"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["init", "--database", url]), 0)
                self.assertEqual(main(["schema", "status", "--database", url]), 0)
                self.assertEqual(main(["schema", "migrate", "--database", url]), 0)
            self.assertIn("base initialisée", out.getvalue())
            self.assertIn("schéma : à jour", out.getvalue())

    @unittest.skipUnless(HAS_DB_DEPS, "alembic/sqlalchemy non installés")
    def test_schema_status_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp) / 'empty.sqlite3'}"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["schema", "status", "--database", url])
            self.assertEqual(code, 1)
            self.assertIn("migration requise", out.getvalue())

    @unittest.skipUnless(HAS_CONFIG_DEPS and HAS_DB_DEPS, "pyyaml/jsonschema/alembic absents")
    def test_doctor_config_valide_et_schema_a_jour(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_config(MINIMAL_YAML)
            url = f"sqlite:///{Path(tmp) / 'db.sqlite3'}"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["init", "--database", url]), 0)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["doctor", "--config", str(path), "--database", url])
            self.assertEqual(code, 0)
            self.assertIn("configuration : valide", out.getvalue())
            self.assertIn("schéma : à jour", out.getvalue())
            self.assertIn(DEFAULT_HOST, out.getvalue())

    @unittest.skipUnless(HAS_CONFIG_DEPS and HAS_DB_DEPS, "pyyaml/jsonschema/alembic absents")
    def test_doctor_schema_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_config(MINIMAL_YAML)
            url = f"sqlite:///{Path(tmp) / 'empty.sqlite3'}"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["doctor", "--config", str(path), "--database", url])
            self.assertEqual(code, 1)
            self.assertIn("migration requise", out.getvalue())

    @unittest.skipUnless(HAS_CONFIG_DEPS, "pyyaml/jsonschema non installés")
    def test_doctor_config_absente(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["doctor", "--config", "/tmp/inexistant-sdlc-config.yaml"])
        self.assertEqual(code, 1)
        self.assertIn("échec", out.getvalue())

    @unittest.skipUnless(HAS_CONFIG_DEPS, "pyyaml/jsonschema non installés")
    def test_doctor_config_invalide(self) -> None:
        path = _write_config("version: 1\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["doctor", "--config", str(path)])
        self.assertEqual(code, 1)
        self.assertIn("échec", out.getvalue())


if __name__ == "__main__":
    unittest.main()
