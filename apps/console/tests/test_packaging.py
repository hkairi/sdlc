"""Tests du packaging : frontend embarqué et commande unique."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base

REPO_ROOT = Path(__file__).resolve().parents[3]
CONSOLE_ROOT = REPO_ROOT / "apps" / "console"


class PackagingTest(unittest.TestCase):
    def test_pyproject_embarque_le_frontend(self) -> None:
        text = (CONSOLE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('packages = ["src/sdlc_console"]', text)
        self.assertTrue((CONSOLE_ROOT / "src" / "sdlc_console" / "web" / "dist").is_dir())
        script = CONSOLE_ROOT / "scripts" / "build_frontend.sh"
        self.assertTrue(script.is_file())
        self.assertIn("npm run build", script.read_text(encoding="utf-8"))

    def test_interface_servie_sur_la_racine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static = root / "dist"
            static.mkdir()
            (static / "index.html").write_text("<!doctype html><html><body>Console</body></html>")
            engine = make_engine(f"sqlite:///{root / 'db.sqlite3'}")
            Base.metadata.create_all(engine)
            factory = make_session_factory(engine)
            app = create_app(
                allowed_hosts={"127.0.0.2"},
                session_factory=factory,
                docs_dir=root / "docs",
                project_root=root,
                watcher_enabled=False,
                static_dir=static,
            )
            client = TestClient(app, base_url="http://127.0.0.2")
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("Console", response.text)
            self.assertIn("Content-Security-Policy", response.headers)
            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
