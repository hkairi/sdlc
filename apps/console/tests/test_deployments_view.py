"""Tests de la vue Déploiements et de la checklist go/no-go."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_console.app import create_app
from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Deployment
from sdlc_console.services.deployments_view import build_deployments_view
from sdlc_console.services.gates import ControlResult, Evidence, run_gate
from sdlc_console.services.projects import create_project


class DeploymentsViewTest(unittest.TestCase):
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
        (self.root / "reports" / "gates").mkdir(parents=True)
        (self.root / "reports" / "gates" / "evidence.txt").write_text("ok\n")
        (self.root / "docs" / "recette").mkdir(parents=True)
        (self.root / "docs" / "recette" / "matrice.md").write_text("# Recette\n")
        self.now = datetime.now(UTC)
        for index, env in enumerate(("dev", "preprod", "prod", "prod")):
            self.session.add(
                Deployment(
                    project_id=self.project.id,
                    deploy_id=f"deploy-{index}",
                    env=env,
                    version=f"v{index}",
                    status="rollback" if index == 3 else "success",
                    is_rollback=index == 3,
                    rollback_of_version="v2" if index == 3 else None,
                    started_at=self.now - timedelta(days=3 - index),
                    note=None,
                    imported_at=self.now,
                )
            )
        self.session.commit()

    def _gate(self, key: str, *, fail: bool = False) -> None:
        control = ControlResult(
            key="control",
            verdict="fail" if fail else "pass",
            reason="échec de test" if fail else "preuve fournie",
            evidence=(Evidence(path="reports/gates/evidence.txt", kind="report"),),
        )
        run_gate(
            self.session,
            self.project,
            key,
            [control],
            gate_name=key,
            root=self.root,
        )
        self.session.commit()

    def test_vue_deploiements_dora_et_go_no_go(self) -> None:
        for key in ("tests", "coverage", "security", "performance", "data"):
            self._gate(key)
        view = build_deployments_view(
            self.session,
            self.project,
            root=self.root,
            limit=2,
            offset=0,
        )
        self.assertEqual(view["environments"]["dev"]["count"], 1)
        self.assertEqual(view["environments"]["preprod"]["count"], 1)
        self.assertEqual(view["environments"]["prod"]["count"], 2)
        self.assertEqual(view["total"], 4)
        self.assertEqual(len(view["history"]), 2)
        self.assertTrue(view["has_more"])
        self.assertEqual(len(view["rollbacks"]), 1)
        self.assertEqual(view["rollbacks"][0]["rollback_of_version"], "v2")
        cfr = next(
            metric for metric in view["dora"]["metrics"] if metric["key"] == "change_failure_rate"
        )
        self.assertEqual(cfr["status"], "measured")
        self.assertEqual(view["go_no_go"]["verdict"], "go")
        self.assertTrue(all(item["evidence"] for item in view["go_no_go"]["checklist"]))

    def test_gate_en_echec_bloque_go(self) -> None:
        for key in ("tests", "coverage", "security", "performance", "data"):
            self._gate(key)
        self._gate("security", fail=True)
        view = build_deployments_view(self.session, self.project, root=self.root)
        self.assertEqual(view["go_no_go"]["verdict"], "no-go")
        self.assertTrue(
            any(item["key"] == "security" for item in view["go_no_go"]["conditions"])
        )

    def test_api_deploiements_filtre_et_go_no_go(self) -> None:
        for key in ("tests", "coverage", "security", "performance", "data"):
            self._gate(key)
        app = create_app(
            allowed_hosts={"127.0.0.2"},
            session_factory=self.Session,
            docs_dir=self.root / "docs",
            project_root=self.root,
            watcher_enabled=False,
        )
        client = TestClient(app, base_url="http://127.0.0.2")
        response = client.get(
            f"/api/projects/{self.project.id}/deployments?env=prod&limit=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)
        self.assertEqual(len(response.json()["history"]), 1)
        self.assertEqual(response.json()["history"][0]["environment"], "prod")
        go = client.get(f"/api/projects/{self.project.id}/go-no-go")
        self.assertEqual(go.status_code, 200)
        self.assertEqual(go.json()["go_no_go"]["verdict"], "go")


if __name__ == "__main__":
    unittest.main()
