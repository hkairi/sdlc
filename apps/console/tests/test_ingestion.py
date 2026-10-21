"""Tests de l'ingestion Git incrémentale et idempotente."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Commit, IngestionRun
from sdlc_console.services.ingestion import (
    GitIngestionError,
    compute_commit_fingerprint,
    detect_ai_assisted,
    ingest_repository,
    last_ingestion,
    last_project_ingestion,
    parse_trailers,
)
from sdlc_console.services.people import list_team_persons
from sdlc_console.services.projects import add_repository, create_project


class GitIngestionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.engine = make_engine(f"sqlite:///{root / 'db.sqlite3'}")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.Session = make_session_factory(self.engine)
        self.session = self.Session()
        self.addCleanup(self.session.close)
        self.project = create_project(self.session, name="Atlas", slug="atlas")
        self.session.commit()

        self.repo_path = root / "repo"
        self.repo_path.mkdir()
        self._git("init", "-b", "main")
        self._git("config", "user.name", "Test")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "commit.gpgsign", "false")
        self.repo = add_repository(
            self.session,
            self.project,
            name="repo",
            provider="github",
            url="https://github.com/hm/repo",
            local_path=self.repo_path,
        )
        self.session.commit()

    def _git(
        self,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def _commit(
        self,
        filename: str,
        content: str,
        message: str,
        *,
        name: str = "Alice",
        email: str = "alice@example.com",
        date: str = "2026-01-01T12:00:00+00:00",
    ) -> str:
        path = self.repo_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self._git("add", filename)
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_DATE": date,
        }
        self._git("commit", "-m", message, env=env)
        return self._git("rev-parse", "HEAD").stdout.strip()

    def test_ingestion_de_base_et_idempotence(self) -> None:
        first_sha = self._commit(
            "app.py",
            "print('hello')\n",
            "feat: initial\n\nAssisted-by: Claude <noreply@anthropic.com>",
        )
        self._commit(
            "app.py",
            "print('hello')\nprint('world')\n",
            "fix: correction",
            name="Bob",
            email="bob@example.com",
            date="2026-01-02T12:00:00+00:00",
        )

        run = ingest_repository(self.session, self.repo, full=True)
        self.session.commit()
        self.assertEqual(run.status, "done")
        stats = json.loads(run.stats_json)
        self.assertEqual(stats["inserted"], 2)
        self.assertEqual(stats["total"], 2)
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(last_ingestion(self.session, self.repo).id, run.id)
        self.assertEqual(last_project_ingestion(self.session, self.project).id, run.id)

        commits = self.session.scalars(select(Commit).order_by(Commit.authored_at)).all()
        self.assertEqual(len(commits), 2)
        first = next(commit for commit in commits if commit.sha == first_sha)
        self.assertEqual(first.person.display_name, "Alice")
        self.assertTrue(first.ai_assisted)
        trailers = json.loads(first.trailers_json)
        self.assertEqual(trailers[0]["key"], "assisted-by")
        self.assertIn("Claude", trailers[0]["value"])
        self.assertEqual(first.additions, 1)
        self.assertEqual(first.deletions, 0)
        self.assertEqual(first.files_changed, 1)
        self.assertEqual(json.loads(first.files_json), ["app.py"])
        self.assertFalse(first.is_merge)
        self.assertFalse(first.is_bot)

        second = commits[1]
        self.assertEqual(second.person.display_name, "Bob")
        self.assertFalse(second.ai_assisted)
        self.assertEqual(json.loads(second.trailers_json), [])

        rerun = ingest_repository(self.session, self.repo, full=True)
        self.session.commit()
        rerun_stats = json.loads(rerun.stats_json)
        self.assertEqual(rerun_stats["inserted"], 0)
        self.assertEqual(rerun_stats["skipped"], 2)
        self.assertEqual(rerun_stats["total"], 2)
        self.assertEqual(
            len(self.session.scalars(select(Commit)).all()),
            2,
        )

    def test_fingerprint_normatif(self) -> None:
        sha = self._commit(
            "f.txt",
            "x\n",
            "feat: fingerprint",
            email="Alice@Example.com",
            date="2026-01-01T12:00:00+02:00",
        )
        ingest_repository(self.session, self.repo, full=True)
        self.session.commit()
        commit = self.session.scalars(select(Commit).where(Commit.sha == sha)).one()
        self.assertEqual(commit.author_email, "alice@example.com")
        expected = hashlib.sha256(
            f"{sha}\nalice@example.com\n2026-01-01T10:00:00+00:00".encode()
        ).hexdigest()
        self.assertEqual(commit.commit_fingerprint, expected)
        self.assertEqual(
            compute_commit_fingerprint(sha, "ALICE@example.com", commit.authored_at),
            expected,
        )

    def test_trailers_ia(self) -> None:
        trailers = parse_trailers(
            "feat: chose\n\nAssisted-by: Claude <noreply@anthropic.com>\n"
            "Co-authored-by: Alice <alice@example.com>"
        )
        self.assertTrue(detect_ai_assisted(trailers))
        self.assertFalse(
            detect_ai_assisted(parse_trailers("Co-authored-by: Alice <alice@example.com>"))
        )
        self.assertFalse(detect_ai_assisted(parse_trailers("aucun trailer")))
        self.assertTrue(detect_ai_assisted(parse_trailers("Co-authored-by: GitHub Copilot")))
        self.assertTrue(detect_ai_assisted(parse_trailers("Assisted-by: ChatGPT")))
        self.assertFalse(detect_ai_assisted(parse_trailers("Co-authored-by: dependabot[bot]")))

    def test_commit_bot(self) -> None:
        self._commit(
            "bot.txt",
            "bot\n",
            "chore: dependabot",
            name="dependabot[bot]",
            email="dependabot[bot]@users.noreply.github.com",
        )
        ingest_repository(self.session, self.repo, full=True)
        self.session.commit()
        commit = self.session.scalars(select(Commit)).one()
        self.assertTrue(commit.is_bot)
        self.assertTrue(commit.person.is_bot)
        self.assertEqual(list_team_persons(self.session, self.project), [])

    def test_merge_commit(self) -> None:
        self._commit("base.txt", "base\n", "feat: base")
        self._git("checkout", "-b", "feature")
        self._commit(
            "feature.txt",
            "feature\n",
            "feat: feature",
            name="Bob",
            email="bob@example.com",
            date="2026-01-02T12:00:00+00:00",
        )
        self._git("checkout", "main")
        self._commit(
            "main.txt",
            "main\n",
            "feat: main",
            name="Carol",
            email="carol@example.com",
            date="2026-01-03T12:00:00+00:00",
        )
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Alice",
            "GIT_AUTHOR_EMAIL": "alice@example.com",
            "GIT_COMMITTER_NAME": "Alice",
            "GIT_COMMITTER_EMAIL": "alice@example.com",
            "GIT_AUTHOR_DATE": "2026-01-04T12:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-01-04T12:00:00+00:00",
        }
        self._git("merge", "--no-ff", "feature", "-m", "merge feature", env=env)
        merge_sha = self._git("rev-parse", "HEAD").stdout.strip()

        ingest_repository(self.session, self.repo, full=True)
        self.session.commit()
        merge = self.session.scalars(select(Commit).where(Commit.sha == merge_sha)).one()
        self.assertTrue(merge.is_merge)
        self.assertEqual(merge.person.display_name, "Alice")

    def test_ingestion_incrementale(self) -> None:
        self._commit(
            "one.txt",
            "one\n",
            "feat: un",
            date="2026-01-01T12:00:00+00:00",
        )
        first = ingest_repository(self.session, self.repo, full=True)
        self.session.commit()
        self.assertEqual(json.loads(first.stats_json)["inserted"], 1)

        self._commit(
            "two.txt",
            "two\n",
            "feat: deux",
            date="2026-02-01T12:00:00+00:00",
        )
        second = ingest_repository(
            self.session,
            self.repo,
            since=datetime(2026, 1, 15, tzinfo=UTC),
        )
        self.session.commit()
        stats = json.loads(second.stats_json)
        self.assertEqual(stats["scanned"], 1)
        self.assertEqual(stats["inserted"], 1)
        self.assertEqual(stats["total"], 2)

    def test_depot_non_git_echoue_et_trace(self) -> None:
        shutil.rmtree(self.repo_path / ".git")
        with self.assertRaises(GitIngestionError):
            ingest_repository(self.session, self.repo, full=True)
        self.session.commit()
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertEqual(run.status, "failed")
        self.assertIsNotNone(run.finished_at)
        self.assertIn("Git", run.error or "")

    def test_depot_retire_refuse(self) -> None:
        self.repo.retired_at = datetime.now(UTC)
        self.session.commit()
        with self.assertRaises(GitIngestionError):
            ingest_repository(self.session, self.repo, full=True)


if __name__ == "__main__":
    unittest.main()
