"""Tests du bac à sable agent : environnement purgé et Git en lecture seule."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

from sqlalchemy import select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import AuditEvent, Base
from sdlc_console.services.agent_runner import enqueue_run, refresh_run
from sdlc_console.services.agent_sandbox import (
    install_git_guard,
    sanitized_environment,
)
from sdlc_console.services.projects import add_repository, create_project


class AgentSandboxTest(unittest.TestCase):
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
        self.repo_path = self.root / "repo"
        self.repo_path.mkdir()
        (self.repo_path / ".git").mkdir()
        self.repo = add_repository(
            self.session,
            self.project,
            name="repo",
            provider="github",
            url="https://github.com/hm/repo",
            local_path=self.repo_path,
        )
        self.session.commit()

    def test_environnement_sans_jetons(self) -> None:
        clean = sanitized_environment(
            {
                "PATH": "/usr/bin",
                "HOME": "/tmp/home",
                "GITHUB_TOKEN": "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
                "GITLAB_TOKEN": "glpat-abcdefghijklmnopqrstuvwxyz",
                "MY_PASSWORD": "secret",
                "APP_SECRET": "secret",
                "NORMAL": "visible",
            }
        )
        self.assertNotIn("GITHUB_TOKEN", clean)
        self.assertNotIn("GITLAB_TOKEN", clean)
        self.assertNotIn("MY_PASSWORD", clean)
        self.assertNotIn("APP_SECRET", clean)
        self.assertEqual(clean["PATH"], "/usr/bin")
        self.assertEqual(clean["NORMAL"], "visible")

    def test_processus_ne_voit_pas_le_jeton(self) -> None:
        os.environ["GITHUB_TOKEN"] = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        self.addCleanup(os.environ.pop, "GITHUB_TOKEN", None)
        config = {
            "agents": {
                "a": {
                    "enabled": True,
                    "models": {
                        "m": {
                            "command": [
                                sys.executable,
                                "-c",
                                "import os; print(os.getenv('GITHUB_TOKEN', 'absent'))",
                            ]
                        }
                    },
                }
            }
        }
        run = enqueue_run(
            self.session,
            self.project,
            agent_id="a",
            model="m",
            role="reviewer",
            task_key="6.8",
            repository_id=self.repo.id,
            config=config,
            root=self.root,
        )
        time.sleep(0.25)
        refresh_run(self.session, run)
        self.session.commit()
        log = Path(run.log_path or "").read_text(encoding="utf-8")
        self.assertNotIn("ghp_", log)
        self.assertIn("absent", log)

    @unittest.skipIf(shutil.which("git") is None, "git absent")
    def test_ecriture_git_refusee_et_auditee(self) -> None:
        git = shutil.which("git")
        assert git is not None
        config = {
            "agents": {
                "a": {
                    "enabled": True,
                    "models": {"m": {"command": [git, "commit", "-m", "x"]}},
                }
            }
        }
        run = enqueue_run(
            self.session,
            self.project,
            agent_id="a",
            model="m",
            role="reviewer",
            task_key="6.8",
            repository_id=self.repo.id,
            config=config,
            root=self.root,
        )
        for _ in range(100):
            time.sleep(0.05)
            refresh_run(self.session, run)
            if run.status != "running":
                break
        self.session.commit()
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.exit_code, 126)
        audit_path = self.root / "reports" / "runs" / f"{run.run_id}-git" / "refusals.jsonl"
        events = self.session.scalars(
            select(AuditEvent).where(AuditEvent.action == "agent.git_write_refused")
        ).all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].object_id, run.run_id)
        self.assertIn("commit", events[0].payload_json)
        self.assertEqual(audit_path.read_text(encoding="utf-8"), "")

    def test_garde_git_installee_en_lecture_seule(self) -> None:
        env, audit_path, guard = install_git_guard(
            self.root,
            "run-test",
            base_env={"PATH": "/usr/bin", "GITHUB_TOKEN": "secret"},
            read_only=True,
        )
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertEqual(env["SDLC_READ_ONLY"], "1")
        self.assertTrue(audit_path.is_file())
        if guard is not None:
            self.assertTrue(guard.is_file())


if __name__ == "__main__":
    unittest.main()
