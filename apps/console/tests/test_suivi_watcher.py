"""Tests du watcher de suivi, des conflits et du flux SSE."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, SuiviInconsistency, Task
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.projects import create_project
from sdlc_console.services.suivi_watcher import EventBroker, SuiviWatcher


def _next_nonempty(lines: Iterator[str]) -> str:
    for line in lines:
        if line:
            return line
    raise AssertionError("flux SSE terminé")


class EventBrokerTest(unittest.TestCase):
    def test_publie_vers_un_abonne(self) -> None:
        async def scenario() -> dict[str, object]:
            broker = EventBroker()
            queue = broker.subscribe()
            broker.publish({"type": "suivi.updated", "project_id": 1})
            await asyncio.sleep(0)
            return await asyncio.wait_for(queue.get(), timeout=1)

        event = asyncio.run(scenario())
        self.assertEqual(event["type"], "suivi.updated")


class SuiviWatcherTest(unittest.TestCase):
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
        self.feature = create_feature(
            self.session,
            self.project,
            key="atlas",
            name="Atlas",
            change="atlas",
            tasks_file="openspec/changes/atlas/tasks.md",
            status="doing",
        )
        self.task = create_task(
            self.session,
            self.feature,
            key="1.1",
            title="Première",
            status="todo",
        )
        self.session.commit()
        self.state_path = self.root / "docs" / "suivi" / "atlas.json"
        self.tasks_path = self.root / "openspec" / "changes" / "atlas" / "tasks.md"
        self.state_path.parent.mkdir(parents=True)
        self.tasks_path.parent.mkdir(parents=True)
        self.state_path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "file_updated": "2026-10-20",
                    "features": [
                        {
                            "id": "atlas",
                            "name": "Atlas",
                            "change": "atlas",
                            "status": "doing",
                            "tasks_file": "openspec/changes/atlas/tasks.md",
                            "tasks": [
                                {
                                    "id": "1.1",
                                    "title": "Première",
                                    "status": "todo",
                                    "updated": "2026-10-20",
                                    "note": None,
                                    "history": [],
                                }
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.tasks_path.write_text(
            "## 1. Socle\n- [ ] 1.1 Première\n",
            encoding="utf-8",
        )
        self.events: list[dict[str, object]] = []
        self.broker = EventBroker()
        self.watcher = SuiviWatcher(
            self.Session,
            project_root=self.root,
            docs_dir=self.root / "docs",
            interval_seconds=0.05,
            broker=self.broker,
            on_event=self.events.append,
        )

    def _scan(self) -> list[dict[str, object]]:
        return self.watcher.scan_once()

    def test_premier_scan_sans_evenement_puis_conflit(self) -> None:
        self.assertEqual(self._scan(), [])
        self.assertEqual(self.events, [])

        self.tasks_path.write_text(
            "## 1. Socle\n- [x] 1.1 Première\n",
            encoding="utf-8",
        )
        events = self._scan()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "suivi.updated")
        self.assertEqual(events[0]["project_id"], self.project.id)
        self.assertEqual(events[0]["inconsistencies"], 1)
        self.assertEqual(events[0]["conflicts"][0]["kind"], "etat_non_done_case_cochee")
        self.assertEqual([event["type"] for event in self.events], ["suivi.updated"])
        self.assertTrue((self.root / "docs" / "suivi-atlas.html").is_file())
        self.assertEqual(
            len(self.session.scalars(select(SuiviInconsistency)).all()),
            1,
        )
        refreshed = self.session.get(Task, self.task.id)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "todo")

    def test_modification_externe_de_state_resynchronise(self) -> None:
        self._scan()
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["features"][0]["tasks"][0]["status"] = "done"
        state["features"][0]["tasks"][0]["note"] = "Terminé hors interface"
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.tasks_path.write_text(
            "## 1. Socle\n- [x] 1.1 Première\n",
            encoding="utf-8",
        )
        events = self._scan()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["inconsistencies"], 0)
        self.assertEqual(events[0]["conflicts"], [])
        self.session.expire_all()
        refreshed = self.session.get(Task, self.task.id)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "done")
        self.assertEqual(refreshed.note, "Terminé hors interface")
        self.assertEqual(
            self.session.scalars(select(SuiviInconsistency)).all(),
            [],
        )
        html = (self.root / "docs" / "suivi-atlas.html").read_text(encoding="utf-8")
        self.assertIn("Terminé", html)

    def test_lifespan_demarre_et_arrete_le_watcher(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_interval=0.05,
        )
        with TestClient(app, base_url="http://127.0.0.2") as client:
            self.assertEqual(client.get("/api/health").status_code, 200)
            self.assertIsNotNone(app.state.watcher)
            assert app.state.watcher is not None
            self.assertTrue(app.state.watcher._thread is not None)
        assert app.state.watcher is not None
        self.assertIsNone(app.state.watcher._thread)

    def test_route_sse_emet_ready(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        with client.stream("GET", "/api/events") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/event-stream", response.headers["content-type"])
            lines = response.iter_lines()
            self.assertEqual(_next_nonempty(lines), "event: ready")
            payload = json.loads(_next_nonempty(lines)[len("data: ") :])
            self.assertEqual(payload["type"], "ready")

    def test_route_sse_emet_suivi_updated(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        with client.stream("GET", "/api/projects/1/events") as response:
            lines = response.iter_lines()
            self.assertEqual(_next_nonempty(lines), "event: ready")
            _next_nonempty(lines)
            app.state.broker.publish(
                {
                    "type": "suivi.updated",
                    "project_id": self.project.id,
                    "inconsistencies": 0,
                    "conflicts": [],
                }
            )
            self.assertEqual(_next_nonempty(lines), "event: suivi.updated")
            payload = json.loads(_next_nonempty(lines)[len("data: ") :])
            self.assertEqual(payload["project_id"], self.project.id)


if __name__ == "__main__":
    unittest.main()
