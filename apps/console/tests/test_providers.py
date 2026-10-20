"""Tests des collecteurs GitHub/GitLab, ETag, pagination, backoff et mode fichier."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Approval, Base, IngestionRun, MergeRequest, Review
from sdlc_console.services.projects import add_repository, create_project
from sdlc_console.services.providers.http import (
    HttpResponse,
    JsonETagCache,
    ProviderAuthError,
    ProviderError,
    ProviderQuotaError,
)
from sdlc_console.services.providers.ingest import (
    collect_repository,
    github_from_file,
    gitlab_from_file,
)


class CallbackClient:
    """Client HTTP piloté par une fonction de test."""

    def __init__(self, callback: Callable[[str, Mapping[str, str]], HttpResponse]) -> None:
        self.callback = callback
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.calls.append((url, dict(headers)))
        return self.callback(url, headers)


def json_response(payload: Any, *, status: int = 200, headers: Mapping[str, str] | None = None) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers=headers or {},
        json=payload,
        text=json.dumps(payload, ensure_ascii=False),
    )


def github_pr(number: int = 12) -> dict[str, Any]:
    return {
        "number": number,
        "title": "feat: ajouter le collecteur",
        "user": {"login": "alice", "email": "alice@example.com"},
        "state": "open",
        "draft": False,
        "created_at": "2026-01-01T10:00:00Z",
        "updated_at": "2026-01-03T10:00:00Z",
        "merged_at": None,
        "base": {"ref": "main"},
        "head": {"ref": "feat/collector"},
        "additions": 10,
        "deletions": 2,
        "html_url": "https://github.com/hm/atlas/pull/12",
    }


def github_reviews() -> list[dict[str, Any]]:
    return [
        {
            "id": 100,
            "user": {"login": "bob", "name": "Bob"},
            "state": "APPROVED",
            "submitted_at": "2026-01-02T10:00:00Z",
        },
        {
            "id": 101,
            "user": {"login": "carol", "name": "Carol"},
            "state": "CHANGES_REQUESTED",
            "submitted_at": "2026-01-02T11:00:00Z",
        },
    ]


def gitlab_mr(iid: int = 7) -> dict[str, Any]:
    return {
        "iid": iid,
        "title": "feat: collecteur GitLab",
        "author": {"username": "bob", "name": "Bob"},
        "state": "merged",
        "created_at": "2026-01-01T10:00:00Z",
        "updated_at": "2026-01-03T10:00:00Z",
        "merged_at": "2026-01-03T09:00:00Z",
        "target_branch": "main",
        "source_branch": "feat/gitlab",
        "squash": True,
        "web_url": "https://gitlab.com/hm/atlas/-/merge_requests/7",
    }


class ProvidersTest(unittest.TestCase):
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

    def test_github_normalisation_et_idempotence(self) -> None:
        def callback(url: str, headers: Mapping[str, str]) -> HttpResponse:
            if "/pulls/12/reviews?" in url:
                return json_response(github_reviews())
            if "/pulls?" in url:
                return json_response([github_pr()])
            raise AssertionError(f"URL inattendue : {url}")

        client = CallbackClient(callback)
        run = collect_repository(self.session, self.github, client=client, token="secret")
        self.session.commit()
        self.assertEqual(run.status, "done")
        stats = json.loads(run.stats_json)
        self.assertEqual(stats["merge_requests"], 1)
        self.assertEqual(stats["reviews"], 2)
        self.assertEqual(stats["approvals"], 1)

        mr = self.session.scalars(select(MergeRequest)).one()
        self.assertEqual(mr.number, 12)
        self.assertEqual(mr.state, "open")
        self.assertEqual(mr.author.display_name, "alice")
        self.assertEqual(mr.target_branch, "main")
        self.assertEqual(mr.source_branch, "feat/collector")
        self.assertEqual(mr.additions, 10)
        self.assertEqual(mr.deletions, 2)
        self.assertIsNone(mr.merge_strategy)
        self.assertEqual(len(mr.reviews), 2)
        self.assertEqual(len(mr.approvals), 1)
        self.assertEqual(mr.approvals[0].actor.display_name, "Bob")
        self.assertTrue(any(entry[1].get("Authorization") == "Bearer secret" for entry in client.calls))

        rerun = collect_repository(self.session, self.github, client=client, token="secret")
        self.session.commit()
        rerun_stats = json.loads(rerun.stats_json)
        self.assertEqual(rerun_stats["inserted"], 0)
        self.assertEqual(rerun_stats["updated"], 1)
        self.assertEqual(len(self.session.scalars(select(MergeRequest)).all()), 1)
        self.assertEqual(len(self.session.scalars(select(Review)).all()), 2)
        self.assertEqual(len(self.session.scalars(select(Approval)).all()), 1)

    def test_gitlab_normalisation(self) -> None:
        def callback(url: str, headers: Mapping[str, str]) -> HttpResponse:
            if "/merge_requests/7/approvals" in url:
                return json_response(
                    {
                        "approved_by": [
                            {"user": {"id": 3, "username": "carol", "name": "Carol"}}
                        ]
                    }
                )
            if "/merge_requests?" in url:
                return json_response([gitlab_mr()])
            raise AssertionError(f"URL inattendue : {url}")

        client = CallbackClient(callback)
        run = collect_repository(self.session, self.gitlab, client=client, token="gl-token")
        self.session.commit()
        self.assertEqual(run.status, "done")
        self.assertEqual(run.source, "gitlab")
        mr = self.session.scalars(select(MergeRequest)).one()
        self.assertEqual(mr.number, 7)
        self.assertEqual(mr.state, "merged")
        self.assertEqual(mr.author.display_name, "Bob")
        self.assertEqual(mr.merge_strategy, "squash")
        self.assertIsNone(mr.additions)
        self.assertIsNone(mr.deletions)
        self.assertEqual(len(mr.reviews), 1)
        self.assertEqual(mr.reviews[0].state, "approved")
        self.assertEqual(len(mr.approvals), 1)
        self.assertEqual(mr.approvals[0].actor.display_name, "Carol")
        self.assertTrue(any("PRIVATE-TOKEN" in entry[1] for entry in client.calls))

    def test_etag_304_reutilise_le_cache(self) -> None:
        cache_path = self.root / "cache.json"

        def callback(url: str, headers: Mapping[str, str]) -> HttpResponse:
            if "/pulls/12/reviews?" in url:
                return json_response([])
            if "/pulls?" in url:
                if headers.get("If-None-Match") == '"abc"':
                    return HttpResponse(status=304, headers={}, json=None, text="")
                return json_response([github_pr()], headers={"ETag": '"abc"'})
            raise AssertionError(f"URL inattendue : {url}")

        client = CallbackClient(callback)
        cache = JsonETagCache(cache_path)
        collect_repository(self.session, self.github, client=client, cache=cache)
        self.session.commit()
        self.assertTrue(cache_path.is_file())

        second = collect_repository(self.session, self.github, client=client, cache=cache)
        self.session.commit()
        stats = json.loads(second.stats_json)
        self.assertEqual(stats["inserted"], 0)
        self.assertTrue(any(entry[1].get("If-None-Match") == '"abc"' for entry in client.calls))
        self.assertEqual(len(self.session.scalars(select(MergeRequest)).all()), 1)

    def test_backoff_sur_quota(self) -> None:
        calls = {"count": 0}
        sleeps: list[float] = []

        def callback(url: str, headers: Mapping[str, str]) -> HttpResponse:
            if "/pulls?" in url:
                calls["count"] += 1
                if calls["count"] == 1:
                    return json_response({"message": "quota"}, status=429, headers={"Retry-After": "0"})
                return json_response([github_pr()])
            if "/pulls/12/reviews?" in url:
                return json_response([])
            raise AssertionError(f"URL inattendue : {url}")

        client = CallbackClient(callback)
        run = collect_repository(
            self.session,
            self.github,
            client=client,
            sleep=sleeps.append,
        )
        self.session.commit()
        self.assertEqual(run.status, "done")
        self.assertEqual(calls["count"], 2)
        self.assertEqual(sleeps, [0.0])
        self.assertEqual(len(self.session.scalars(select(MergeRequest)).all()), 1)

    def test_quota_epuise_trace_un_echec_sans_donnees(self) -> None:
        def callback(url: str, headers: Mapping[str, str]) -> HttpResponse:
            if "/pulls?" in url:
                return json_response({"message": "quota"}, status=429, headers={"Retry-After": "0"})
            raise AssertionError(f"URL inattendue : {url}")

        client = CallbackClient(callback)
        with self.assertRaises(ProviderQuotaError):
            collect_repository(self.session, self.github, client=client, sleep=lambda _: None)
        self.session.commit()
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertEqual(run.status, "failed")
        self.assertIn("quota", (run.error or "").lower())
        self.assertEqual(self.session.scalars(select(MergeRequest)).all(), [])

    def test_jeton_invalide(self) -> None:
        def callback(url: str, headers: Mapping[str, str]) -> HttpResponse:
            return json_response({"message": "Bad credentials"}, status=401)

        client = CallbackClient(callback)
        with self.assertRaises(ProviderAuthError):
            collect_repository(self.session, self.github, client=client)
        self.session.commit()
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertEqual(run.status, "failed")

    def test_pagination(self) -> None:
        page_one = [github_pr(number) for number in range(1, 101)]
        page_two = [github_pr(101)]

        def callback(url: str, headers: Mapping[str, str]) -> HttpResponse:
            if "/reviews?" in url:
                return json_response([])
            if "/pulls?" in url:
                page = parse_qs(urlparse(url).query).get("page", [""])[0]
                if page == "1":
                    return json_response(page_one)
                if page == "2":
                    return json_response(page_two)
            raise AssertionError(f"URL inattendue : {url}")

        client = CallbackClient(callback)
        run = collect_repository(self.session, self.github, client=client)
        self.session.commit()
        stats = json.loads(run.stats_json)
        self.assertEqual(stats["merge_requests"], 101)
        self.assertEqual(len(self.session.scalars(select(MergeRequest)).all()), 101)

    def test_mode_fichier_github(self) -> None:
        path = self.root / "github.json"
        path.write_text(
            json.dumps(
                {
                    "pull_requests": [
                        {
                            "number": 4,
                            "title": "fichier",
                            "user": {"login": "alice"},
                            "state": "open",
                            "base": {"ref": "main"},
                            "head": {"ref": "feat"},
                            "created_at": "2026-01-01T10:00:00Z",
                        }
                    ],
                    "reviews": {
                        "4": [
                            {
                                "id": 8,
                                "user": {"login": "bob"},
                                "state": "APPROVED",
                                "submitted_at": "2026-01-02T10:00:00Z",
                            }
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        items = github_from_file(path)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].number, 4)
        self.assertIsNone(items[0].additions)
        self.assertEqual(len(items[0].reviews), 1)
        self.assertEqual(len(items[0].approvals), 1)

        run = collect_repository(self.session, self.github, mode="file", file_path=path)
        self.session.commit()
        self.assertEqual(run.status, "done")
        self.assertEqual(len(self.session.scalars(select(MergeRequest)).all()), 1)

    def test_mode_fichier_gitlab(self) -> None:
        path = self.root / "gitlab.json"
        path.write_text(
            json.dumps(
                {
                    "merge_requests": [gitlab_mr(9)],
                    "approvals": {
                        "9": {
                            "approved_by": [
                                {"user": {"id": 4, "username": "dave", "name": "Dave"}}
                            ]
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        items = gitlab_from_file(path)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].number, 9)
        self.assertEqual(len(items[0].approvals), 1)
        run = collect_repository(self.session, self.gitlab, mode="file", file_path=path)
        self.session.commit()
        self.assertEqual(run.status, "done")
        self.assertEqual(len(self.session.scalars(select(Approval)).all()), 1)

    def test_mode_fichier_absent(self) -> None:
        with self.assertRaises(ProviderError):
            collect_repository(
                self.session,
                self.github,
                mode="file",
                file_path=self.root / "absent.json",
            )


if __name__ == "__main__":
    unittest.main()
