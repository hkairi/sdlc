"""Tests de l'agrégation multi-dépôts et de la déduplication."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Commit, Repository
from sdlc_console.services.aggregation import DEDUP_BADGE, POTENTIAL_BADGE, aggregate_commits
from sdlc_console.services.ingestion import compute_commit_fingerprint
from sdlc_console.services.people import resolve_person
from sdlc_console.services.projects import (
    add_repository,
    create_project,
    retire_repository,
    set_primary_repository,
)


class AggregationTest(unittest.TestCase):
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

    def _repo(
        self,
        name: str,
        *,
        primary: bool = False,
        dedup_group: str | None = None,
        is_mirror: bool = False,
        is_fork: bool = False,
    ) -> Repository:
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
            is_primary=primary,
            dedup_group=dedup_group,
            is_mirror=is_mirror,
            is_fork=is_fork,
        )
        self.session.commit()
        return repository

    def _commit(
        self,
        repository: Repository,
        sha: str,
        *,
        email: str = "alice@example.com",
        authored_at: datetime = datetime(2026, 1, 1, 12, tzinfo=UTC),
        message: str = "feat: même changement",
        additions: int = 3,
        deletions: int = 1,
        files_changed: int = 2,
        is_merge: bool = False,
        ai_assisted: bool = False,
        fingerprint: str | None = None,
    ) -> Commit:
        person = resolve_person(
            self.session,
            self.project,
            email=email,
            display_name=email.split("@")[0],
        )
        commit = Commit(
            repository_id=repository.id,
            sha=sha,
            person_id=person.id,
            author_name=person.display_name,
            author_email=email,
            authored_at=authored_at,
            committed_at=authored_at,
            additions=additions,
            deletions=deletions,
            files_changed=files_changed,
            is_merge=is_merge,
            is_bot=person.is_bot,
            ai_assisted=ai_assisted,
            trailers_json="[]",
            commit_fingerprint=fingerprint
            or compute_commit_fingerprint(sha, email, authored_at),
            message=message,
        )
        self.session.add(commit)
        self.session.flush()
        return commit

    def test_meme_empreinte_dedupliquee_et_origine(self) -> None:
        primary = self._repo("api", dedup_group="api")
        mirror = self._repo("api-mirror", dedup_group="api", is_mirror=True)
        sha = "a" * 40
        self._commit(primary, sha)
        self._commit(mirror, sha)
        self.session.commit()

        result = aggregate_commits(self.session, self.project)
        self.assertEqual(result.raw_commits, 2)
        self.assertEqual(result.unique_commits, 1)
        self.assertEqual(result.duplicate_commits, 1)
        self.assertTrue(result.dedup_applied)
        self.assertEqual(result.dedup_badge, DEDUP_BADGE)
        self.assertEqual(result.totals.commits, 1)
        self.assertEqual(len(result.deduplicated_commits), 1)
        dedup = result.deduplicated_commits[0]
        self.assertEqual(dedup.origin_repository_name, "api")
        self.assertEqual(dedup.duplicate_repository_names, ("api-mirror",))
        self.assertEqual(dedup.reason, "empreinte")
        self.assertEqual(dedup.dedup_group, "api")
        metrics_by_name = {
            metric.repository_name: metric.metrics.commits
            for metric in result.repository_metrics
        }
        self.assertEqual(metrics_by_name, {"api": 1, "api-mirror": 1})

    def test_dedup_group_avec_sha_different(self) -> None:
        primary = self._repo("api", dedup_group="api")
        fork = self._repo("api-fork", dedup_group="api", is_fork=True)
        self._commit(primary, "b" * 40)
        self._commit(fork, "c" * 40)
        self.session.commit()

        result = aggregate_commits(self.session, self.project)
        self.assertEqual(result.raw_commits, 2)
        self.assertEqual(result.unique_commits, 1)
        self.assertEqual(result.duplicate_commits, 1)
        self.assertTrue(result.dedup_applied)
        self.assertEqual(result.deduplicated_commits[0].reason, "dedup_group")
        self.assertEqual(result.deduplicated_commits[0].origin_repository_name, "api")
        self.assertEqual(result.totals.commits, 1)

    def test_doublon_non_declare_signale_sans_dedup(self) -> None:
        first = self._repo("api")
        second = self._repo("web")
        self._commit(first, "d" * 40)
        self._commit(second, "e" * 40)
        self.session.commit()

        result = aggregate_commits(self.session, self.project)
        self.assertEqual(result.raw_commits, 2)
        self.assertEqual(result.unique_commits, 2)
        self.assertEqual(result.duplicate_commits, 0)
        self.assertFalse(result.dedup_applied)
        self.assertIsNone(result.dedup_badge)
        self.assertEqual(result.potential_badge, POTENTIAL_BADGE)
        self.assertEqual(len(result.potential_duplicates), 1)
        self.assertEqual(set(result.potential_duplicates[0].repository_names), {"api", "web"})
        self.assertEqual(result.totals.commits, 2)

    def test_filtre_par_depot(self) -> None:
        primary = self._repo("api")
        mirror = self._repo("api-mirror", dedup_group="api", is_mirror=True)
        sha = "f" * 40
        self._commit(primary, sha)
        self._commit(mirror, sha)
        self.session.commit()

        result = aggregate_commits(self.session, self.project, repository_ids=[primary.id])
        self.assertEqual(result.raw_commits, 1)
        self.assertEqual(result.unique_commits, 1)
        self.assertFalse(result.dedup_applied)
        self.assertEqual([metric.repository_name for metric in result.repository_metrics], ["api"])

    def test_origine_principale_prioritaire(self) -> None:
        first = self._repo("api")
        second = self._repo("web")
        set_primary_repository(self.session, second)
        self.session.commit()
        sha = "1" * 40
        self._commit(first, sha)
        self._commit(second, sha)
        self.session.commit()

        result = aggregate_commits(self.session, self.project)
        self.assertEqual(result.deduplicated_commits[0].origin_repository_name, "web")
        self.assertEqual(result.deduplicated_commits[0].duplicate_repository_names, ("api",))

    def test_depot_retire_exclu_des_agregats(self) -> None:
        first = self._repo("api")
        second = self._repo("web")
        self._commit(first, "2" * 40)
        self._commit(second, "3" * 40)
        self.session.commit()
        retire_repository(self.session, second)
        self.session.commit()

        result = aggregate_commits(self.session, self.project)
        self.assertEqual([metric.repository_name for metric in result.repository_metrics], ["api"])
        self.assertEqual(result.raw_commits, 1)

        with self.assertRaises(ValueError):
            aggregate_commits(self.session, self.project, repository_ids=[second.id])

    def test_metriques_par_depot(self) -> None:
        primary = self._repo("api")
        other = self._repo("web")
        self._commit(primary, "4" * 40, additions=10, deletions=2, files_changed=4)
        self._commit(
            primary,
            "5" * 40,
            email="dependabot[bot]@users.noreply.github.com",
            additions=1,
            deletions=0,
            files_changed=1,
        )
        self._commit(
            primary,
            "6" * 40,
            additions=3,
            deletions=1,
            files_changed=2,
            is_merge=True,
            ai_assisted=True,
        )
        self._commit(other, "7" * 40, additions=2, deletions=2, files_changed=1)
        self.session.commit()

        result = aggregate_commits(self.session, self.project)
        metrics = {metric.repository_name: metric.metrics for metric in result.repository_metrics}
        self.assertEqual(metrics["api"].commits, 3)
        self.assertEqual(metrics["api"].bot_commits, 1)
        self.assertEqual(metrics["api"].human_commits, 2)
        self.assertEqual(metrics["api"].merge_commits, 1)
        self.assertEqual(metrics["api"].ai_assisted_commits, 1)
        self.assertEqual(metrics["api"].additions, 14)
        self.assertEqual(metrics["api"].deletions, 3)
        self.assertEqual(metrics["api"].files_changed, 7)
        self.assertEqual(result.totals.commits, 4)
        self.assertEqual(result.totals.bot_commits, 1)
        self.assertEqual(result.totals.merge_commits, 1)
        self.assertEqual(result.totals.ai_assisted_commits, 1)

    def test_meme_contenu_dans_un_seul_depot_non_dedup(self) -> None:
        repository = self._repo("api", dedup_group="api")
        self._commit(repository, "8" * 40)
        self._commit(repository, "9" * 40)
        self.session.commit()

        result = aggregate_commits(self.session, self.project)
        self.assertEqual(result.raw_commits, 2)
        self.assertEqual(result.unique_commits, 2)
        self.assertFalse(result.dedup_applied)

    def test_aucun_commit(self) -> None:
        result = aggregate_commits(self.session, self.project)
        self.assertEqual(result.totals.commits, 0)
        self.assertEqual(result.repository_metrics, ())
        self.assertFalse(result.dedup_applied)


if __name__ == "__main__":
    unittest.main()
