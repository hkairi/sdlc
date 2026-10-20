"""Scénario de bout en bout du suivi et contrôle d'accessibilité statique."""

from __future__ import annotations

import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.features import create_feature, create_task
from sdlc_console.services.projects import create_project


class _HtmlCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, {key: value or "" for key, value in attrs}))

    def handle_data(self, data: str) -> None:
        self.text.append(data)


class SuiviE2ETest(unittest.TestCase):
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
        feature = create_feature(
            self.session,
            self.project,
            key="F-1",
            name="Suivi",
            status="doing",
        )
        create_task(
            self.session,
            feature,
            key="3.6",
            title="Scénario de bout en bout",
            status="doing",
            acceptance="Le suivi s'ouvre une fois",
            lot="L3",
        )
        self.session.commit()
        self.app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
        )
        self.client = TestClient(self.app, base_url="http://127.0.0.2")

    def test_le_suivi_devient_pret_puis_reste_accessible(self) -> None:
        before = self.client.get(f"/api/projects/{self.project.id}/suivi/status")
        self.assertEqual(before.status_code, 200)
        self.assertFalse(before.json()["ready"])
        self.assertTrue(before.json()["open_on_ready"])

        generated = self.client.get(f"/api/projects/{self.project.id}/suivi?format=json")
        self.assertEqual(generated.status_code, 200)
        self.assertEqual(generated.json()["summary"]["tasks"], 1)

        after = self.client.get(f"/api/projects/{self.project.id}/suivi/status")
        self.assertEqual(after.status_code, 200)
        payload = after.json()
        self.assertTrue(payload["ready"])
        self.assertFalse(payload["stale"])
        self.assertEqual(payload["url"], f"/api/projects/{self.project.id}/suivi?format=html")
        self.assertTrue(Path(payload["html_path"]).is_file())
        self.assertTrue(Path(payload["json_path"]).is_file())

        html = self.client.get(payload["url"])
        self.assertEqual(html.status_code, 200)
        self.assertTrue(html.headers["content-type"].startswith("text/html"))
        self.assertIn("Content-Security-Policy", html.headers)
        self.assertIn("Fichier généré, ne pas modifier", html.text)
        self.assertIn("Scénario de bout en bout", html.text)

        second = self.client.get(payload["url"])
        self.assertEqual(second.status_code, 200)

    def test_accessibilite_statique_du_html_genere(self) -> None:
        self.client.get(f"/api/projects/{self.project.id}/suivi?format=json")
        status = self.client.get(f"/api/projects/{self.project.id}/suivi/status").json()
        html = self.client.get(status["url"]).text
        parser = _HtmlCollector()
        parser.feed(html)
        tags = parser.tags
        names = [name for name, _attrs in tags]
        self.assertIn("html", names)
        html_attrs = dict(tags[names.index("html")][1])
        self.assertEqual(html_attrs.get("lang"), "fr")
        self.assertIn("main", names)
        self.assertIn("h1", names)
        self.assertIn("table", names)
        self.assertIn("caption", names)
        self.assertIn("progress", names)
        self.assertIn("time", names)
        self.assertNotIn("script", names)
        self.assertNotIn("iframe", names)

        scoped_headers = [
            attrs for name, attrs in tags if name == "th" and attrs.get("scope") == "col"
        ]
        self.assertGreaterEqual(len(scoped_headers), 1)
        progress = next(attrs for name, attrs in tags if name == "progress")
        self.assertIn("value", progress)
        self.assertEqual(progress.get("max"), "100")
        time_attrs = next(attrs for name, attrs in tags if name == "time")
        self.assertIn("datetime", time_attrs)

        external_stylesheets = [
            attrs
            for name, attrs in tags
            if name == "link" and "stylesheet" in attrs.get("rel", "")
        ]
        self.assertEqual(external_stylesheets, [])
        text = " ".join(parser.text)
        self.assertIn("Terminé", text)
        self.assertIn("En cours", text)


if __name__ == "__main__":
    unittest.main()
