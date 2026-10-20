"""Tests des métriques d'équipe par personne et par dépôt."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import (
    Approval,
    Base,
    Commit,
    MergeRequest,
    Review,
    utc_now,
)
from sdlc_console.services.people import resolve_person
from sdlc_console.services.projects import add_repository, create_project
from sdlc_console.services.team_metrics import build_team_metrics


class TeamMetricsTest(unittest.TestCase):
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
        self.api = self._repo("api", primary=True)
        self.web = self._repo("web", dedup_group="app", mirror=True)
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
        self.bot = resolve_person(
            self.session,
            self.project,
            email="bot@example.com",
            display_name="Dependabot",
        )
        self.bot.is_bot = True
        self._commit(
            self.api,
            "a1",
            self.alice,
            additions=10,
            ai=True,
            fingerprint="fp-alice",
        )
        self._commit(
            self.web,
            "a1",
            self.alice,
            additions=10,
            ai=True,
            fingerprint="fp-alice",
        )
        self._commit(self.web, "b1", self.bob, additions=5, fingerprint="fp-bob")
        self._commit(self.web, "bot1", self.bot, additions=99, fingerprint="fp-bot")
        self.api_mr = self._mr(self.api, 1, self.alice, "Alice MR")
        self.web_mr = self._mr(self.web, 2, self.bob, "Bob MR")
        self.session.add(
            Review(
                mr_id=self.api_mr.id,
                reviewer_person_id=self.bob.id,
                state="approved",
                submitted_at=utc_now(),
                is_agent=False,
            )
        )
        self.session.add(
            Review(
                mr_id=self.web_mr.id,
                reviewer_person_id=self.alice.id,
                state="approved",
                submitted_at=utc_now(),
                is_agent=False,
            )
        )
        self.session.add(
            Approval(
                mr_id=self.api_mr.id,
                actor_person_id=self.bob.id,
                actor_type="human",
                approved_at=utc_now(),
            )
        )
        self.session.commit()

    def _repo(self, name: str, *, primary: bool = False, dedup_group: str | None = None, mirror: bool = False):
        path = self.root / name
        path.mkdir()
        (path / ".git").mkdir()
        return add_repository(
            self.session,
            self.project,
            name=name,
            provider="github",
            url=f"https://github.com/hm/{name}",
            local_path=path,
            is_primary=primary,
            dedup_group=dedup_group,
            is_mirror=mirror,
        )

    def _commit(
        self,
        repository,
        sha: str,
        person,
        *,
        additions: int,
        ai: bool = False,
        fingerprint: str,
    ) -> Commit:
        moment = datetime(2026, 10, 1, 10, 0, tzinfo=utc_now().tzinfo)
        trailers = (
            [{"key": "assisted-by", "value": "Claude"}] if ai else []
        )
        commit = Commit(
            repository_id=repository.id,
            sha=sha,
            person_id=person.id,
            author_name=person.display_name,
            author_email=f"{person.id}@example.com",
            authored_at=moment,
            committed_at=moment + timedelta(minutes=1),
            additions=additions,
            deletions=1,
            files_changed=1,
            is_merge=False,
            is_bot=person.is_bot,
            ai_assisted=ai,
            trailers_json=json.dumps(trailers),
            commit_fingerprint=fingerprint,
            message="message",
        )
        self.session.add(commit)
        self.session.flush()
        return commit

    def _mr(self, repository, number: int, person, title: str) -> MergeRequest:
        mr = MergeRequest(
            repository_id=repository.id,
            number=number,
            title=title,
            author_person_id=person.id,
            state="merged",
            created_at=utc_now(),
            updated_at=utc_now(),
            merged_at=utc_now(),
        )
        self.session.add(mr)
        self.session.flush()
        return mr

    def test_metriques_par_personne_et_depot(self) -> None:
        metrics = build_team_metrics(self.session, self.project)
        self.assertEqual(metrics["totals"]["commits"], 2)
        self.assertEqual(metrics["totals"]["merged_requests"], 2)
        self.assertEqual(metrics["totals"]["reviews"], 2)
        self.assertEqual(metrics["totals"]["approvals"], 1)
        self.assertEqual(metrics["totals"]["persons"], 2)
        self.assertEqual(metrics["totals"]["ai_percent"], 50.0)
        names = {item["person"]["display_name"]: item for item in metrics["persons"]}
        self.assertNotIn("Dependabot", names)
        self.assertEqual(names["Alice"]["commits"], 1)
        self.assertEqual(names["Alice"]["additions"], 10)
        self.assertEqual(names["Alice"]["ai"]["percent"], 100.0)
        self.assertEqual(len(names["Alice"]["repositories"]), 2)
        self.assertEqual(names["Bob"]["commits"], 1)
        self.assertEqual(names["Bob"]["ai"]["status"], "not_measured")

    def test_filtre_par_depot(self) -> None:
        metrics = build_team_metrics(
            self.session,
            self.project,
            repository_ids=[self.web.id],
        )
        self.assertEqual(metrics["totals"]["commits"], 2)
        self.assertEqual(len(metrics["repositories"]), 1)
        self.assertEqual(metrics["repositories"][0]["repository_name"], "web")

    def test_api_team(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/team")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["totals"]["commits"], 2)
        filtered = client.get(
            f"/api/projects/{self.project.id}/team",
            params={"repository_id": self.api.id},
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(len(filtered.json()["repositories"]), 1)
        self.assertEqual(filtered.json()["repositories"][0]["repository_id"], self.api.id)


if __name__ == "__main__":
    unittest.main()
