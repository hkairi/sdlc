"""Tests de la mise à jour atomique d'une tâche (API, CLI et fichiers)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from sdlc_console.app import create_app
from sdlc_console.cli import main
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, SuiviInconsistency, Task
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.projects import create_project
from sdlc_console.services.task_update import TaskUpdateError, update_task_status


class TaskUpdateTest(unittest.TestCase):
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
        self.feature = create_feature(
            self.session,
            self.project,
            key="atlas",
            name="Atlas",
            change="atlas",
            tasks_file="openspec/changes/atlas/tasks.md",
            status="doing",
        )
        self.first = create_task(
            self.session,
            self.feature,
            key="1.1",
            title="Première",
            status="todo",
        )
        self.second = create_task(
            self.session,
            self.feature,
            key="1.2",
            title="Deuxième",
            status="todo",
        )
        self.session.commit()
        self.state_path = self.root / "docs" / "suivi" / "atlas.json"
        self.tasks_path = self.root / "openspec" / "changes" / "atlas" / "tasks.md"
        self.state_path.parent.mkdir(parents=True)
        self.tasks_path.parent.mkdir(parents=True)
        self.state_path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "file_updated": "2026-10-20",
                    "features": [
                        {
                            "id": "atlas",
                            "name": "Atlas",
                            "change": "atlas",
                            "status": "doing",
                            "tasks_file": "openspec/changes/atlas/tasks.md",
                            "tasks": [
                                {
                                    "id": "1.1",
                                    "title": "Première",
                                    "status": "todo",
                                    "updated": "2026-10-20",
                                    "note": None,
                                    "history": [],
                                },
                                {
                                    "id": "1.2",
                                    "title": "Deuxième",
                                    "status": "todo",
                                    "updated": "2026-10-20",
                                    "note": None,
                                    "history": [],
                                },
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.tasks_path.write_text(
            "## 1. Socle\n"
            "- [ ] 1.1 Première\n"
            "- [ ] 1.2 Deuxième\n",
            encoding="utf-8",
        )

    def _update(self, task: Task, status: str, note: str | None = None):
        return update_task_status(
            self.session,
            self.project,
            task,
            status=status,
            note=note,
            root=self.root,
        )

    def _checkbox(self, task_key: str) -> bool:
        prefix = "- ["
        for line in self.tasks_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(prefix) and f"] {task_key} " in line:
                return line[3].lower() == "x"
        self.fail(f"tâche absente de tasks.md : {task_key}")

    def _state_task(self, task_key: str) -> dict[str, object]:
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        for feature in state["features"]:
            for task in feature["tasks"]:
                if task["id"] == task_key:
                    return task
        self.fail(f"tâche absente de state.json : {task_key}")

    def test_mise_a_jour_des_trois_supports(self) -> None:
        result = self._update(self.first, "done", "Terminé par le test")
        self.assertLess(result.duration_ms, 2000)
        self.assertEqual(self.first.status, "done")
        self.assertEqual(self.first.note, "Terminé par le test")

        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        raw_task = state["features"][0]["tasks"][0]
        self.assertEqual(raw_task["status"], "done")
        self.assertEqual(raw_task["note"], "Terminé par le test")
        self.assertEqual(raw_task["history"][-1]["status"], "done")
        self.assertIn("[x] 1.1 Première", self.tasks_path.read_text(encoding="utf-8"))
        self.assertTrue(result.html_path.is_file())
        self.assertIn("Terminé", result.html_path.read_text(encoding="utf-8"))
        self.assertTrue(result.json_path.is_file())
        generated = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(generated["summary"]["done"], 1)
        self.assertEqual(generated["summary"]["todo"], 1)

        rerun = self._update(self.first, "doing")
        self.assertEqual(self.first.status, "doing")
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        raw_task = state["features"][0]["tasks"][0]
        self.assertEqual(raw_task["status"], "doing")
        self.assertEqual(raw_task["note"], "Terminé par le test")
        self.assertIn("[ ] 1.1 Première", self.tasks_path.read_text(encoding="utf-8"))
        self.assertEqual(len(raw_task["history"]), 2)
        self.assertGreaterEqual(rerun.duration_ms, 0)

    def test_done_equivaut_a_case_cochee_pour_tous_les_statuts(self) -> None:
        for status in ("done", "todo", "doing", "blocked", "cancelled"):
            self._update(self.first, status, f"statut {status}")
            state_task = self._state_task("1.1")
            self.assertEqual(state_task["status"], status)
            self.assertEqual(
                self._checkbox("1.1"),
                status == "done",
                f"case incohérente pour le statut {status}",
            )

    def test_mise_a_jour_tache_par_tache_sans_mode_lot(self) -> None:
        self._update(self.first, "done", "seule la première")
        self.session.expire_all()
        first = self.session.get(Task, self.first.id)
        second = self.session.get(Task, self.second.id)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        assert first is not None and second is not None
        self.assertEqual(first.status, "done")
        self.assertEqual(second.status, "todo")
        self.assertEqual(self._state_task("1.1")["status"], "done")
        self.assertEqual(self._state_task("1.2")["status"], "todo")
        self.assertTrue(self._checkbox("1.1"))
        self.assertFalse(self._checkbox("1.2"))

        self._update(self.second, "done", "puis la seconde")
        self.session.expire_all()
        first = self.session.get(Task, self.first.id)
        self.assertIsNotNone(first)
        assert first is not None
        self.assertEqual(first.status, "done")
        self.assertTrue(self._checkbox("1.1"))
        self.assertTrue(self._checkbox("1.2"))

    def test_cli_refuse_plusieurs_taches(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            main(["task", "set", "1.1", "done", "1.2"])
        self.assertEqual(raised.exception.code, 2)

    def test_incoherence_locale_supprimee(self) -> None:
        self.session.add(
            SuiviInconsistency(
                project_id=self.project.id,
                feature_key="atlas",
                task_key="1.1",
                kind="etat_done_case_vide",
                message="state.json indique done mais tasks.md n'est pas coché",
                state_status="done",
                tasks_md_checked=False,
            )
        )
        self.session.commit()
        self._update(self.first, "done", "Corrigé")
        remaining = self.session.scalars(select(SuiviInconsistency)).all()
        self.assertEqual(remaining, [])

    def test_echec_ecriture_restaure_les_sources(self) -> None:
        state_before = self.state_path.read_text(encoding="utf-8")
        tasks_before = self.tasks_path.read_text(encoding="utf-8")
        blocker = self.root / "blocked"
        blocker.write_text("fichier", encoding="utf-8")
        with self.assertRaises(OSError):
            self._update_with_paths(self.first, "done", blocker / "suivi.html")
        self.assertEqual(self.state_path.read_text(encoding="utf-8"), state_before)
        self.assertEqual(self.tasks_path.read_text(encoding="utf-8"), tasks_before)
        self.assertEqual(
            self.session.scalars(select(SuiviInconsistency)).all(),
            [],
        )
        self.session.rollback()
        refreshed = self.session.get(Task, self.first.id)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "todo")
        self.assertEqual(self._state_task("1.1")["status"], "todo")
        self.assertFalse(self._checkbox("1.1"))

    def test_echec_ecriture_state_apres_tasks_md(self) -> None:
        from unittest.mock import patch

        from sdlc_console.services import task_update as task_update_module

        state_before = self.state_path.read_text(encoding="utf-8")
        tasks_before = self.tasks_path.read_text(encoding="utf-8")
        original = task_update_module._atomic_write

        def fail_state(path: Path, content: str) -> None:
            if path == self.state_path.resolve():
                raise OSError("écriture state.json impossible")
            original(path, content)

        with (
            patch.object(task_update_module, "_atomic_write", side_effect=fail_state),
            self.assertRaises(OSError),
        ):
            self._update(self.first, "done", "échec state")
        self.assertEqual(self.state_path.read_text(encoding="utf-8"), state_before)
        self.assertEqual(self.tasks_path.read_text(encoding="utf-8"), tasks_before)
        self.assertEqual(
            self.session.scalars(select(SuiviInconsistency)).all(),
            [],
        )
        self.session.expire_all()
        refreshed = self.session.get(Task, self.first.id)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "todo")
        self.assertEqual(self._state_task("1.1")["status"], "todo")
        self.assertFalse(self._checkbox("1.1"))

    def _update_with_paths(self, task: Task, status: str, html_path: Path):
        return update_task_status(
            self.session,
            self.project,
            task,
            status=status,
            note="échec",
            html_path=html_path,
            root=self.root,
        )

    def test_tache_absente_de_tasks_md_refusee(self) -> None:
        self.tasks_path.write_text("## 1. Socle\n- [ ] 1.2 Deuxième\n", encoding="utf-8")
        with self.assertRaises(TaskUpdateError):
            self._update(self.first, "done")
        self.session.rollback()
        refreshed = self.session.get(Task, self.first.id)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "todo")

    def test_api_patch_avec_csrf(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            csrf_secret=b"test-secret",
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        token = client.get("/api/csrf").json()["token"]
        response = client.patch(
            f"/api/projects/{self.project.id}/tasks/{self.first.id}",
            json={"status": "done", "note": "via API"},
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["task"]["status"], "done")
        self.assertLess(payload["duration_ms"], 2000)
        self.assertEqual(
            json.loads(self.state_path.read_text(encoding="utf-8"))["features"][0]["tasks"][0]["note"],
            "via API",
        )
        self.assertIn("[x] 1.1", self.tasks_path.read_text(encoding="utf-8"))
        status = client.get(
            f"/api/projects/{self.project.id}/suivi/status"
        ).json()
        self.assertTrue(status["ready"])
        self.assertFalse(status["stale"])
        self.assertEqual(status["summary"]["done"], 1)

        forbidden = client.patch(
            f"/api/projects/{self.project.id}/tasks/{self.second.id}",
            json={"status": "done"},
        )
        self.assertEqual(forbidden.status_code, 403)
        invalid = client.patch(
            f"/api/projects/{self.project.id}/tasks/{self.second.id}",
            json={"status": "invalide"},
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(invalid.status_code, 422)
        missing = client.patch(
            f"/api/projects/{self.project.id}/tasks/99999",
            json={"status": "done"},
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(missing.status_code, 404)

    def test_cli_task_set(self) -> None:
        code = main(
            [
                "task",
                "set",
                str(self.first.id),
                "done",
                "--note",
                "via CLI",
                "--project",
                "atlas",
                "--database",
                f"sqlite:///{self.root / 'db.sqlite3'}",
                "--root",
                str(self.root),
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("[x] 1.1", self.tasks_path.read_text(encoding="utf-8"))
        self.assertEqual(
            json.loads(self.state_path.read_text(encoding="utf-8"))["features"][0]["tasks"][0]["note"],
            "via CLI",
        )
        with self.Session() as session:
            refreshed = session.get(Task, self.first.id)
            self.assertIsNotNone(refreshed)
            assert refreshed is not None
            self.assertEqual(refreshed.status, "done")


if __name__ == "__main__":
    unittest.main()
