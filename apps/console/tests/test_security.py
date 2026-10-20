"""Tests de la sécurité locale : Host, Origin/Referer, CSRF, Content-Type, CSP."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.security import CsrfProtector

BASE = "http://127.0.0.2"
ALLOWED_ORIGINS = {"http://127.0.0.2:8765", "http://127.0.0.2:5173"}


def _app() -> object:
    app = create_app(
        allowed_hosts={"127.0.0.2"},
        allowed_origins=ALLOWED_ORIGINS,
        csrf_secret=b"test-secret",
    )

    @app.post("/api/_test")
    def _test() -> dict[str, bool]:
        return {"ok": True}

    return app


class CsrfProtectorTest(unittest.TestCase):
    def test_jeton_valide(self) -> None:
        protector = CsrfProtector(b"secret")
        self.assertTrue(protector.verify(protector.issue()))

    def test_jeton_altere(self) -> None:
        protector = CsrfProtector(b"secret")
        token = protector.issue()
        self.assertFalse(protector.verify(token[:-1] + ("0" if token[-1] != "0" else "1")))

    def test_jeton_absent(self) -> None:
        self.assertFalse(CsrfProtector(b"secret").verify(None))


class SecurityMiddlewareTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _app()
        self.client = TestClient(self.app, base_url=BASE)

    def _token(self) -> str:
        return str(self.client.get("/api/csrf").json()["token"])

    def test_host_invalide(self) -> None:
        with TestClient(self.app, base_url="http://evil.example") as client:
            response = client.get("/api/health")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_host")

    def test_host_valide_et_entetes(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Content-Security-Policy", response.headers)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_csrf_absent(self) -> None:
        response = self.client.post("/api/_test", json={"x": 1})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "invalid_csrf")

    def test_csrf_valide(self) -> None:
        response = self.client.post(
            "/api/_test",
            json={"x": 1},
            headers={"X-SDLC-CSRF": self._token()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_content_type_non_json(self) -> None:
        response = self.client.post(
            "/api/_test",
            content="x=1",
            headers={"Content-Type": "text/plain", "X-SDLC-CSRF": self._token()},
        )
        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json()["code"], "invalid_content_type")

    def test_origine_externe(self) -> None:
        response = self.client.post(
            "/api/_test",
            json={"x": 1},
            headers={"X-SDLC-CSRF": self._token(), "Origin": "http://evil.example"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "invalid_origin")

    def test_referer_externe(self) -> None:
        response = self.client.post(
            "/api/_test",
            json={"x": 1},
            headers={"X-SDLC-CSRF": self._token(), "Referer": "http://evil.example/page"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "invalid_referer")

    def test_origine_autorisee(self) -> None:
        response = self.client.post(
            "/api/_test",
            json={"x": 1},
            headers={"X-SDLC-CSRF": self._token(), "Origin": "http://127.0.0.2:5173"},
        )
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
