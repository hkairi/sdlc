"""Tests du jeu de démonstration idempotent."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Deployment, GateRun, Project, TaskRun
from sdlc_console.services.demo import seed_demo


class DemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.engine = make_engine(f"sqlite:///{self.root / 'db.sqlite3'}")
        Base.metadata.create_all(self.engine)
        self.Session = make_session_factory(self.engine)
        self.session = self.Session()
        self.addCleanup(self.session.close)

    def test_seed_demo_complet_et_idempotent(self) -> None:
        result = seed_demo(self.session, root=self.root)
        self.assertTrue(result["seeded"])
        self.assertEqual(result["repositories"], 2)
        self.assertEqual(result["tasks"], 5)
        self.assertEqual(result["runs"], 5)
        self.assertEqual(result["deployments"], 5)
        self.assertEqual(result["gates"], 7)
        self.assertEqual(
            self.session.scalar(select(func.count(Project.id))),
            1,
        )
        self.assertEqual(
            self.session.scalar(select(func.count(TaskRun.id))),
            5,
        )
        self.assertEqual(
            self.session.scalar(select(func.count(Deployment.id))),
            5,
        )
        self.assertEqual(
            self.session.scalar(select(func.count(GateRun.id))),
            7,
        )
        again = seed_demo(self.session, root=self.root)
        self.assertFalse(again["seeded"])
        self.assertEqual(
            self.session.scalar(select(func.count(Project.id))),
            1,
        )


if __name__ == "__main__":
    unittest.main()
