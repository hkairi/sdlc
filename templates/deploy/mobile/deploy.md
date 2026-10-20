# Déploiement — {{composant}} (profil `mobile`)

<!-- Procédure destinée à docs/ops/deploy-{{composant}}.md (skill deploy-procedure).
     Remplacer les marqueurs {{…}} puis supprimer les consignes. -->

## 1. Prérequis

- [ ] `scripts/ci.sh` est **vert** (lint, tests, build).
- [ ] Le gate **go/no-go** est validé (`gates.go_no_go`).
- [ ] Le **numéro de version** et le **numéro de build** sont incrémentés
      (`{{version}}`, build `{{numero-build}}`).
- [ ] Les **clés de signature** sont disponibles (hors dépôt).
- [ ] Les notes de version (`release-notes`) sont rédigées.
- [ ] L'API serveur requise est **déjà en production** et rétrocompatible.
- [ ] Le mécanisme d'**indicateur de fonctionnalité** `{{indicateur-fonctionnalite}}`
      est disponible pour un rollback fonctionnel.
- [ ] La sauvegarde (§ 5) est assurée (sources, artefacts, clés).

## 2. Étapes de déploiement

1. Construire et signer l'artefact : `{{commande-build-signature}}`.
2. Publier sur le **canal de test** : `{{commande-canaux-beta}}`.
3. Valider sur appareils/appareils de recette `{{matrice-appareils}}`.
4. Soumettre la version au magasin : `{{commande-soumission}}`.
5. Une fois la revue acceptée, **publier** vers la production (déploiement
   progressif : `{{pourcentage-deploiement-progressif}}`).

## 3. Vérifications

- [ ] Le build installé démarre sans crash sur les appareils de référence.
- [ ] Le parcours critique fonctionne : `{{parcours-critique}}`.
- [ ] Les indicateurs de plantage sont stables après publication :
      `{{tableau-de-bord-crashs}}`.
- [ ] La version visible dans le magasin est la bonne (`{{version}}`).

## 4. Rollback

1. **Fonctionnel** : désactiver la fonctionnalité défectueuse via
   `{{indicateur-fonctionnalite}}` (immédiat, sans mise à jour).
2. **Publication corrective** : préparer et soumettre un correctif
   (voir la voie transverse `hotfix`) ; augmenter le numéro de build.
3. Stopper un déploiement progressif si la plateforme le permet
   (`{{commande-arret-deploiement-progressif}}`).

> Journaliser le rollback avec `result: "rollback"`.

## 5. Sauvegarde

- Vérifier que les sources sont committées et poussées.
- Conserver l'artefact signé de la version précédente dans
  `{{registre-builds}}`.
- Confirmer la disponibilité des clés de signature et de leur procédure de
  restauration.

## 6. Journalisation

Ajouter une ligne dans `docs/journal/deploys.jsonl`, format § 12 :

```json
{"ts":"{{horodatage-iso-8601}}","env":"production","component":"{{composant}}","version":"{{version}}","result":"success","duration_s":null,"by":"{{operateur-ou-pipeline}}","note":"{{note}}"}
```

`result` ∈ `success` | `rollback` | `failed`. Champs inconnus : `null`.

---

*Responsable : {{responsable}} — Dernière mise à jour : {{date}}*
