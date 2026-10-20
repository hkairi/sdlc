"""Tests des fixtures hors réseau GitHub/GitLab/CI et des échecs fournisseur."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sqlalchemy import select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Approval, Base, IngestionRun, MergeRequest, Review
from sdlc_console.services.projects import add_repository, create_project
from sdlc_console.services.providers.http import (
    HttpResponse,
    ProviderAuthError,
    ProviderQuotaError,
    ProviderUnavailableError,
)
from sdlc_console.services.providers.ingest import (
    collect_repository,
    github_from_file,
    gitlab_from_file,
)

FIXTURES = Path(__file__).parent / "fixtures" / "providers"


class ExplodingClient:
    """Client qui échoue si un test en mode fichier tente un appel réseau."""

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        raise AssertionError(f"appel réseau interdit : {url}")


class UnavailableClient:
    """Client qui simule une coupure réseau."""

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        raise ProviderUnavailableError("réseau coupé")


class FixtureErrorClient:
    """Client qui rejoue une réponse d'erreur enregistrée dans une fixture."""

    def __init__(self, fixture: Path) -> None:
        self.payload: dict[str, Any] = json.loads(fixture.read_text(encoding="utf-8"))
        self.calls = 0

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.calls += 1
        return HttpResponse(
            status=int(self.payload["status"]),
            headers={
                str(key): str(value)
                for key, value in self.payload.get("headers", {}).items()
            },
            json=self.payload.get("json"),
            text=json.dumps(self.payload.get("json", {}), ensure_ascii=False),
        )


class ProviderFixturesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        previous_cache = os.environ.get("SDLC_PROVIDER_CACHE")
        os.environ["SDLC_PROVIDER_CACHE"] = str(self.root / "provider-cache.json")
        self.addCleanup(self._restore_cache, previous_cache)
        self.engine = make_engine(f"sqlite:///{self.root / 'db.sqlite3'}")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.Session = make_session_factory(self.engine)
        self.session = self.Session()
        self.addCleanup(self.session.close)
        self.project = create_project(self.session, name="Atlas", slug="atlas")
        self.session.commit()

        github_path = self.root / "github"
        github_path.mkdir()
        (github_path / ".git").mkdir()
        gitlab_path = self.root / "gitlab"
        gitlab_path.mkdir()
        (gitlab_path / ".git").mkdir()
        self.github = add_repository(
            self.session,
            self.project,
            name="github",
            provider="github",
            url="https://github.com/hm/atlas",
            local_path=github_path,
        )
        self.gitlab = add_repository(
            self.session,
            self.project,
            name="gitlab",
            provider="gitlab",
            url="https://gitlab.com/hm/atlas",
            local_path=gitlab_path,
        )
        self.session.commit()

    @staticmethod
    def _restore_cache(previous: str | None) -> None:
        if previous is None:
            os.environ.pop("SDLC_PROVIDER_CACHE", None)
        else:
            os.environ["SDLC_PROVIDER_CACHE"] = previous

    def test_fixture_github_mode_fichier(self) -> None:
        items = github_from_file(FIXTURES / "github_pulls.json")
        self.assertEqual(len(items), 3)
        by_number = {item.number: item for item in items}
        self.assertEqual(by_number[101].state, "open")
        self.assertEqual(by_number[102].state, "merged")
        self.assertEqual(by_number[103].state, "draft")
        self.assertEqual(len(by_number[101].reviews), 2)
        self.assertEqual(len(by_number[101].approvals), 1)
        self.assertEqual(len(by_number[102].approvals), 1)

        run = collect_repository(
            self.session,
            self.github,
            mode="file",
            file_path=FIXTURES / "github_pulls.json",
            client=ExplodingClient(),
        )
        self.session.commit()
        self.assertEqual(run.status, "done")
        self.assertEqual(len(self.session.scalars(select(MergeRequest)).all()), 3)
        self.assertEqual(len(self.session.scalars(select(Review)).all()), 3)
        self.assertEqual(len(self.session.scalars(select(Approval)).all()), 2)

    def test_fixture_gitlab_mode_fichier(self) -> None:
        items = gitlab_from_file(FIXTURES / "gitlab_merge_requests.json")
        self.assertEqual(len(items), 2)
        by_number = {item.number: item for item in items}
        self.assertEqual(by_number[201].state, "merged")
        self.assertEqual(by_number[201].merge_strategy, "squash")
        self.assertEqual(len(by_number[201].approvals), 2)
        self.assertEqual(by_number[202].state, "draft")
        self.assertEqual(by_number[202].approvals, ())

        run = collect_repository(
            self.session,
            self.gitlab,
            mode="file",
            file_path=FIXTURES / "gitlab_merge_requests.json",
            client=ExplodingClient(),
        )
        self.session.commit()
        self.assertEqual(run.status, "done")
        self.assertEqual(len(self.session.scalars(select(MergeRequest)).all()), 2)
        self.assertEqual(len(self.session.scalars(select(Review)).all()), 2)
        self.assertEqual(len(self.session.scalars(select(Approval)).all()), 2)

    def test_fixtures_ci_sans_reseau(self) -> None:
        checks = json.loads((FIXTURES / "github_checks.json").read_text(encoding="utf-8"))
        pipelines = json.loads((FIXTURES / "gitlab_pipelines.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {check["conclusion"] for check in checks["check_runs"]},
            {"success", "failure"},
        )
        self.assertEqual(
            {pipeline["status"] for pipeline in pipelines["pipelines"]},
            {"success", "failed"},
        )
        self.assertTrue(all("sha" in pipeline for pipeline in pipelines["pipelines"]))

    def test_echec_reseau_trace(self) -> None:
        with self.assertRaises(ProviderUnavailableError):
            collect_repository(self.session, self.github, client=UnavailableClient())
        self.session.commit()
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertEqual(run.status, "failed")
        self.assertIn("réseau", (run.error or "").lower())
        self.assertEqual(self.session.scalars(select(MergeRequest)).all(), [])

    def test_echec_quota_depuis_fixture(self) -> None:
        client = FixtureErrorClient(FIXTURES / "github_quota.json")
        with self.assertRaises(ProviderQuotaError):
            collect_repository(
                self.session,
                self.github,
                client=client,
                sleep=lambda _: None,
            )
        self.session.commit()
        self.assertEqual(client.calls, 3)
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertEqual(run.status, "failed")
        self.assertEqual(self.session.scalars(select(MergeRequest)).all(), [])

    def test_echec_jeton_depuis_fixture(self) -> None:
        client = FixtureErrorClient(FIXTURES / "github_unauthorized.json")
        with self.assertRaises(ProviderAuthError):
            collect_repository(self.session, self.github, client=client)
        self.session.commit()
        self.assertEqual(client.calls, 1)
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertEqual(run.status, "failed")


if __name__ == "__main__":
    unittest.main()
