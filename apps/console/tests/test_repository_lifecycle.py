"""Tests du retrait, de la suppression cascadée et de l'audit des dépôts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import (
    Approval,
    AuditEvent,
    Base,
    Commit,
    IngestionRun,
    MergeRequest,
    Repository,
    Review,
    utc_now,
)
from sdlc_console.services.ingestion import compute_commit_fingerprint
from sdlc_console.services.people import resolve_person
from sdlc_console.services.projects import (
    RepositoryError,
    add_repository,
    create_project,
    delete_repository,
    get_primary_repository,
    list_repositories,
    retire_repository,
)


class RepositoryLifecycleTest(unittest.TestCase):
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
        self.session.commit()

    def _repo(self, name: str) -> Repository:
        path = self.root / name
        path.mkdir()
        (path / ".git").mkdir()
        repository = add_repository(
            self.session,
            self.project,
            name=name,
            provider="github",
            url=f"https://github.com/hm/{name}",
            local_path=path,
        )
        self.session.commit()
        return repository

    def _seed_repository_data(self, repository: Repository) -> None:
        person = resolve_person(
            self.session,
            self.project,
            email="alice@example.com",
            display_name="Alice",
        )
        sha = "a" * 40
        now = utc_now()
        self.session.add(
            Commit(
                repository_id=repository.id,
                sha=sha,
                person_id=person.id,
                author_name="Alice",
                author_email="alice@example.com",
                authored_at=now,
                committed_at=now,
                additions=1,
                deletions=0,
                files_changed=1,
                is_merge=False,
                is_bot=False,
                ai_assisted=False,
                trailers_json="[]",
                commit_fingerprint=compute_commit_fingerprint(
                    sha,
                    "alice@example.com",
                    now,
                ),
                message="feat: seed",
            )
        )
        mr = MergeRequest(
            repository_id=repository.id,
            number=1,
            title="feat: seed",
            author_person_id=person.id,
            state="open",
            imported_at=utc_now(),
        )
        self.session.add(mr)
        self.session.flush()
        self.session.add(
            Review(
                mr_id=mr.id,
                reviewer_person_id=person.id,
                state="approved",
                external_id="review:1",
                imported_at=utc_now(),
            )
        )
        self.session.add(
            Approval(
                mr_id=mr.id,
                actor_person_id=person.id,
                actor_type="human",
                external_id="approval:1",
                imported_at=utc_now(),
            )
        )
        self.session.add(
            IngestionRun(
                project_id=self.project.id,
                repository_id=repository.id,
                source="git",
                status="done",
                started_at=utc_now(),
                finished_at=utc_now(),
            )
        )
        self.session.commit()

    def test_retrait_audite_et_historique_conserve(self) -> None:
        first = self._repo("api")
        second = self._repo("web")
        self._seed_repository_data(first)
        retire_repository(self.session, first, reason="fin de vie")
        self.session.commit()

        self.assertIsNotNone(first.retired_at)
        self.assertFalse(first.is_primary)
        self.assertTrue(second.is_primary)
        self.assertEqual([repo.name for repo in list_repositories(self.session, self.project)], ["web"])
        self.assertEqual(
            [repo.name for repo in list_repositories(self.session, self.project, include_retired=True)],
            ["api", "web"],
        )
        self.assertEqual(self.session.scalar(select(func.count(Commit.id))), 1)
        self.assertEqual(self.session.scalar(select(func.count(MergeRequest.id))), 1)

        event = self.session.scalars(select(AuditEvent)).one()
        self.assertEqual(event.action, "repository.retire")
        self.assertEqual(event.object_id, str(first.id))
        self.assertIn('"reason":"fin de vie"', event.payload_json)
        self.assertIn('"was_primary":true', event.payload_json)
        self.assertIn(f'"new_primary_repository_id":{second.id}', event.payload_json)

    def test_suppression_cascadee_auditee_et_reelue(self) -> None:
        first = self._repo("api")
        second = self._repo("web")
        self._seed_repository_data(first)
        delete_repository(self.session, first, confirm=True, reason="doublon")
        self.session.commit()

        self.assertIsNone(self.session.scalar(select(Repository).where(Repository.id == first.id)))
        self.assertTrue(second.is_primary)
        self.assertEqual(self.session.scalar(select(func.count(Commit.id))), 0)
        self.assertEqual(self.session.scalar(select(func.count(MergeRequest.id))), 0)
        self.assertEqual(self.session.scalar(select(func.count(Review.id))), 0)
        self.assertEqual(self.session.scalar(select(func.count(Approval.id))), 0)
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertIsNone(run.repository_id)

        event = self.session.scalars(select(AuditEvent)).one()
        self.assertEqual(event.action, "repository.delete")
        self.assertEqual(event.object_id, str(first.id))
        self.assertIn('"reason":"doublon"', event.payload_json)
        self.assertIn(f'"new_primary_repository_id":{second.id}', event.payload_json)

    def test_suppression_sans_confirmation_refusee(self) -> None:
        first = self._repo("api")
        self._repo("web")
        with self.assertRaises(RepositoryError):
            delete_repository(self.session, first)
        self.session.commit()
        self.assertIsNotNone(self.session.scalar(select(Repository).where(Repository.id == first.id)))
        self.assertEqual(len(self.session.scalars(select(AuditEvent)).all()), 0)

    def test_suppression_dernier_depot_refusee(self) -> None:
        first = self._repo("api")
        with self.assertRaises(RepositoryError):
            delete_repository(self.session, first, confirm=True)
        self.session.commit()
        self.assertIsNotNone(self.session.scalar(select(Repository).where(Repository.id == first.id)))

    def test_suppression_depot_retire_auditee_et_chaine(self) -> None:
        first = self._repo("api")
        second = self._repo("web")
        third = self._repo("docs")
        retire_repository(self.session, first, reason="archive")
        self.session.commit()
        delete_repository(self.session, second, confirm=True, reason="suppression")
        self.session.commit()

        events = self.session.scalars(select(AuditEvent).order_by(AuditEvent.id)).all()
        self.assertEqual([event.action for event in events], ["repository.retire", "repository.delete"])
        self.assertEqual(events[1].prev_hash, events[0].hash)
        self.assertEqual(get_primary_repository(self.session, self.project).id, third.id)


if __name__ == "__main__":
    unittest.main()
