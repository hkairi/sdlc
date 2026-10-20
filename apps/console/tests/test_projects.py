"""Tests des services projets et dépôts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import Base, Repository
from sdlc_console.services.projects import (
    RepositoryError,
    add_repository,
    create_project,
    delete_repository,
    get_primary_repository,
    list_repositories,
    retire_repository,
    set_primary_repository,
)


def _make_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").mkdir(exist_ok=True)
    return path


class ProjectsTest(unittest.TestCase):
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

    def _add(self, name: str, *, primary: bool = False, **kwargs: object) -> Repository:
        path = _make_git_repo(self.root / name)
        return add_repository(
            self.session,
            self.project,
            name=name,
            provider="github",
            url=f"https://github.com/hm/{name}",
            local_path=path,
            is_primary=primary,
            **kwargs,
        )

    def test_premier_depot_principal(self) -> None:
        first = self._add("api")
        self.session.commit()
        self.assertTrue(first.is_primary)
        self.assertEqual(get_primary_repository(self.session, self.project).id, first.id)

    def test_second_depot_non_principal(self) -> None:
        first = self._add("api")
        second = self._add("web")
        self.session.commit()
        self.assertTrue(first.is_primary)
        self.assertFalse(second.is_primary)
        self.assertEqual(len(list_repositories(self.session, self.project)), 2)

    def test_changement_de_principal(self) -> None:
        first = self._add("api")
        second = self._add("web")
        self.session.commit()
        set_primary_repository(self.session, second)
        self.session.commit()
        self.assertFalse(first.is_primary)
        self.assertTrue(second.is_primary)
        primaries = [repo for repo in list_repositories(self.session, self.project) if repo.is_primary]
        self.assertEqual(len(primaries), 1)

    def test_retrait_du_principal_reelit(self) -> None:
        first = self._add("api")
        second = self._add("web")
        self.session.commit()
        retire_repository(self.session, first)
        self.session.commit()
        self.assertIsNotNone(first.retired_at)
        self.assertTrue(second.is_primary)
        self.assertEqual([repo.id for repo in list_repositories(self.session, self.project)], [second.id])
        self.assertEqual(len(list_repositories(self.session, self.project, include_retired=True)), 2)

    def test_refus_retrait_dernier_depot(self) -> None:
        self._add("api")
        self.session.commit()
        with self.assertRaises(RepositoryError):
            retire_repository(self.session, get_primary_repository(self.session, self.project))

    def test_suppression_du_principal_reelit(self) -> None:
        first = self._add("api")
        second = self._add("web")
        self.session.commit()
        delete_repository(self.session, first, confirm=True)
        self.session.commit()
        self.assertTrue(second.is_primary)
        self.assertEqual([repo.id for repo in list_repositories(self.session, self.project)], [second.id])

    def test_refus_suppression_dernier_depot(self) -> None:
        self._add("api")
        self.session.commit()
        with self.assertRaises(RepositoryError):
            delete_repository(
                self.session,
                get_primary_repository(self.session, self.project),
                confirm=True,
            )

    def test_refus_suppression_sans_confirmation(self) -> None:
        first = self._add("api")
        self._add("web")
        self.session.commit()
        with self.assertRaises(RepositoryError):
            delete_repository(self.session, first)
        self.session.commit()
        self.assertEqual(len(list_repositories(self.session, self.project, include_retired=True)), 2)

    def test_doublon_nom(self) -> None:
        self._add("api")
        self.session.commit()
        with self.assertRaises(IntegrityError):
            self._add("api")
            self.session.commit()

    def test_fournisseur_invalide(self) -> None:
        path = _make_git_repo(self.root / "api")
        with self.assertRaises(RepositoryError):
            add_repository(
                self.session,
                self.project,
                name="api",
                provider="bitbucket",
                url="https://bitbucket.org/hm/api",
                local_path=path,
            )

    def test_chemin_non_git(self) -> None:
        path = self.root / "pas-git"
        path.mkdir()
        with self.assertRaises(RepositoryError):
            add_repository(
                self.session,
                self.project,
                name="pas-git",
                provider="github",
                url="https://github.com/hm/pas-git",
                local_path=path,
            )

    def test_dedup_group_et_miroir(self) -> None:
        repo = self._add("api", dedup_group="groupe-api", is_mirror=True, is_fork=True)
        self.session.commit()
        self.assertEqual(repo.dedup_group, "groupe-api")
        self.assertTrue(repo.is_mirror)
        self.assertTrue(repo.is_fork)


if __name__ == "__main__":
    unittest.main()
