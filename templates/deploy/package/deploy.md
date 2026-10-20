# Déploiement — {{composant}} (profil `package`)

<!-- Procédure destinée à docs/ops/deploy-{{composant}}.md (skill deploy-procedure).
     Remplacer les marqueurs {{…}} puis supprimer les consignes. -->

## 1. Prérequis

- [ ] `scripts/ci.sh` est **vert** (lint, tests, couverture, analyse de code).
- [ ] Le gate **go/no-go** est validé (`gates.go_no_go`).
- [ ] Le **numéro de version** respecte SemVer et est cohérent avec le
      `CHANGELOG` (`{{version}}`).
- [ ] Les identifiants de publication du registre sont disponibles
      (`{{secret-publication}}`), jamais dans le dépôt.
- [ ] La **version candidate** a été validée sur le registre de test
      `{{registre-test}}`.
- [ ] La sauvegarde (§ 5) est assurée (sources committées, artefact local
      conservé).

## 2. Étapes de déploiement

1. Construire l'artefact : `{{commande-build-package}}`.
2. Publier la version candidate sur le registre de test :
   `{{commande-publication-test}}`.
3. Installer et tester depuis le registre de test dans un projet consommateur.
4. Publier la version définitive : `{{commande-publication}}`.
5. Mettre à jour la documentation et le `CHANGELOG` si nécessaire.

## 3. Vérifications

- [ ] La version est visible sur le registre : `{{commande-verification-version}}`.
- [ ] L'installation depuis le registre fonctionne :
      `{{commande-installation-verification}}`.
- [ ] Les métadonnées (licence, description, liens) sont correctes.
- [ ] Aucune dépendance de développement n'est embarquée à tort.

## 4. Rollback

1. **Déprécier** la version fautive : `{{commande-deprecation}}`.
2. Publier une **version corrective** (patch) dès que possible :
   `{{commande-publication}}`.
3. Si le registre autorise la suppression et que le risque le justifie,
   `{{commande-unpublish}}` (usage exceptionnel, documenté dans le `CHANGELOG`).

> Journaliser le rollback avec `result: "rollback"`.

## 5. Sauvegarde

- Vérifier que les sources et le `CHANGELOG` sont committés et poussés.
- Conserver localement l'artefact publié (`{{chemin-artefact}}`) et son empreinte.

## 6. Journalisation

Ajouter une ligne dans `docs/journal/deploys.jsonl`, format § 12 :

```json
{"ts":"{{horodatage-iso-8601}}","env":"production","component":"{{composant}}","version":"{{version}}","result":"success","duration_s":null,"by":"{{operateur-ou-pipeline}}","note":"{{note}}"}
```

`result` ∈ `success` | `rollback` | `failed`. Champs inconnus : `null`.

---

*Responsable : {{responsable}} — Dernière mise à jour : {{date}}*
