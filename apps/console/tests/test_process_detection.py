"""Tests de détection des profils de processus Git."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.process_detection import ProcessSignals, detect_process
from sdlc_console.services.projects import add_repository, create_project


class ProcessDetectionTest(unittest.TestCase):
    def test_github_flow_avec_releases(self) -> None:
        detection = detect_process(
            ProcessSignals(
                branches=("main",),
                tags=("v1.0.0", "v1.1.0"),
                merge_strategy={"squash": 8, "merge": 2},
                ci_files=(".github/workflows/ci.yml",),
            )
        )
        self.assertEqual(detection.key, "github_flow")
        self.assertEqual(detection.label, "GitHub Flow + releases")
        self.assertTrue(detection.detected)
        self.assertGreaterEqual(detection.confidence, 0.7)
        self.assertIn("tags_semver", {signal["kind"] for signal in detection.signals})

    def test_git_flow(self) -> None:
        detection = detect_process(
            ProcessSignals(
                branches=("main", "develop", "release/1.0", "hotfix/urgent"),
                merge_commits=30,
                total_commits=100,
            )
        )
        self.assertEqual(detection.key, "git_flow")
        self.assertEqual(detection.label, "Git Flow")
        self.assertTrue(detection.detected)

    def test_trunk_based(self) -> None:
        detection = detect_process(
            ProcessSignals(
                branches=("main", "feature/courte"),
                protected_branches=("main",),
                ci_files=(".github/workflows/ci.yml",),
            )
        )
        self.assertEqual(detection.key, "trunk_based")
        self.assertTrue(detection.detected)

    def test_gitlab_flow(self) -> None:
        detection = detect_process(
            ProcessSignals(
                branches=("main", "staging", "production"),
                ci_files=(".gitlab-ci.yml",),
            )
        )
        self.assertEqual(detection.key, "gitlab_flow")
        self.assertEqual(detection.label, "GitLab Flow")

    def test_non_identifiable(self) -> None:
        detection = detect_process(ProcessSignals())
        self.assertEqual(detection.key, "unknown")
        self.assertFalse(detection.detected)
        self.assertGreater(len(detection.reasons), 0)
        self.assertEqual(detection.confidence, 0.0)

    def test_api_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = make_engine(f"sqlite:///{root / 'db.sqlite3'}")
            Base.metadata.create_all(engine)
            Session = make_session_factory(engine)
            with Session() as session:
                project = create_project(session, name="Atlas", slug="atlas")
                repo_path = root / "repo"
                repo_path.mkdir()
                (repo_path / ".git").mkdir()
                add_repository(
                    session,
                    project,
                    name="api",
                    provider="github",
                    url="https://github.com/hm/api",
                    local_path=repo_path,
                )
                session.commit()
                app = create_app(
                    allowed_hosts={"127.0.0.2"},
                    session_factory=Session,
                    docs_dir=root / "docs",
                    project_root=root,
                    watcher_enabled=False,
                )
                client = TestClient(app, base_url="http://127.0.0.2")
                response = client.get(f"/api/projects/{project.id}/process")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["total"], 1)
                self.assertEqual(response.json()["repositories"][0]["profile"], "unknown")
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
