"""Tests de la vue Documentation : fraîcheur, lecteur sûr et génération."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base
from sdlc_console.services.documents_view import (
    GENERATED_NOTICE,
    build_documents_view,
    read_document,
)
from sdlc_console.services.projects import create_project


class DocumentsViewTest(unittest.TestCase):
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
        self.docs = self.root / "docs"
        self._write("docs/00-cadrage/brief.md", "# Brief\n<html><script>alert(1)</script>\n")
        self._write("docs/00-cadrage/exigences-nf.md", "# Exigences\n")
        self._write("docs/architecture/adr/ADR-001.md", "# ADR\n")
        self._write("openspec/changes/atlas/specs/core/spec.md", "# Spec\n")
        self._write("docs/recette/atlas.md", "# Recette\n")
        self._write("docs/ops/runbook.md", "# Runbook\n")
        self._write("docs/incidents/inc-1.md", "# Incident\n")
        self._write("docs/release-notes/0.1.0.md", "# Version\n")
        self._write("docs/suivi-console.html", "<!-- Fichier généré, ne pas modifier. -->\n")
        self.session.commit()

    def _write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_inventaire_fraicheur_et_generated(self) -> None:
        brief = self.root / "docs/00-cadrage/brief.md"
        old = time.time() - 60 * 86400
        os.utime(brief, (old, old))
        view = build_documents_view(
            self.session,
            self.project,
            root=self.root,
            docs_dir=self.docs,
            config={"documentation": {"freshness_days": 30}},
        )
        self.assertEqual(view["summary"]["missing"], 0)
        self.assertEqual(view["summary"]["stale"], 1)
        generated = next(
            item for item in view["documents"] if item["path"] == "docs/suivi-console.html"
        )
        self.assertTrue(generated["generated"])
        self.assertEqual(generated["notice"], GENERATED_NOTICE)
        self.assertIn("/suivi?format=json", generated["regenerate_url"])
        brief_data = next(item for item in view["documents"] if item["path"].endswith("brief.md"))
        self.assertEqual(brief_data["status"], "stale")
        self.assertTrue(brief_data["editable"])

    def test_lecture_markdown_sans_html_interprete(self) -> None:
        document = read_document(
            self.project,
            "docs/00-cadrage/brief.md",
            root=self.root,
        )
        self.assertTrue(document["html_disabled"])
        self.assertIn("<script>alert(1)</script>", document["markdown"] or "")
        with self.assertRaises(ValueError):
            read_document(self.project, ".env", root=self.root)

    def test_api_documents_et_contenu(self) -> None:
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.docs,
            project_root=self.root,
            watcher_enabled=False,
            config_data={"documentation": {"freshness_days": 30}},
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(f"/api/projects/{self.project.id}/documents")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["summary"]["present"], 8)
        selected = client.get(
            f"/api/projects/{self.project.id}/documents?path=docs/00-cadrage/brief.md"
        )
        self.assertEqual(selected.status_code, 200)
        self.assertIn("<script>", selected.json()["selected"]["markdown"])
        content = client.get(
            f"/api/projects/{self.project.id}/documents/content?path=docs/00-cadrage/brief.md"
        )
        self.assertEqual(content.status_code, 200)
        self.assertTrue(content.json()["html_disabled"])


if __name__ == "__main__":
    unittest.main()
