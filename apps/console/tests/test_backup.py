"""Tests de sauvegarde, vérification et restauration globales."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.backup import (
    BackupError,
    backup_database,
    backup_status,
    list_backups,
    restore_backup,
    verify_backup,
)
from sdlc_console.services.projects import create_project


class BackupTest(unittest.TestCase):
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
        self.session.commit()
        self.backups = self.root / "backups"

    def test_sauvegarde_verification_et_restauration(self) -> None:
        manifest = backup_database(self.session, backups_dir=self.backups)
        path = Path(manifest["backup_path"])
        self.assertTrue(path.is_file())
        self.assertTrue(manifest["verified"])
        self.assertFalse(manifest["restore_tested"])
        self.assertEqual(path.stat().st_size, manifest["size_bytes"])

        verified = verify_backup(path)
        self.assertTrue(verified["verified"])
        status = backup_status(path)
        self.assertTrue(status["fresh"])
        self.assertLess(status["age_hours"], 1)
        listing = list_backups(self.backups)
        self.assertEqual(listing["total"], 1)
        self.assertEqual(listing["latest"]["id"], manifest["id"])

        target = self.root / "restored.sqlite3"
        restored = restore_backup(path, target)
        self.assertTrue(restored["restore_tested"])
        self.assertTrue(target.is_file())
        connection = sqlite3.connect(target)
        try:
            row = connection.execute("SELECT name FROM projects").fetchone()
        finally:
            connection.close()
        self.assertEqual(row[0], "Atlas")
        self.assertTrue(verify_backup(path)["restore_tested"])

    def test_sauvegarde_alteree_refusee(self) -> None:
        manifest = backup_database(self.session, backups_dir=self.backups)
        path = Path(manifest["backup_path"])
        path.write_bytes(b"pas une base sqlite")
        with self.assertRaises(BackupError):
            verify_backup(path)
        with self.assertRaises(BackupError):
            restore_backup(path, self.root / "restored.sqlite3")

    def test_api_sauvegarde_et_liste(self) -> None:
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
            "/api/backup",
            json={},
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["backup"]["verified"])
        listing = client.get("/api/backups")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["total"], 1)
        backup_id = response.json()["backup"]["id"]
        verify = client.post(
            f"/api/backups/{backup_id}/verify",
            json={},
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["backup"]["verified"])


if __name__ == "__main__":
    unittest.main()
