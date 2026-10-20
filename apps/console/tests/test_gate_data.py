"""Tests du gate de données : migrations, PII, sauvegarde, rétention et chiffrement."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, GateFinding
from sdlc_console.services.gate_data import (
    run_data_gate,
    scan_migrations,
    scan_pii_logs,
)
from sdlc_console.services.projects import create_project


class GateDataTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.engine = make_engine(f"sqlite:///{self.root / 'db.sqlite3'}")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.Session = make_session_factory(self.engine)
        self.session = self.Session()
        self.addCleanup(self.session.close)
        self.project = create_project(self.session, name="Atlas", slug="atlas")
        self.session.commit()
        self.migrations = self.root / "reports" / "data" / "migrations"
        self.logs = self.root / "reports" / "data" / "logs"
        self.migrations.mkdir(parents=True)
        self.logs.mkdir(parents=True)
        self.backup = self.root / "reports" / "data" / "backup.json"
        self._backup(restore_tested=True)

    def _migration(self, sql: str, name: str = "001.sql") -> Path:
        path = self.migrations / name
        path.write_text(sql, encoding="utf-8")
        return path

    def _log(self, content: str, name: str = "app.log") -> Path:
        path = self.logs / name
        path.write_text(content, encoding="utf-8")
        return path

    def _backup(
        self,
        *,
        restore_tested: bool = True,
        verified: bool = True,
        age_hours: float = 1,
    ) -> Path:
        self.backup.write_text(
            json.dumps(
                {
                    "verified": verified,
                    "restore_tested": restore_tested,
                    "age_hours": age_hours,
                }
            ),
            encoding="utf-8",
        )
        return self.backup

    def _run(self, **kwargs):
        return run_data_gate(
            self.session,
            self.project,
            root=self.root,
            **kwargs,
        )

    def test_gate_data_sain_passe(self) -> None:
        self._migration("ALTER TABLE users ADD COLUMN age INTEGER;")
        self._log("2026-10-20 INFO démarrage\n")
        result = self._run(retention_days=365, encrypted=True)
        self.assertEqual(result.evaluation.verdict, "pass")
        self.assertFalse(result.evaluation.blocks)
        self.assertEqual(result.evaluation.controls[0]["key"], "migrations")
        report = self.root / "reports" / "gates" / "data.json"
        self.assertTrue(report.is_file())
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["verdict"], "pass")

    def test_migration_destructive_bloque(self) -> None:
        self._migration("ALTER TABLE users ADD COLUMN email TEXT NOT NULL;")
        self._log("ok\n")
        result = self._run(retention_days=365, encrypted=True)
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertTrue(result.evaluation.blocks)
        self.assertEqual(len(result.migrations), 1)
        self.assertIn("NOT NULL", result.migrations[0].reason)
        self.assertEqual(
            self.session.scalar(select(func.count(GateFinding.id))),
            1,
        )

    def test_pii_dans_les_logs_bloque(self) -> None:
        self._migration("SELECT 1;")
        self._log("utilisateur alice@example.com connecté\n")
        result = self._run(retention_days=365, encrypted=True)
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertTrue(result.evaluation.blocks)
        self.assertEqual(result.pii[0].value, "alice@example.com")
        self.assertIn("PII", json.dumps(result.evaluation.findings, ensure_ascii=False))

    def test_sauvegarde_non_testee_bloque(self) -> None:
        self._migration("SELECT 1;")
        self._log("ok\n")
        self._backup(restore_tested=False)
        result = self._run(retention_days=365, encrypted=True)
        self.assertEqual(result.evaluation.verdict, "fail")
        self.assertTrue(result.evaluation.blocks)
        self.assertEqual(result.evaluation.controls[2]["verdict"], "fail")

    def test_retention_et_chiffrement_absents_alertent(self) -> None:
        self._migration("SELECT 1;")
        self._log("ok\n")
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "warn")
        self.assertFalse(result.evaluation.blocks)
        details = json.dumps(result.evaluation.findings, ensure_ascii=False)
        self.assertIn("rétention", details)
        self.assertIn("chiffrement", details)

    def test_absence_de_preuve_not_run(self) -> None:
        self.migrations.joinpath("001.sql").unlink(missing_ok=True)
        self.logs.joinpath("app.log").unlink(missing_ok=True)
        self.backup.unlink(missing_ok=True)
        result = self._run()
        self.assertEqual(result.evaluation.verdict, "not_run")
        self.assertTrue(result.evaluation.blocks)

    def test_scan_migrations_et_logs(self) -> None:
        path = self._migration(
            "ALTER TABLE users DROP COLUMN legacy;\n"
            "DELETE FROM users;\n"
        )
        risks = scan_migrations([path], root=self.root)
        self.assertEqual(len(risks), 2)
        self.assertIn("DROP COLUMN", risks[0].reason)
        self.assertIn("DELETE", risks[1].reason)
        log = self._log("email bob@example.com\n")
        pii = scan_pii_logs([log], root=self.root)
        self.assertEqual(pii[0].line, 1)


if __name__ == "__main__":
    unittest.main()
