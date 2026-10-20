"""Tests d'ingestion de state.json et tasks.md et des incohérences de suivi."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Feature, IngestionRun, SuiviInconsistency, Task
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.people import resolve_person
from sdlc_console.services.projects import add_repository, create_project
from sdlc_console.services.suivi_ingestion import (
    SuiviIngestionError,
    ingest_state,
    ingest_suivi,
    ingest_tasks_md,
    parse_tasks_md_file,
)


class SuiviIngestionTest(unittest.TestCase):
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

    def _state(self, features: list[dict[str, object]], *, name: str = "state.json") -> Path:
        path = self.root / name
        path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "file_updated": "2026-10-20",
                    "features": features,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def _tasks(self, body: str, *, change: str = "console-sdlc") -> Path:
        directory = self.root / change
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "tasks.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_ingestion_coherente_et_idempotente(self) -> None:
        state = self._state(
            [
                {
                    "id": "console-sdlc",
                    "name": "Console SDLC",
                    "change": "console-sdlc",
                    "objective": "Construire la console",
                    "tasks_file": "openspec/changes/console-sdlc/tasks.md",
                    "sources": {
                        "proposal": "openspec/changes/console-sdlc/proposal.md",
                        "design": "openspec/changes/console-sdlc/design.md",
                    },
                    "phases": [
                        {
                            "id": "cadrage",
                            "name": "Cadrage",
                            "order": 1,
                            "items": [{"id": "proposal", "status": "done"}],
                        }
                    ],
                    "version": "0.1",
                    "delivered": False,
                    "blocked": False,
                    "tasks": [
                        {
                            "id": "1.1",
                            "lot": "L1",
                            "title": "Initialiser",
                            "text": "Initialiser apps/console",
                            "status": "done",
                            "updated": "2026-10-20",
                            "note": "Fait",
                            "executor": "Claude",
                            "reviewer": "GLM",
                            "files": ["a.py"],
                            "acceptance": "Le squelette existe",
                        },
                        {
                            "id": "1.2",
                            "lot": "L1",
                            "title": "Config",
                            "text": "Écrire le schéma",
                            "status": "doing",
                            "updated": "2026-10-20",
                        },
                    ],
                }
            ]
        )
        tasks = self._tasks(
            "## 1. Socle\n"
            "- [x] 1.1 Initialiser `apps/console/`\n"
            "- [ ] 1.2 **[1.1]** Écrire le schéma de configuration\n"
        )
        result = ingest_suivi(
            self.session,
            self.project,
            state_path=state,
            tasks_paths=[tasks],
        )
        self.session.commit()
        self.assertEqual(result.run.status, "done")
        self.assertEqual(result.run.source, "suivi")
        self.assertEqual(result.stats["features_inserted"], 1)
        self.assertEqual(result.stats["tasks_inserted"], 2)
        self.assertEqual(result.inconsistencies, ())

        feature = self.session.scalars(select(Feature)).one()
        self.assertEqual(feature.key, "console-sdlc")
        self.assertEqual(feature.name, "Console SDLC")
        self.assertEqual(feature.status, "doing")
        self.assertEqual(feature.objective, "Construire la console")
        self.assertEqual(feature.spec_path, "openspec/changes/console-sdlc/design.md")
        self.assertEqual(json.loads(feature.sources_json)["proposal"], "openspec/changes/console-sdlc/proposal.md")
        phases = json.loads(feature.phases_json)
        self.assertEqual(phases[0]["id"], "cadrage")
        self.assertEqual(phases[0]["items"][0]["status"], "done")
        self.assertEqual(feature.version, "0.1")

        first = self.session.scalars(select(Task).where(Task.key == "1.1")).one()
        self.assertEqual(first.status, "done")
        self.assertEqual(first.title, "Initialiser")
        self.assertEqual(first.description, "Initialiser `apps/console/`")
        self.assertEqual(first.note, "Fait")
        self.assertEqual(first.executor_label, "Claude")
        self.assertEqual(first.reviewer_label, "GLM")
        self.assertEqual(json.loads(first.files_json), ["a.py"])
        self.assertEqual(first.acceptance, "Le squelette existe")
        self.assertIsNotNone(first.updated_at)
        second = self.session.scalars(select(Task).where(Task.key == "1.2")).one()
        self.assertEqual(second.status, "doing")
        self.assertNotIn("**[", second.description or "")

        rerun = ingest_suivi(
            self.session,
            self.project,
            state_path=state,
            tasks_paths=[tasks],
        )
        self.session.commit()
        self.assertEqual(len(self.session.scalars(select(Feature)).all()), 1)
        self.assertEqual(len(self.session.scalars(select(Task)).all()), 2)
        self.assertEqual(rerun.stats["features_inserted"], 0)
        self.assertEqual(rerun.stats["tasks_inserted"], 0)
        self.assertEqual(rerun.stats["md_tasks_inserted"], 0)

    def test_incoherences_case_et_statut(self) -> None:
        state = self._state(
            [
                {
                    "id": "console-sdlc",
                    "name": "Console",
                    "change": "console-sdlc",
                    "tasks": [
                        {"id": "1.1", "title": "Une", "status": "done"},
                        {"id": "1.2", "title": "Deux", "status": "todo"},
                    ],
                }
            ]
        )
        tasks = self._tasks(
            "## 1. Socle\n"
            "- [ ] 1.1 Une\n"
            "- [x] 1.2 Deux\n"
        )
        result = ingest_suivi(
            self.session,
            self.project,
            state_path=state,
            tasks_paths=[tasks],
        )
        self.session.commit()
        self.assertEqual(len(result.inconsistencies), 2)
        kinds = {item.kind for item in result.inconsistencies}
        self.assertEqual(kinds, {"etat_done_case_vide", "etat_non_done_case_cochee"})
        self.assertEqual(result.stats["inconsistencies"], 2)
        persisted = self.session.scalars(select(SuiviInconsistency)).all()
        self.assertEqual(len(persisted), 2)
        self.assertEqual(
            {item.kind for item in persisted},
            {"etat_done_case_vide", "etat_non_done_case_cochee"},
        )

        coherent_tasks = self._tasks(
            "## 1. Socle\n"
            "- [x] 1.1 Une\n"
            "- [ ] 1.2 Deux\n"
        )
        ingest_suivi(
            self.session,
            self.project,
            state_path=state,
            tasks_paths=[coherent_tasks],
        )
        self.session.commit()
        self.assertEqual(
            self.session.scalars(select(SuiviInconsistency)).all(),
            [],
        )

    def test_taches_presentes_dans_une_seule_source(self) -> None:
        state = self._state(
            [
                {
                    "id": "console-sdlc",
                    "name": "Console",
                    "change": "console-sdlc",
                    "tasks": [{"id": "1.1", "title": "Une", "status": "done"}],
                }
            ]
        )
        tasks = self._tasks(
            "## 1. Socle\n"
            "- [x] 1.2 Deux\n"
        )
        result = ingest_suivi(
            self.session,
            self.project,
            state_path=state,
            tasks_paths=[tasks],
        )
        self.session.commit()
        kinds = {item.kind for item in result.inconsistencies}
        self.assertEqual(kinds, {"tache_absente_tasks_md", "case_absente_state"})
        self.assertEqual(len(self.session.scalars(select(Task)).all()), 2)
        created = self.session.scalars(select(Task).where(Task.key == "1.2")).one()
        self.assertEqual(created.status, "done")

    def test_tasks_md_sans_state_cree_feature(self) -> None:
        tasks = self._tasks(
            "## 2. Projets\n"
            "- [x] 2.1 Une\n"
            "- [ ] 2.2 Deux\n",
            change="autre-change",
        )
        result = ingest_tasks_md(self.session, self.project, tasks)
        self.session.commit()
        self.assertEqual(result.run.status, "done")
        feature = self.session.scalars(select(Feature)).one()
        self.assertEqual(feature.key, "autre-change")
        self.assertEqual(feature.status, "doing")
        self.assertEqual(len(feature.tasks), 2)
        self.assertEqual(result.inconsistencies, ())

    def test_state_sans_tasks_md(self) -> None:
        state = self._state(
            [
                {
                    "id": "console-sdlc",
                    "name": "Console",
                    "change": "console-sdlc",
                    "delivered": True,
                    "tasks": [{"id": "1.1", "title": "Une", "status": "done"}],
                }
            ]
        )
        result = ingest_state(self.session, self.project, state)
        self.session.commit()
        feature = self.session.scalars(select(Feature)).one()
        self.assertEqual(feature.status, "done")
        self.assertEqual(result.inconsistencies, ())
        self.assertEqual(result.run.source, "state.json")

    def test_statuts_derives_delivered_et_blocked(self) -> None:
        state = self._state(
            [
                {"id": "done-f", "name": "Done", "delivered": True},
                {"id": "blocked-f", "name": "Blocked", "blocked": True},
                {"id": "todo-f", "name": "Todo"},
            ]
        )
        ingest_state(self.session, self.project, state)
        self.session.commit()
        statuses = {
            feature.key: feature.status
            for feature in self.session.scalars(select(Feature)).all()
        }
        self.assertEqual(statuses, {"done-f": "done", "blocked-f": "blocked", "todo-f": "todo"})

    def test_preservation_des_personnes_et_depots(self) -> None:
        path = self.root / "api"
        path.mkdir()
        (path / ".git").mkdir()
        repository = add_repository(
            self.session,
            self.project,
            name="api",
            provider="github",
            url="https://github.com/hm/api",
            local_path=path,
        )
        owner = resolve_person(
            self.session,
            self.project,
            email="alice@example.com",
            display_name="Alice",
        )
        reviewer = resolve_person(
            self.session,
            self.project,
            email="bob@example.com",
            display_name="Bob",
        )
        feature = create_feature(
            self.session,
            self.project,
            key="console-sdlc",
            name="Console",
            primary_repository=repository,
            repository_ids=[repository.id],
            owner_person=owner,
        )
        task = create_task(
            self.session,
            feature,
            key="1.1",
            title="Une",
            primary_repository=repository,
            repository_ids=[repository.id],
            owner_person=owner,
            reviewer_person=reviewer,
        )
        self.session.commit()
        state = self._state(
            [
                {
                    "id": "console-sdlc",
                    "name": "Console",
                    "change": "console-sdlc",
                    "tasks": [{"id": "1.1", "title": "Une nouvelle", "status": "done"}],
                }
            ]
        )
        tasks = self._tasks("## 1. Socle\n- [x] 1.1 Une\n")
        ingest_suivi(
            self.session,
            self.project,
            state_path=state,
            tasks_paths=[tasks],
        )
        self.session.commit()
        self.assertEqual(feature.owner_person_id, owner.id)
        self.assertEqual(feature.primary_repository_id, repository.id)
        self.assertEqual([repo.id for repo in feature.repositories], [repository.id])
        self.assertEqual(task.owner_person_id, owner.id)
        self.assertEqual(task.reviewer_person_id, reviewer.id)
        self.assertEqual(task.primary_repository_id, repository.id)
        self.assertEqual([repo.id for repo in task.repositories], [repository.id])

    def test_statut_invalide_et_json_invalide(self) -> None:
        state = self._state(
            [
                {
                    "id": "console-sdlc",
                    "name": "Console",
                    "tasks": [{"id": "1.1", "title": "Une", "status": "inconnu"}],
                }
            ]
        )
        with self.assertRaises(SuiviIngestionError):
            ingest_state(self.session, self.project, state)
        self.session.commit()
        run = self.session.scalars(select(IngestionRun)).one()
        self.assertEqual(run.status, "failed")
        self.assertEqual(self.session.scalars(select(Feature)).all(), [])

        invalid = self.root / "invalid.json"
        invalid.write_text("{", encoding="utf-8")
        with self.assertRaises(SuiviIngestionError):
            ingest_state(self.session, self.project, invalid)
        self.session.commit()

    def test_parse_tasks_md(self) -> None:
        tasks = self._tasks(
            "## 2. Projets, dépôts et ingestion\n"
            "- [x] 2.1 **[1.3]** Implémenter les projets\n"
            "- [ ] 2.2 Simple\n"
        )
        parsed = parse_tasks_md_file(tasks)
        self.assertEqual(parsed.change, "console-sdlc")
        self.assertEqual(parsed.tasks[0].key, "2.1")
        self.assertTrue(parsed.tasks[0].checked)
        self.assertEqual(parsed.tasks[0].lot, "L2")
        self.assertEqual(parsed.tasks[0].title, "Implémenter les projets")
        self.assertFalse(parsed.tasks[1].checked)


if __name__ == "__main__":
    unittest.main()
