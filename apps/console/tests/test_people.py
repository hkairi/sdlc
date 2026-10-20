"""Tests des personnes, identités, fusions et détection des bots."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select

from sdlc_console.db import make_engine, make_session_factory
from sdlc_console.models import AuditEvent, Base, Person, PersonIdentity, PersonMerge
from sdlc_console.services.people import (
    IdentityConflictError,
    PersonError,
    add_identity,
    create_person,
    find_person_by_email,
    find_person_by_external_id,
    is_bot_identity,
    list_persons,
    list_team_persons,
    merge_persons,
    resolve_person,
    unmerge_person,
)
from sdlc_console.services.projects import create_project


class PeopleTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.engine = make_engine(f"sqlite:///{root / 'db.sqlite3'}")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.Session = make_session_factory(self.engine)
        self.session = self.Session()
        self.addCleanup(self.session.close)
        self.project = create_project(self.session, name="Atlas", slug="atlas")
        self.session.commit()

    def _resolve(self, **kwargs: object) -> Person:
        person = resolve_person(self.session, self.project, **kwargs)
        self.session.commit()
        return person

    def test_resolution_par_email_cree_une_personne(self) -> None:
        person = self._resolve(email="Alice@Example.com", display_name="Alice")
        self.assertEqual(person.display_name, "Alice")
        self.assertFalse(person.is_bot)
        self.assertEqual(len(person.identities), 1)
        self.assertEqual(person.identities[0].email, "alice@example.com")
        self.assertEqual(person.identities[0].provider, "email")
        self.assertEqual(find_person_by_email(self.session, self.project, "ALICE@example.com").id, person.id)

    def test_resolution_idempotente_par_email(self) -> None:
        first = self._resolve(email="alice@example.com", display_name="Alice")
        second = self._resolve(email="alice@example.com", display_name="Alice bis")
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(list_persons(self.session, self.project)), 1)
        self.assertEqual(len(second.identities), 1)

    def test_resolution_par_compte_github(self) -> None:
        person = self._resolve(provider="github", external_id="42", display_name="Bob")
        self.assertEqual(person.display_name, "Bob")
        self.assertEqual(len(person.identities), 1)
        identity = person.identities[0]
        self.assertEqual(identity.provider, "github")
        self.assertEqual(identity.external_id, "42")
        self.assertIsNone(identity.email)
        found = find_person_by_external_id(self.session, self.project, "github", "42")
        self.assertEqual(found.id, person.id)

    def test_email_et_compte_dans_une_seule_identite(self) -> None:
        person = self._resolve(
            email="alice@example.com",
            provider="github",
            external_id="42",
            display_name="Alice",
        )
        self.assertEqual(len(person.identities), 1)
        identity = person.identities[0]
        self.assertEqual(identity.provider, "github")
        self.assertEqual(identity.external_id, "42")
        self.assertEqual(identity.email, "alice@example.com")
        self.assertEqual(self._resolve(email="alice@example.com").id, person.id)
        self.assertEqual(
            self._resolve(provider="github", external_id="42").id,
            person.id,
        )

    def test_completion_d_une_identite_existante(self) -> None:
        person = self._resolve(email="alice@example.com", display_name="Alice")
        same = self._resolve(email="alice@example.com", provider="github", external_id="42")
        self.assertEqual(same.id, person.id)
        identities = self.session.scalars(
            select(PersonIdentity).where(PersonIdentity.person_id == person.id)
        ).all()
        self.assertEqual(len(identities), 1)
        self.assertEqual(identities[0].provider, "github")
        self.assertEqual(identities[0].external_id, "42")
        self.assertEqual(identities[0].email, "alice@example.com")

    def test_contributeur_multi_emails_et_comptes(self) -> None:
        person = self._resolve(
            email="alice@example.com",
            provider="github",
            external_id="42",
            display_name="Alice",
        )
        same = self._resolve(email="alice@corp.example", provider="github", external_id="42")
        self.assertEqual(same.id, person.id)
        same = self._resolve(email="alice@example.com", provider="gitlab", external_id="gl-7")
        self.assertEqual(same.id, person.id)

        identities = self.session.scalars(
            select(PersonIdentity).where(PersonIdentity.person_id == person.id)
        ).all()
        emails = {identity.email for identity in identities if identity.email is not None}
        accounts = {
            (identity.provider, identity.external_id)
            for identity in identities
            if identity.external_id is not None
        }
        self.assertEqual(emails, {"alice@example.com", "alice@corp.example"})
        self.assertEqual(accounts, {("github", "42"), ("gitlab", "gl-7")})
        self.assertEqual(find_person_by_email(self.session, self.project, "alice@corp.example").id, person.id)
        self.assertEqual(find_person_by_external_id(self.session, self.project, "gitlab", "gl-7").id, person.id)

    def test_bots_exclus_des_metriques_d_equipe(self) -> None:
        human = self._resolve(email="alice@example.com", display_name="Alice")
        self._resolve(email="dependabot[bot]@users.noreply.github.com")
        self.assertEqual([person.id for person in list_team_persons(self.session, self.project)], [human.id])
        self.assertEqual(len(list_persons(self.session, self.project)), 2)

    def test_conflit_email_et_compte(self) -> None:
        self._resolve(email="alice@example.com", display_name="Alice")
        self._resolve(provider="github", external_id="42", display_name="Bob")
        with self.assertRaises(IdentityConflictError):
            resolve_person(
                self.session,
                self.project,
                email="alice@example.com",
                provider="github",
                external_id="42",
            )

    def test_meme_email_dans_deux_projets(self) -> None:
        other = create_project(self.session, name="Borealis", slug="borealis")
        self.session.commit()
        first = self._resolve(email="alice@example.com", display_name="Alice")
        second = resolve_person(self.session, other, email="alice@example.com", display_name="Alice")
        self.session.commit()
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.project_id, self.project.id)
        self.assertEqual(second.project_id, other.id)

    def test_email_unique_dans_un_projet(self) -> None:
        first = self._resolve(email="alice@example.com", display_name="Alice")
        other = create_person(self.session, self.project, display_name="Alice bis")
        self.session.commit()
        with self.assertRaises(IdentityConflictError):
            add_identity(self.session, other, email="ALICE@example.com")
        self.assertEqual(find_person_by_email(self.session, self.project, "alice@example.com").id, first.id)

    def test_noms_identiques_autorises(self) -> None:
        create_person(self.session, self.project, display_name="Alex")
        create_person(self.session, self.project, display_name="Alex")
        self.session.commit()
        self.assertEqual(len(list_persons(self.session, self.project)), 2)

    def test_fusion_et_defusion(self) -> None:
        source = self._resolve(email="alice@example.com", display_name="Alice")
        target = self._resolve(
            provider="github",
            external_id="42",
            email="alice@corp.example",
            display_name="Alice Corp",
        )
        source_identity_ids = [identity.id for identity in source.identities]
        merge = merge_persons(self.session, source, target, reason="même personne")
        self.session.commit()

        self.assertEqual(source.superseded_by_person_id, target.id)
        self.assertEqual(merge.source_person_id, source.id)
        self.assertEqual(merge.target_person_id, target.id)
        self.assertIsNone(merge.undone_at)
        self.assertEqual(json.loads(merge.identity_ids_json), source_identity_ids)

        identities = self.session.scalars(
            select(PersonIdentity).where(PersonIdentity.id.in_(source_identity_ids))
        ).all()
        self.assertTrue(all(identity.person_id == target.id for identity in identities))
        self.assertEqual([person.id for person in list_persons(self.session, self.project)], [target.id])
        self.assertEqual(len(list_persons(self.session, self.project, include_merged=True)), 2)

        unmerge_person(self.session, source)
        self.session.commit()
        self.assertIsNone(source.superseded_by_person_id)
        self.assertIsNotNone(merge.undone_at)
        identities = self.session.scalars(
            select(PersonIdentity).where(PersonIdentity.id.in_(source_identity_ids))
        ).all()
        self.assertTrue(all(identity.person_id == source.id for identity in identities))
        self.assertEqual(len(list_persons(self.session, self.project)), 2)

    def test_fusion_ecrit_un_evenement_d_audit(self) -> None:
        source = self._resolve(email="alice@example.com", display_name="Alice")
        target = self._resolve(email="bob@example.com", display_name="Bob")
        merge = merge_persons(self.session, source, target, reason="doublon")
        self.session.commit()

        events = self.session.scalars(select(AuditEvent).order_by(AuditEvent.id)).all()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.action, "person.merge")
        self.assertEqual(event.project_id, self.project.id)
        self.assertEqual(event.object_id, str(source.id))
        self.assertEqual(event.generation, 1)
        self.assertEqual(event.prev_hash, "")
        self.assertEqual(len(event.hash), 64)
        payload = json.loads(event.payload_json)
        self.assertEqual(payload["merge_id"], merge.id)
        self.assertEqual(payload["source_person_id"], source.id)
        self.assertEqual(payload["target_person_id"], target.id)
        self.assertEqual(payload["reason"], "doublon")

        unmerge_person(self.session, source)
        self.session.commit()
        events = self.session.scalars(select(AuditEvent).order_by(AuditEvent.id)).all()
        self.assertEqual(len(events), 2)
        unmerge_event = events[1]
        self.assertEqual(unmerge_event.action, "person.unmerge")
        self.assertEqual(unmerge_event.prev_hash, event.hash)
        self.assertEqual(unmerge_event.generation, 1)
        self.assertEqual(len(unmerge_event.hash), 64)
        self.assertNotEqual(unmerge_event.hash, event.hash)

    def test_fusion_refusee_avec_soi_meme(self) -> None:
        person = self._resolve(email="alice@example.com", display_name="Alice")
        with self.assertRaises(PersonError):
            merge_persons(self.session, person, person)

    def test_fusion_refusee_entre_projets(self) -> None:
        other = create_project(self.session, name="Borealis", slug="borealis")
        self.session.commit()
        source = self._resolve(email="alice@example.com", display_name="Alice")
        target = resolve_person(self.session, other, email="bob@example.com", display_name="Bob")
        self.session.commit()
        with self.assertRaises(PersonError):
            merge_persons(self.session, source, target)

    def test_defusion_sans_fusion_refusee(self) -> None:
        person = self._resolve(email="alice@example.com", display_name="Alice")
        with self.assertRaises(PersonError):
            unmerge_person(self.session, person)

    def test_detection_des_bots(self) -> None:
        self.assertTrue(is_bot_identity("dependabot[bot]@users.noreply.github.com", "dependabot[bot]"))
        self.assertTrue(is_bot_identity("github-actions[bot]@users.noreply.github.com"))
        self.assertTrue(is_bot_identity("bot@example.com"))
        self.assertTrue(is_bot_identity("renovate@example.com"))
        self.assertFalse(is_bot_identity("robot@example.com", "Robert"))
        self.assertFalse(is_bot_identity("alice@example.com", "Alice"))

    def test_personne_bot_marquee(self) -> None:
        person = self._resolve(email="github-actions[bot]@users.noreply.github.com")
        self.assertTrue(person.is_bot)
        human = self._resolve(email="alice@example.com", display_name="Alice")
        self.assertFalse(human.is_bot)

    def test_person_merge_persistee(self) -> None:
        source = self._resolve(email="alice@example.com", display_name="Alice")
        target = self._resolve(email="bob@example.com", display_name="Bob")
        merge = merge_persons(self.session, source, target, reason="doublon")
        self.session.commit()
        stored = self.session.scalars(select(PersonMerge)).one()
        self.assertEqual(stored.id, merge.id)
        self.assertEqual(stored.reason, "doublon")


if __name__ == "__main__":
    unittest.main()
