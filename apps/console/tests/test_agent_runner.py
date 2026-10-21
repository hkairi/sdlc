"""Tests du runner d'agents : préflight, file et concurrence."""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, TaskRun
from sdlc_console.services.agent_runner import (
    RunPreflightError,
    cancel_run,
    dispatch_queue,
    enqueue_run,
    refresh_run,
)
from sdlc_console.services.projects import add_repository, create_project


class AgentRunnerTest(unittest.TestCase):
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
        repo_path = self.root / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()
        self.repo = add_repository(
            self.session,
            self.project,
            name="repo",
            provider="github",
            url="https://github.com/hm/repo",
            local_path=repo_path,
        )
        self.config = {
            "runner": {"max_concurrency": 1},
            "agents": {
                "agent-a": {
                    "enabled": True,
                    "cli": sys.executable,
                    "models": {
                        "m1": {
                            "command": [
                                sys.executable,
                                "-c",
                                "import time; time.sleep(0.2); print('ok')",
                            ]
                        }
                    },
                }
            },
        }
        self.session.commit()

    def _enqueue(self, task_key: str = "1.1"):
        return enqueue_run(
            self.session,
            self.project,
            agent_id="agent-a",
            model="m1",
            role="executor",
            task_key=task_key,
            repository_id=self.repo.id,
            config=self.config,
            root=self.root,
        )

    def test_preflight_refuse_cli_inconnue(self) -> None:
        config = {
            "agents": {
                "agent-a": {
                    "enabled": True,
                    "models": {"m1": {"command": ["/commande/inexistante"]}},
                }
            }
        }
        with self.assertRaises(RunPreflightError):
            enqueue_run(
                self.session,
                self.project,
                agent_id="agent-a",
                model="m1",
                role="executor",
                task_key="1.1",
                repository_id=self.repo.id,
                config=config,
                root=self.root,
            )
        self.assertEqual(self.session.query(TaskRun).count(), 0)

    def test_file_et_concurrence(self) -> None:
        first = self._enqueue("1.1")
        second = self._enqueue("1.2")
        self.assertEqual(first.status, "running")
        self.assertEqual(second.status, "queued")
        time.sleep(0.4)
        refresh_run(self.session, first)
        self.session.commit()
        self.assertEqual(first.status, "done")
        dispatch_queue(self.session, self.project, config=self.config, root=self.root)
        self.session.commit()
        self.assertEqual(second.status, "running")
        time.sleep(0.4)
        refresh_run(self.session, second)
        self.session.commit()
        self.assertEqual(second.status, "done")

    def test_timeout_crash_et_annulation(self) -> None:
        timeout_config = {
            "runner": {"max_concurrency": 1},
            "agents": {
                "agent-a": {
                    "enabled": True,
                    "models": {
                        "m1": {
                            "command": [
                                sys.executable,
                                "-c",
                                "import time; time.sleep(2)",
                            ],
                            "timeout_seconds": 1,
                        }
                    },
                }
            },
        }
        run = enqueue_run(
            self.session,
            self.project,
            agent_id="agent-a",
            model="m1",
            role="executor",
            task_key="1.1",
            repository_id=self.repo.id,
            timeout_seconds=0,
            config=timeout_config,
            root=self.root,
        )
        # timeout_seconds=0 utilise la valeur du modèle.
        time.sleep(1.3)
        refresh_run(self.session, run)
        self.session.commit()
        self.assertEqual(run.status, "timeout")
        self.assertTrue(Path(run.log_path).is_file())

        crash_config = {
            "agents": {
                "agent-a": {
                    "enabled": True,
                    "models": {"m1": {"command": [sys.executable, "-c", "raise SystemExit(3)"]}},
                }
            }
        }
        crash = enqueue_run(
            self.session,
            self.project,
            agent_id="agent-a",
            model="m1",
            role="executor",
            task_key="1.2",
            repository_id=self.repo.id,
            config=crash_config,
            root=self.root,
        )
        time.sleep(0.2)
        refresh_run(self.session, crash)
        self.session.commit()
        self.assertEqual(crash.status, "failed")
        self.assertEqual(crash.exit_code, 3)

        first = self._enqueue("1.3")
        queued = self._enqueue("1.4")
        cancel_run(self.session, queued)
        cancel_run(self.session, first)
        self.session.commit()
        self.assertEqual(queued.status, "cancelled")
        self.assertEqual(first.status, "cancelled")

    def test_api_run(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
            config_data=self.config,
            csrf_secret=b"test-secret",
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        token = client.get("/api/csrf").json()["token"]
        response = client.post(
            f"/api/projects/{self.project.id}/runs",
            json={
                "agent_id": "agent-a",
                "model": "m1",
                "role": "executor",
                "task_key": "1.1",
                "repository_id": self.repo.id,
            },
            headers={"X-SDLC-CSRF": token},
        )
        self.assertEqual(response.status_code, 200)
        run_id = response.json()["run"]["run_id"]
        time.sleep(0.4)
        status = client.get(f"/api/runs/{run_id}")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["run"]["status"], "done")


if __name__ == "__main__":
    unittest.main()
