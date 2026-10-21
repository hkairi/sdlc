"""Tests du bus factor et de la propriété par zone CODEOWNERS."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Commit
from sdlc_console.services.ownership import build_ownership, parse_codeowners
from sdlc_console.services.people import resolve_person
from sdlc_console.services.projects import add_repository, create_project


class OwnershipTest(unittest.TestCase):
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
        (repo_path / "CODEOWNERS").write_text(
            "src/billing/ @alice @bob\n"
            "src/empty/ @carol\n",
            encoding="utf-8",
        )
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
            provider="github",
            external_id="alice",
        )
        self.bob = resolve_person(
            self.session,
            self.project,
            email="bob@example.com",
            display_name="Bob",
            provider="github",
            external_id="bob",
        )
        self.carol = resolve_person(
            self.session,
            self.project,
            email="carol@example.com",
            display_name="Carol",
            provider="github",
            external_id="carol",
        )
        self.bot = resolve_person(
            self.session,
            self.project,
            email="bot@example.com",
            display_name="Bot",
            provider="github",
            external_id="bot",
        )
        self.bot.is_bot = True
        self._commit("a1", self.alice, ["src/billing/a.py"])
        self._commit("a2", self.alice, ["src/billing/b.py"])
        self._commit("a3", self.alice, ["src/billing/c.py"])
        self._commit("b1", self.bob, ["src/billing/d.py"])
        self._commit("bot1", self.bot, ["src/billing/bot.py"])
        self._commit(
            "old",
            self.alice,
            ["src/billing/old.py"],
            when=datetime.now(UTC) - timedelta(days=200),
        )
        self.session.commit()

    def _commit(self, sha: str, person, files: list[str], *, when: datetime | None = None) -> None:
        moment = when or datetime.now(UTC) - timedelta(days=1)
        self.session.add(
            Commit(
                repository_id=self.repo.id,
                sha=sha,
                person_id=person.id,
                author_name=person.display_name,
                author_email=f"{person.id}@example.com",
                authored_at=moment,
                committed_at=moment,
                additions=1,
                deletions=0,
                files_changed=len(files),
                files_json=json.dumps(files),
                is_merge=False,
                is_bot=person.is_bot,
                ai_assisted=False,
                trailers_json="[]",
                commit_fingerprint=f"fp-{sha}",
                message="message",
            )
        )
        self.session.flush()

    def test_bus_factor_et_alertes(self) -> None:
        result = build_ownership(self.session, self.project)
        zones = {zone["zone"]: zone for zone in result["zones"]}
        billing = zones["src/billing/"]
        self.assertEqual(billing["commits"], 4)
        self.assertEqual(billing["bus_factor"], 1)
        self.assertTrue(billing["risk"])
        self.assertEqual(billing["primary_owner"]["name"], "Alice")
        self.assertEqual(billing["secondary_owner"]["name"], "Bob")
        self.assertEqual(billing["declared_owners"], ["alice", "bob"])
        self.assertEqual(billing["owners"], ["Alice", "Bob"])
        self.assertEqual(result["alerts"][0]["zone"], "src/billing/")
        self.assertEqual(zones["src/empty/"]["bus_factor"], None)
        self.assertEqual(zones["src/empty/"]["status"], "not_measured")

    def test_fenetre_et_fichiers(self) -> None:
        result = build_ownership(self.session, self.project, window_days=2)
        billing = next(zone for zone in result["zones"] if zone["zone"] == "src/billing/")
        self.assertEqual(billing["commits"], 4)
        # La vieille commit et le bot sont exclus, pas les quatre commits récents.

        filtered = build_ownership(self.session, self.project, repository_ids=[self.repo.id])
        self.assertEqual(filtered["zones"][0]["repository_name"], "api")

    def test_parse_codeowners(self) -> None:
        rules = parse_codeowners(
            "# commentaire\nsrc/a/ @alice @bob\n[section]\nsrc/b/ @carol\n",
            repository_id=1,
        )
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0].pattern, "src/a/")
        self.assertEqual(rules[0].owners, ("alice", "bob"))

    def test_api_ownership(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/team/ownership")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["zones"][0]["bus_factor"], 1)
        self.assertEqual(
            client.get(f"/api/projects/{self.project.id}/team/ownership?repository_id=all").status_code,
            200,
        )

    def test_sans_codeowners(self) -> None:
        (self.root / "api" / "CODEOWNERS").unlink()
        result = build_ownership(self.session, self.project)
        self.assertEqual(result["status"], "not_measured")
        self.assertEqual(result["zones"], [])


if __name__ == "__main__":
    unittest.main()
