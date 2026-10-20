"""Tests des features, tâches et liaisons multi-dépôts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import (
    Base,
    Feature,
    FeatureRepository,
    Repository,
    Task,
    TaskRepository,
)
from sdlc_console.services.features import (
    FeatureError,
    create_feature,
    create_task,
    get_feature_by_key,
    get_task_by_key,
    list_features,
    list_tasks,
    set_feature_repositories,
    set_task_repositories,
)
from sdlc_console.services.people import resolve_person
from sdlc_console.services.projects import add_repository, create_project


class FeaturesTasksTest(unittest.TestCase):
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
        self.api = self._repo("api")
        self.web = self._repo("web")
        self.owner = resolve_person(
            self.session,
            self.project,
            email="alice@example.com",
            display_name="Alice",
        )
        self.reviewer = resolve_person(
            self.session,
            self.project,
            email="bob@example.com",
            display_name="Bob",
        )
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

    def test_feature_et_tache_multi_depots(self) -> None:
        feature = create_feature(
            self.session,
            self.project,
            key="F-1",
            name="Collecte multi-dépôts",
            status="doing",
            primary_repository=self.api,
            repository_ids=[self.api.id],
            owner_person=self.owner,
            spec_path="openspec/changes/console-sdlc/specs/console-core/spec.md",
            change="console-sdlc",
            objective="Collecter les commits",
            tasks_file="openspec/changes/console-sdlc/tasks.md",
            sources={"proposal": "openspec/changes/console-sdlc/proposal.md"},
            version="0.1",
        )
        set_feature_repositories(
            self.session,
            feature,
            [self.api.id, self.web.id],
            primary_repository_id=self.web.id,
        )
        self.session.commit()

        self.assertEqual(feature.status, "doing")
        self.assertEqual(feature.primary_repository_id, self.web.id)
        self.assertEqual({repo.name for repo in feature.repositories}, {"api", "web"})
        self.assertEqual(feature.owner.display_name, "Alice")
        self.assertEqual(json.loads(feature.sources_json), {"proposal": "openspec/changes/console-sdlc/proposal.md"})
        self.assertEqual(feature.objective, "Collecter les commits")

        task = create_task(
            self.session,
            feature,
            key="3.1",
            title="Créer les modèles",
            status="doing",
            primary_repository=self.web,
            repository_ids=[self.api.id],
            owner_person=self.owner,
            reviewer_person=self.reviewer,
            executor_label="Claude",
            reviewer_label="GLM",
            files=["apps/console/src/sdlc_console/models.py"],
            acceptance="Les quatre tables existent",
            description="Implémenter les modèles et services.",
            lot="L3",
            note="En cours.",
        )
        self.session.commit()

        self.assertEqual(task.key, "3.1")
        self.assertEqual(task.status, "doing")
        self.assertEqual(task.primary_repository_id, self.web.id)
        self.assertEqual({repo.name for repo in task.repositories}, {"api", "web"})
        self.assertEqual(task.owner.display_name, "Alice")
        self.assertEqual(task.reviewer.display_name, "Bob")
        self.assertEqual(task.executor_label, "Claude")
        self.assertEqual(json.loads(task.files_json), ["apps/console/src/sdlc_console/models.py"])
        self.assertEqual(task.acceptance, "Les quatre tables existent")
        primary_links = [
            link.repository_id for link in task.repository_links if link.is_primary
        ]
        self.assertEqual(primary_links, [self.web.id])
        self.assertEqual(get_feature_by_key(self.session, self.project, "F-1").id, feature.id)
        self.assertEqual(get_task_by_key(self.session, feature, "3.1").id, task.id)

    def test_cle_feature_unique_par_projet(self) -> None:
        create_feature(self.session, self.project, key="F-1", name="Une")
        self.session.commit()
        with self.assertRaises(IntegrityError):
            create_feature(self.session, self.project, key="F-1", name="Deux")
        self.session.rollback()
        other = create_project(self.session, name="Borealis", slug="borealis")
        self.session.commit()
        create_feature(self.session, other, key="F-1", name="Une")
        self.session.commit()
        self.assertEqual(self.session.scalar(select(func.count(Feature.id))), 2)

    def test_cle_tache_unique_par_feature(self) -> None:
        feature = create_feature(self.session, self.project, key="F-1", name="Une")
        create_task(self.session, feature, key="3.1", title="Une")
        self.session.commit()
        with self.assertRaises(IntegrityError):
            create_task(self.session, feature, key="3.1", title="Deux")
        self.session.rollback()
        other = create_feature(self.session, self.project, key="F-2", name="Deux")
        create_task(self.session, other, key="3.1", title="Une")
        self.session.commit()
        self.assertEqual(self.session.scalar(select(func.count(Task.id))), 2)

    def test_statut_invalide_refuse(self) -> None:
        with self.assertRaises(FeatureError):
            create_feature(self.session, self.project, key="F-1", name="Une", status="inconnu")
        feature = create_feature(self.session, self.project, key="F-1", name="Une")
        self.session.commit()
        with self.assertRaises(FeatureError):
            create_task(self.session, feature, key="3.1", title="Une", status="inconnu")

    def test_depot_hors_projet_refuse(self) -> None:
        other = create_project(self.session, name="Borealis", slug="borealis")
        self.session.commit()
        path = self.root / "other"
        path.mkdir()
        (path / ".git").mkdir()
        other_repo = add_repository(
            self.session,
            other,
            name="other",
            provider="github",
            url="https://github.com/hm/other",
            local_path=path,
        )
        self.session.commit()
        with self.assertRaises(FeatureError):
            create_feature(
                self.session,
                self.project,
                key="F-1",
                name="Une",
                repository_ids=[other_repo.id],
            )

    def test_remplacement_des_depots_et_principal(self) -> None:
        feature = create_feature(
            self.session,
            self.project,
            key="F-1",
            name="Une",
            primary_repository=self.api,
            repository_ids=[self.api.id],
        )
        self.session.commit()
        set_feature_repositories(self.session, feature, [self.web.id])
        self.session.commit()
        self.assertEqual([repo.name for repo in feature.repositories], ["web"])
        self.assertIsNone(feature.primary_repository_id)

        set_feature_repositories(
            self.session,
            feature,
            [self.web.id],
            primary_repository_id=self.web.id,
        )
        self.session.commit()
        self.assertEqual(feature.primary_repository_id, self.web.id)

        task = create_task(
            self.session,
            feature,
            key="3.1",
            title="Une",
            primary_repository=self.api,
            repository_ids=[self.api.id],
        )
        self.session.commit()
        set_task_repositories(
            self.session,
            task,
            [self.web.id],
            primary_repository_id=self.web.id,
        )
        self.session.commit()
        self.assertEqual([repo.name for repo in task.repositories], ["web"])
        self.assertEqual(task.primary_repository_id, self.web.id)
        primary_links = [link.repository_id for link in task.repository_links if link.is_primary]
        self.assertEqual(primary_links, [self.web.id])
        self.assertEqual(self.session.scalar(select(func.count(TaskRepository.task_id))), 1)

    def test_filtres_et_cascade(self) -> None:
        first = create_feature(self.session, self.project, key="F-1", name="Une", status="done")
        second = create_feature(self.session, self.project, key="F-2", name="Deux", status="doing")
        task_done = create_task(self.session, first, key="1.1", title="Une", status="done")
        create_task(self.session, second, key="2.1", title="Deux", status="doing")
        self.session.commit()

        done_features = list_features(self.session, self.project, statuses=["done"])
        self.assertEqual([feature.key for feature in done_features], ["F-1"])
        done_tasks = list_tasks(self.session, first, statuses=["done"])
        self.assertEqual([task.key for task in done_tasks], ["1.1"])

        self.session.delete(first)
        self.session.commit()
        self.assertIsNone(self.session.scalar(select(Feature).where(Feature.id == first.id)))
        self.assertIsNone(self.session.scalar(select(Task).where(Task.id == task_done.id)))
        self.assertEqual(self.session.scalar(select(func.count(FeatureRepository.feature_id))), 0)
        self.assertEqual(self.session.scalar(select(func.count(TaskRepository.task_id))), 0)


if __name__ == "__main__":
    unittest.main()
