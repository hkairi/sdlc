"""Tests de rétention, purge, ancrage et intégrité de l'audit."""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import AuditEvent, Base, Commit, IngestionRun, TaskRun, utc_now
from sdlc_console.services.audit import anchor_audit, append_audit, verify_audit_chain
from sdlc_console.services.backup import backup_database
from sdlc_console.services.projects import add_repository, create_project
from sdlc_console.services.purge import (
    PurgeError,
    run_audit_purge,
    run_purge,
)


class PurgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.database = self.root / "data" / "sdlc.sqlite3"
        self.database.parent.mkdir()
        self.engine = make_engine(f"sqlite:///{self.database}")
        Base.metadata.create_all(self.engine)
        self.Session = make_session_factory(self.engine)
        self.session = self.Session()
        self.addCleanup(self.session.close)
        self.project = create_project(self.session, name="Atlas", slug="atlas")
        repo_path = self.root / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()
        repository = add_repository(
            self.session,
            self.project,
            name="repo",
            provider="github",
            url="https://github.com/hm/repo",
            local_path=repo_path,
        )
        now = datetime.now(UTC)
        old = now - timedelta(days=500)
        self.old_commit = Commit(
            repository_id=repository.id,
            sha="old",
            authored_at=old,
            committed_at=old,
            commit_fingerprint="old",
            message="old",
        )
        self.new_commit = Commit(
            repository_id=repository.id,
            sha="new",
            authored_at=now,
            committed_at=now,
            commit_fingerprint="new",
            message="new",
        )
        # Le dépôt est facultatif pour ces lignes ; on utilise un identifiant
        # existant uniquement quand le test en crée un.
        self.session.add_all([self.old_commit, self.new_commit])
        self.old_run = TaskRun(
            project_id=self.project.id,
            run_id="old-run",
            status="done",
            started_at=old,
            imported_at=old,
        )
        self.new_run = TaskRun(
            project_id=self.project.id,
            run_id="new-run",
            status="done",
            started_at=now,
            imported_at=now,
        )
        self.session.add_all([self.old_run, self.new_run])
        self.old_ingestion = IngestionRun(
            project_id=self.project.id,
            source="git",
            status="done",
            started_at=old,
            finished_at=old,
        )
        self.new_ingestion = IngestionRun(
            project_id=self.project.id,
            source="git",
            status="done",
            started_at=now,
            finished_at=now,
        )
        self.session.add_all([self.old_ingestion, self.new_ingestion])
        self.session.commit()
        self.old_audit = append_audit(
            self.session,
            project_id=self.project.id,
            action="seed",
            object_type="test",
            object_id="old",
        )
        self.session.commit()
        self.backups = self.root / "backups"
        self.files = self.root / "reports" / "runs"
        self.files.mkdir(parents=True)
        old_file = self.files / "old.log"
        old_file.write_text("old")
        old_time = time.time() - 500 * 86400
        os.utime(old_file, (old_time, old_time))
        self.new_file = self.files / "new.log"
        self.new_file.write_text("new")
        logs = self.root / "logs"
        logs.mkdir()
        old_log = logs / "old.log"
        old_log.write_text("old")
        os.utime(old_log, (old_time, old_time))

    def _backup(self) -> None:
        backup_database(self.session, backups_dir=self.backups)

    def test_purge_standard_conserve_audit_et_supprime_les_vieux(self) -> None:
        self._backup()
        result = run_purge(
            self.session,
            self.project,
            backups_dir=self.backups,
            root=self.root,
            confirm=True,
        )
        self.session.commit()
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["deleted"]["commits"], 1)
        self.assertEqual(result["deleted"]["task_runs"], 1)
        self.assertEqual(result["deleted"]["ingestion_runs"], 1)
        self.assertIn("reports/runs/old.log", result["files_deleted"])
        self.assertIn("logs/old.log", result["files_deleted"])
        self.assertTrue(self.new_file.is_file())
        self.assertFalse((self.files / "old.log").exists())
        self.assertFalse((self.root / "logs" / "old.log").exists())
        self.assertEqual(
            self.session.scalar(select(func.count(AuditEvent.id))),
            2,
        )  # seed + purge.completed
        integrity = verify_audit_chain(self.session, self.project.id)
        self.assertTrue(integrity["valid"], integrity)
        self.assertTrue(
            self.session.scalar(select(func.count(Commit.id)).where(Commit.sha == "new"))
        )

    def test_backup_absent_ou_trop_ancien_refuse(self) -> None:
        with self.assertRaises(PurgeError) as missing:
            run_purge(
                self.session,
                self.project,
                backups_dir=self.backups,
                root=self.root,
                confirm=True,
            )
        self.assertEqual(missing.exception.code, "backup_too_old")
        self._backup()
        # Rendre le manifeste artificiellement ancien.
        manifest = next(self.backups.glob("*.json"))
        data = json.loads(manifest.read_text())
        data["created_at"] = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(PurgeError) as old:
            run_purge(
                self.session,
                self.project,
                backups_dir=self.backups,
                root=self.root,
                confirm=True,
            )
        self.assertEqual(old.exception.code, "backup_too_old")

    def test_purge_sans_confirmation_et_ingestion_en_cours(self) -> None:
        with self.assertRaises(PurgeError) as missing:
            run_purge(
                self.session,
                self.project,
                backups_dir=self.backups,
                root=self.root,
            )
        self.assertEqual(missing.exception.code, "confirmation_required")
        self._backup()
        running = IngestionRun(
            project_id=self.project.id,
            source="git",
            status="running",
            started_at=utc_now(),
        )
        self.session.add(running)
        self.session.commit()
        with self.assertRaises(PurgeError) as busy:
            run_purge(
                self.session,
                self.project,
                backups_dir=self.backups,
                root=self.root,
                confirm=True,
            )
        self.assertEqual(busy.exception.code, "purge_busy")

    def test_ancrage_et_purge_audit(self) -> None:
        anchor = anchor_audit(self.session, self.project.id)
        self.session.commit()
        next_event = append_audit(
            self.session,
            project_id=self.project.id,
            action="after_anchor",
            object_type="test",
            object_id="next",
        )
        self.session.commit()
        self.assertEqual(next_event.generation, anchor.generation + 1)
        self.assertEqual(next_event.prev_hash, "")
        self.assertTrue(verify_audit_chain(self.session, self.project.id)["valid"])
        result = run_audit_purge(
            self.session,
            self.project,
            cutoff=datetime.now(UTC) + timedelta(days=1),
        )
        self.session.commit()
        self.assertGreater(result["deleted"], 0)
        self.assertTrue(result["integrity"]["valid"])

    def test_chaine_audit_alteree_detectee(self) -> None:
        event = append_audit(
            self.session,
            project_id=self.project.id,
            action="tamper",
            object_type="test",
            object_id="tamper",
        )
        self.session.commit()
        event.hash = "0" * 64
        self.session.commit()
        integrity = verify_audit_chain(self.session, self.project.id)
        self.assertFalse(integrity["valid"])
        self.assertTrue(any("empreinte invalide" in issue for issue in integrity["issues"]))

    def test_api_purge(self) -> None:
        self._backup()
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            backup_dir=self.backups,
            watcher_enabled=False,
            csrf_secret=b"test-secret",
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        token = client.get("/api/csrf").json()["token"]
        response = client.post(
            f"/api/projects/{self.project.id}/purge",
            json={"confirm": True},
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["audit_excluded"])
        integrity = client.get(
            f"/api/projects/{self.project.id}/audit/integrity"
        )
        self.assertEqual(integrity.status_code, 200)
        self.assertTrue(integrity.json()["valid"])


if __name__ == "__main__":
    unittest.main()
