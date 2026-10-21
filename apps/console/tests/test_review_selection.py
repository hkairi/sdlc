"""Tests de la sélection du relecteur indépendant."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.projects import create_project
from sdlc_console.services.review_selection import (
    ReviewerCandidate,
    candidates_from_config,
    independence_level,
    select_reviewer,
)


class ReviewSelectionTest(unittest.TestCase):
    def test_niveaux_independance(self) -> None:
        complete = ReviewerCandidate("B", "M2", "famille-2")
        partial = ReviewerCandidate("B", "M2", "famille-1")
        degraded = ReviewerCandidate("A", "M3", "famille-2")
        self.assertEqual(
            independence_level(
                author_agent="A",
                author_model="M1",
                author_family="famille-1",
                candidate=complete,
            ),
            "complete",
        )
        self.assertEqual(
            independence_level(
                author_agent="A",
                author_model="M1",
                author_family="famille-1",
                candidate=partial,
            ),
            "partial",
        )
        self.assertEqual(
            independence_level(
                author_agent="A",
                author_model="M1",
                author_family="famille-1",
                candidate=degraded,
            ),
            "degraded",
        )

    def test_selection_meilleur_et_derogation(self) -> None:
        candidates = [
            ReviewerCandidate("C", "M3", "famille-2"),
            ReviewerCandidate("B", "M2", "famille-1"),
            ReviewerCandidate("A", "M1", "famille-1"),
        ]
        selection = select_reviewer(
            author_agent="A",
            author_model="M1",
            author_family="famille-1",
            candidates=candidates,
        )
        self.assertEqual(selection.selected.agent_id, "C")
        self.assertEqual(selection.level, "complete")
        self.assertTrue(selection.allowed)

        degraded = select_reviewer(
            author_agent="A",
            author_model="M1",
            candidates=[ReviewerCandidate("A", "M1")],
        )
        self.assertEqual(degraded.level, "degraded")
        self.assertFalse(degraded.allowed)
        self.assertTrue(degraded.waiver_required)
        waived = select_reviewer(
            author_agent="A",
            author_model="M1",
            candidates=[ReviewerCandidate("A", "M1")],
            waiver=True,
        )
        self.assertTrue(waived.allowed)
        self.assertEqual(waived.selected.agent_id, "A")

    def test_config_et_api(self) -> None:
        config = {
            "agents": {
                "A": {"enabled": True, "models": {"M1": "cli a"}},
                "B": {
                    "enabled": True,
                    "models": {"M2": {"family": "famille-2", "label": "B2"}},
                },
            }
        }
        candidates = candidates_from_config(config)
        self.assertEqual({candidate.agent_id for candidate in candidates}, {"A", "B"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = make_engine(f"sqlite:///{root / 'db.sqlite3'}")
            Base.metadata.create_all(engine)
            Session = make_session_factory(engine)
            with Session() as session:
                project = create_project(session, name="Atlas", slug="atlas")
                session.commit()
                app = create_app(
                    allowed_hosts={"127.0.0.2"},
                    session_factory=Session,
                    docs_dir=root / "docs",
                    project_root=root,
                    config_data=config,
                    watcher_enabled=False,
                )
                client = TestClient(app, base_url="http://127.0.0.2")
                response = client.get(
                    f"/api/projects/{project.id}/reviewers",
                    params={
                        "author_agent": "A",
                        "author_model": "M1",
                        "author_family": "famille-1",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["selected"]["agent_id"], "B")
                self.assertEqual(response.json()["level"], "complete")
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
