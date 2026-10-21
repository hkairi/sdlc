"""Tests de la chaîne de validation auteur → agent → humain."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import (
    Approval,
    Base,
    MergeRequest,
    Review,
    utc_now,
)
from sdlc_console.services.people import resolve_person
from sdlc_console.services.projects import add_repository, create_project
from sdlc_console.services.validation_chain import build_validation_chain


class ValidationChainTest(unittest.TestCase):
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
        repo_path = self.root / "api"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()
        self.repo = add_repository(
            self.session,
            self.project,
            name="api",
            provider="github",
            url="https://github.com/hm/api",
            local_path=repo_path,
        )
        self.alice = resolve_person(
            self.session,
            self.project,
            email="alice@example.com",
            display_name="Alice",
        )
        self.bob = resolve_person(
            self.session,
            self.project,
            email="bob@example.com",
            display_name="Bob",
        )
        self.carol = resolve_person(
            self.session,
            self.project,
            email="carol@example.com",
            display_name="Carol",
        )
        self.complete = self._mr(1, self.alice)
        self.agent_only = self._mr(2, self.bob)
        self.pending = self._mr(3, self.carol)
        self.session.add(
            Review(
                mr_id=self.complete.id,
                reviewer_agent_id="reviewer-agent",
                state="approved",
                submitted_at=utc_now(),
                is_agent=True,
            )
        )
        self.session.add(
            Approval(
                mr_id=self.complete.id,
                actor_person_id=self.bob.id,
                actor_type="human",
                approved_at=utc_now(),
            )
        )
        self.session.add(
            Review(
                mr_id=self.agent_only.id,
                reviewer_agent_id="reviewer-agent",
                state="approved",
                submitted_at=utc_now(),
                is_agent=True,
            )
        )
        self.session.commit()

    def _mr(self, number: int, author) -> MergeRequest:
        mr = MergeRequest(
            repository_id=self.repo.id,
            number=number,
            title=f"MR {number}",
            author_person_id=author.id,
            state="open",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.session.add(mr)
        self.session.flush()
        return mr

    def test_taux_et_chaines(self) -> None:
        result = build_validation_chain(self.session, self.project)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["agent_reviewed"], 2)
        self.assertEqual(result["human_approved"], 1)
        self.assertEqual(result["complete"], 1)
        self.assertEqual(result["agent_review_rate"], 66.67)
        self.assertEqual(result["human_approval_rate"], 33.33)
        self.assertEqual(result["complete_rate"], 33.33)
        complete = next(chain for chain in result["chains"] if chain["mr_id"] == self.complete.id)
        self.assertEqual(complete["status"], "complete")
        self.assertEqual(
            [step["status"] for step in complete["chain"]],
            ["done", "done", "done"],
        )
        pending = next(chain for chain in result["chains"] if chain["mr_id"] == self.pending.id)
        self.assertEqual(
            [step["status"] for step in pending["chain"]],
            ["done", "pending", "pending"],
        )
        self.assertEqual(result["repositories"][0]["human_approval_rate"], 33.33)

    def test_api_team_contient_validation(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        team = client.get(f"/api/projects/{self.project.id}/team")
        self.assertEqual(team.status_code, 200)
        self.assertEqual(team.json()["validation"]["total"], 3)
        validation = client.get(
            f"/api/projects/{self.project.id}/team/validation"
        )
        self.assertEqual(validation.status_code, 200)
        self.assertEqual(validation.json()["agent_reviewed"], 2)
        filtered = client.get(
            f"/api/projects/{self.project.id}/team/validation",
            params={"repository_id": "all"},
        )
        self.assertEqual(filtered.status_code, 200)

    def test_sans_mr_non_mesure(self) -> None:
        other = create_project(self.session, name="Empty", slug="empty")
        self.session.commit()
        result = build_validation_chain(self.session, other)
        self.assertEqual(result["status"], "not_measured")
        self.assertIsNone(result["agent_review_rate"])


if __name__ == "__main__":
    unittest.main()
