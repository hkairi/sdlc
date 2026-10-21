"""Tests de performance reproductibles sur un volume réduit pour la CI.

Le jeu de démonstration de la cible (100 000 commits) est généré par
`apps/console/scripts/perf_console.py`. La CI utilise 10 000 commits pour rester
rapide, avec les mêmes seuils de temps et de mémoire.
"""

from __future__ import annotations

import tempfile
import time
import tracemalloc
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import insert

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Commit, utc_now
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.overview import build_overview
from sdlc_console.services.projects import add_repository, create_project
from sdlc_console.services.team_metrics import build_team_metrics

REPOSITORIES = 5
COMMITS = 10_000


class PerformanceTargetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.engine = make_engine(f"sqlite:///{root / 'perf.sqlite3'}")
        Base.metadata.create_all(cls.engine)
        cls.Session = make_session_factory(cls.engine)
        cls.session = cls.Session()
        cls.project = create_project(cls.session, name="Perf", slug="perf")
        cls.repository_ids: list[int] = []
        for index in range(REPOSITORIES):
            path = root / f"repo-{index}"
            path.mkdir()
            (path / ".git").mkdir()
            repository = add_repository(
                cls.session,
                cls.project,
                name=f"repo-{index}",
                provider="github",
                url=f"https://github.com/hm/repo-{index}",
                local_path=path,
                is_primary=index == 0,
            )
            cls.repository_ids.append(repository.id)
        feature = create_feature(cls.session, cls.project, key="perf", name="Perf")
        for index in range(100):
            create_task(cls.session, feature, key=f"t-{index}", title=f"Tâche {index}")
        cls.session.commit()
        rows = []
        start = datetime.now(UTC) - timedelta(days=365)
        for index in range(COMMITS):
            rows.append(
                {
                    "repository_id": cls.repository_ids[index % REPOSITORIES],
                    "sha": f"{index:040x}",
                    "authored_at": start + timedelta(minutes=index),
                    "committed_at": start + timedelta(minutes=index),
                    "additions": index % 20,
                    "deletions": index % 7,
                    "files_changed": 1,
                    "files_json": "[]",
                    "is_merge": False,
                    "is_bot": False,
                    "ai_assisted": False,
                    "trailers_json": "[]",
                    "commit_fingerprint": f"fingerprint-{index}",
                    "message": f"commit {index}",
                    "created_at": utc_now(),
                }
            )
        cls.session.execute(insert(Commit), rows)
        cls.session.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()
        cls.engine.dispose()
        cls._tmp.cleanup()

    def test_vue_ensemble_sous_1_5_s(self) -> None:
        start = time.perf_counter()
        payload = build_overview(self.session, self.project)
        elapsed = time.perf_counter() - start
        self.assertEqual(payload["project"]["id"], self.project.id)
        self.assertLess(elapsed, 1.5)

    def test_vue_multi_depots_sous_2_s(self) -> None:
        start = time.perf_counter()
        payload = build_team_metrics(self.session, self.project)
        elapsed = time.perf_counter() - start
        self.assertEqual(len(payload["repositories"]), REPOSITORIES)
        self.assertLess(elapsed, 2.0)

    def test_demarrage_sous_2_s(self) -> None:
        start = time.perf_counter()
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=Path(self._tmp.name) / "docs",
            project_root=Path(self._tmp.name),
            watcher_enabled=False,
        )
        elapsed = time.perf_counter() - start
        self.assertIsNotNone(app)
        self.assertLess(elapsed, 2.0)

    def test_memoire_sous_512_mo(self) -> None:
        tracemalloc.start()
        try:
            build_team_metrics(self.session, self.project)
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak / (1024 * 1024), 512)

    def test_liste_paginee_sous_500_ms(self) -> None:
        from sdlc_console.services.features_view import build_features_view

        start = time.perf_counter()
        payload = build_features_view(self.session, self.project, limit=50)
        elapsed = time.perf_counter() - start
        self.assertEqual(len(payload["features"]), 1)
        self.assertLess(elapsed, 0.5)


if __name__ == "__main__":
    unittest.main()
