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
                self.assertIn("persons", tables)
                self.assertIn("person_identities", tables)
                self.assertIn("person_merges", tables)
                self.assertIn("audit_events", tables)
                self.assertIn("commits", tables)
                self.assertIn("ingestion_runs", tables)
                self.assertIn("merge_requests", tables)
                self.assertIn("reviews", tables)
                self.assertIn("approvals", tables)
                self.assertIn("task_runs", tables)
                self.assertIn("deployments", tables)
                self.assertIn("features", tables)
                self.assertIn("feature_repositories", tables)
                self.assertIn("tasks", tables)
                self.assertIn("task_repositories", tables)
                self.assertIn("suivi_inconsistencies", tables)
                self.assertIn("gates", tables)
                self.assertIn("gate_runs", tables)
                self.assertIn("gate_findings", tables)
                self.assertIn("gate_waivers", tables)
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
                person_columns = {column["name"] for column in inspector.get_columns("persons")}
                self.assertEqual(
                    person_columns,
                    {
                        "id",
                        "project_id",
                        "display_name",
                        "role",
                        "is_bot",
                        "superseded_by_person_id",
                        "created_at",
                    },
                )
                identity_columns = {column["name"] for column in inspector.get_columns("person_identities")}
                self.assertEqual(
                    identity_columns,
                    {
                        "id",
                        "project_id",
                        "person_id",
                        "provider",
                        "external_id",
                        "email",
                        "created_at",
                    },
                )
                merge_columns = {column["name"] for column in inspector.get_columns("person_merges")}
                self.assertEqual(
                    merge_columns,
                    {
                        "id",
                        "project_id",
                        "source_person_id",
                        "target_person_id",
                        "reason",
                        "identity_ids_json",
                        "created_at",
                        "undone_at",
                    },
                )
                audit_columns = {column["name"] for column in inspector.get_columns("audit_events")}
                self.assertEqual(
                    audit_columns,
                    {
                        "id",
                        "project_id",
                        "actor_person_id",
                        "actor_label",
                        "action",
                        "object_type",
                        "object_id",
                        "payload_json",
                        "created_at",
                        "generation",
                        "prev_hash",
                        "hash",
                    },
                )
                commit_columns = {column["name"] for column in inspector.get_columns("commits")}
                self.assertEqual(
                    commit_columns,
                    {
                        "id",
                        "repository_id",
                        "sha",
                        "person_id",
                        "author_name",
                        "author_email",
                        "authored_at",
                        "committed_at",
                        "additions",
                        "deletions",
                        "files_changed",
                        "is_merge",
                        "is_bot",
                        "ai_assisted",
                        "trailers_json",
                        "commit_fingerprint",
                        "message",
                        "created_at",
                    },
                )
                run_columns = {column["name"] for column in inspector.get_columns("ingestion_runs")}
                self.assertEqual(
                    run_columns,
                    {
                        "id",
                        "project_id",
                        "repository_id",
                        "source",
                        "started_at",
                        "finished_at",
                        "status",
                        "stats_json",
                        "error",
                    },
                )
                mr_columns = {column["name"] for column in inspector.get_columns("merge_requests")}
                self.assertEqual(
                    mr_columns,
                    {
                        "id",
                        "repository_id",
                        "number",
                        "title",
                        "author_person_id",
                        "state",
                        "created_at",
                        "updated_at",
                        "merged_at",
                        "target_branch",
                        "source_branch",
                        "merge_strategy",
                        "additions",
                        "deletions",
                        "url",
                        "imported_at",
                    },
                )
                review_columns = {column["name"] for column in inspector.get_columns("reviews")}
                self.assertEqual(
                    review_columns,
                    {
                        "id",
                        "mr_id",
                        "reviewer_person_id",
                        "reviewer_agent_id",
                        "model",
                        "state",
                        "submitted_at",
                        "is_agent",
                        "independence",
                        "external_id",
                        "imported_at",
                    },
                )
                approval_columns = {column["name"] for column in inspector.get_columns("approvals")}
                self.assertEqual(
                    approval_columns,
                    {
                        "id",
                        "mr_id",
                        "actor_person_id",
                        "actor_type",
                        "approved_at",
                        "external_id",
                        "imported_at",
                    },
                )
                task_run_columns = {column["name"] for column in inspector.get_columns("task_runs")}
                self.assertEqual(
                    task_run_columns,
                    {
                        "id",
                        "project_id",
                        "run_id",
                        "task_id",
                        "task_key",
                        "agent_id",
                        "primary_repository_id",
                        "model",
                        "role",
                        "started_at",
                        "ended_at",
                        "status",
                        "cost_eur",
                        "estimated_cost_eur",
                        "budget_eur",
                        "tokens_in",
                        "tokens_out",
                        "pid",
                        "process_group",
                        "exit_code",
                        "log_path",
                        "cancel_requested",
                        "report_path",
                        "origin",
                        "imported_at",
                    },
                )
                deployment_columns = {column["name"] for column in inspector.get_columns("deployments")}
                self.assertEqual(
                    deployment_columns,
                    {
                        "id",
                        "project_id",
                        "deploy_id",
                        "repository_id",
                        "repository_label",
                        "env",
                        "version",
                        "status",
                        "started_at",
                        "finished_at",
                        "by_person_id",
                        "by_label",
                        "note",
                        "feature_id",
                        "feature_key",
                        "is_rollback",
                        "rollback_of_version",
                        "imported_at",
                    },
                )
                feature_columns = {column["name"] for column in inspector.get_columns("features")}
                self.assertEqual(
                    feature_columns,
                    {
                        "id",
                        "project_id",
                        "primary_repository_id",
                        "key",
                        "name",
                        "status",
                        "owner_person_id",
                        "spec_path",
                        "change",
                        "objective",
                        "tasks_file",
                        "sources_json",
                        "phases_json",
                        "delivered",
                        "blocked",
                        "version",
                        "updated_at",
                    },
                )
                task_columns = {column["name"] for column in inspector.get_columns("tasks")}
                self.assertEqual(
                    task_columns,
                    {
                        "id",
                        "feature_id",
                        "primary_repository_id",
                        "key",
                        "title",
                        "description",
                        "lot",
                        "status",
                        "owner_person_id",
                        "reviewer_person_id",
                        "executor_label",
                        "reviewer_label",
                        "files_json",
                        "acceptance",
                        "note",
                        "updated_at",
                    },
                )
                feature_repository_columns = {
                    column["name"] for column in inspector.get_columns("feature_repositories")
                }
                self.assertEqual(feature_repository_columns, {"feature_id", "repository_id"})
                task_repository_columns = {
                    column["name"] for column in inspector.get_columns("task_repositories")
                }
                self.assertEqual(task_repository_columns, {"task_id", "repository_id", "is_primary"})
                gate_columns = {column["name"] for column in inspector.get_columns("gates")}
                self.assertEqual(
                    gate_columns,
                    {
                        "id",
                        "project_id",
                        "key",
                        "name",
                        "blocking",
                        "config_json",
                        "config_fingerprint",
                        "created_at",
                        "updated_at",
                    },
                )
                gate_run_columns = {
                    column["name"] for column in inspector.get_columns("gate_runs")
                }
                self.assertEqual(
                    gate_run_columns,
                    {
                        "id",
                        "project_id",
                        "gate_id",
                        "gate_key",
                        "repository_id",
                        "feature_id",
                        "verdict",
                        "blocks",
                        "reason",
                        "report_path",
                        "config_fingerprint",
                        "controls_json",
                        "evidence_json",
                        "findings_count",
                        "started_at",
                        "finished_at",
                        "created_at",
                    },
                )
                gate_finding_columns = {
                    column["name"] for column in inspector.get_columns("gate_findings")
                }
                self.assertEqual(
                    gate_finding_columns,
                    {
                        "id",
                        "gate_run_id",
                        "control_key",
                        "key",
                        "severity",
                        "message",
                        "file_path",
                        "line",
                        "evidence_path",
                    },
                )
                waiver_columns = {
                    column["name"] for column in inspector.get_columns("gate_waivers")
                }
                self.assertEqual(
                    waiver_columns,
                    {
                        "id",
                        "project_id",
                        "gate_key",
                        "target_type",
                        "target_id",
                        "reason",
                        "owner",
                        "approver",
                        "expires_at",
                        "created_at",
                        "revoked_at",
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
                self.assertNotIn("persons", tables)
                self.assertNotIn("person_identities", tables)
                self.assertNotIn("person_merges", tables)
                self.assertNotIn("audit_events", tables)
                self.assertNotIn("commits", tables)
                self.assertNotIn("ingestion_runs", tables)
                self.assertNotIn("merge_requests", tables)
                self.assertNotIn("reviews", tables)
                self.assertNotIn("approvals", tables)
                self.assertNotIn("task_runs", tables)
                self.assertNotIn("deployments", tables)
                self.assertNotIn("features", tables)
                self.assertNotIn("feature_repositories", tables)
                self.assertNotIn("tasks", tables)
                self.assertNotIn("task_repositories", tables)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
