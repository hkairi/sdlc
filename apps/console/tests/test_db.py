"""Tests SQLite : pragmas, modèles et migrations Alembic."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Project

CONSOLE_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = CONSOLE_ROOT / "alembic.ini"


class DbTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "nested" / "test.sqlite3"
        self.url = f"sqlite:///{self.db_path}"
        self.engine = make_engine(self.url)
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.Session = make_session_factory(self.engine)

    def test_pragmas_sqlite(self) -> None:
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("PRAGMA journal_mode")).scalar(), "wal")
            self.assertEqual(connection.execute(text("PRAGMA foreign_keys")).scalar(), 1)
            self.assertEqual(connection.execute(text("PRAGMA synchronous")).scalar(), 1)
            self.assertEqual(connection.execute(text("PRAGMA busy_timeout")).scalar(), 5000)

    def test_creation_du_dossier_parent(self) -> None:
        self.assertTrue(self.db_path.parent.is_dir())

    def test_insertion_projet(self) -> None:
        with self.Session() as session:
            session.add(Project(name="Atlas", slug="atlas"))
            session.commit()
            projects = session.query(Project).all()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].slug, "atlas")
        self.assertEqual(projects[0].timezone, "Europe/Paris")
        self.assertIsNotNone(projects[0].created_at)

    def test_slug_unique(self) -> None:
        with self.Session() as session:
            session.add_all([Project(name="A", slug="atlas"), Project(name="B", slug="atlas")])
            with self.assertRaises(IntegrityError):
                session.commit()


class MigrationTest(unittest.TestCase):
    def test_upgrade_alembic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp) / 'migrated.sqlite3'}"
            config = Config(str(ALEMBIC_INI))
            config.set_main_option("sqlalchemy.url", url)
            command.upgrade(config, "head")
            engine = make_engine(url)
            try:
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                self.assertIn("projects", tables)
                self.assertIn("repositories", tables)
                columns = {column["name"] for column in inspector.get_columns("projects")}
                self.assertEqual(columns, {"id", "name", "slug", "timezone", "created_at"})
                repository_columns = {column["name"] for column in inspector.get_columns("repositories")}
                self.assertEqual(
                    repository_columns,
                    {
                        "id",
                        "project_id",
                        "name",
                        "provider",
                        "url",
                        "local_path",
                        "default_branch",
                        "is_primary",
                        "dedup_group",
                        "is_mirror",
                        "is_fork",
                        "retired_at",
                        "created_at",
                    },
                )
            finally:
                engine.dispose()

    def test_downgrade_alembic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp) / 'downgraded.sqlite3'}"
            config = Config(str(ALEMBIC_INI))
            config.set_main_option("sqlalchemy.url", url)
            command.upgrade(config, "head")
            command.downgrade(config, "base")
            engine = make_engine(url)
            try:
                tables = inspect(engine).get_table_names()
                self.assertNotIn("projects", tables)
                self.assertNotIn("repositories", tables)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
