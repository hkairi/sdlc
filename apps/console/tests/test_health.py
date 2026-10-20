"""Test de santé FastAPI."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from sdlc_console.app import app


class HealthTest(unittest.TestCase):
    def test_health(self) -> None:
        with TestClient(app, base_url="http://127.0.0.2") as client:
            response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertIn("Content-Security-Policy", response.headers)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)


if __name__ == "__main__":
    unittest.main()
