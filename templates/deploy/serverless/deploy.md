# Déploiement — {{composant}} (profil `serverless`)

<!-- Procédure destinée à docs/ops/deploy-{{composant}}.md (skill deploy-procedure).
     Remplacer les marqueurs {{…}} puis supprimer les consignes. -->

## 1. Prérequis

- [ ] `scripts/ci.sh` est **vert**.
- [ ] Le gate **go/no-go** est validé (`gates.go_no_go`).
- [ ] L'infrastructure est décrite en IaC (`{{chemin-iac}}`) et à jour.
- [ ] Les identifiants de déploiement sont disponibles (profil cloud
      `{{profil-identifiants}}`), jamais dans le dépôt.
- [ ] Le stage de préproduction `{{stage-preprod}}` est déployé et testé.
- [ ] La **version de production précédente** est identifiée
      (`{{version-precedente}}`) pour le rollback d'alias.
- [ ] La sauvegarde des données managées est active (§ 5).

## 2. Étapes de déploiement

1. Empaqueter les fonctions : `{{commande-package}}`.
2. Déployer en préproduction : `{{commande-deploiement-preprod}}`.
3. Tester la préproduction (voir § 3 sur `{{url-sante-preprod}}`).
4. Déployer en production : `{{commande-deploiement-production}}`.
5. Faire pointer l'alias de production sur la nouvelle version :
   `{{commande-alias-production}}`.

## 3. Vérifications

- [ ] L'invocation de la fonction de santé répond :
      `{{commande-invocation-sante}}`.
- [ ] Les journaux ne montrent pas d'erreur : `{{commande-journaux}}`.
- [ ] Parcours critique OK : `{{parcours-critique}}`.
- [ ] Aucun événement perdu : la DLQ `{{nom-dlq}}` est vide.
- [ ] La version active est la bonne : `{{commande-verification-version}}`.

## 4. Rollback

1. Repointer l'alias sur la version précédente :
   `{{commande-rollback-alias}}`.
2. Si une migration de données est en cause, restaurer depuis la sauvegarde (§ 5).
3. Rejouer le § 3.

> Journaliser le rollback avec `result: "rollback"`.

## 5. Sauvegarde

- Vérifier la sauvegarde à point dans le temps des services de données :
  `{{commande-verification-sauvegardes}}`.
- Exporter la configuration des déclencheurs et files si elle n'est pas en IaC.

## 6. Journalisation

Ajouter une ligne dans `docs/journal/deploys.jsonl`, format § 12 :

```json
{"ts":"{{horodatage-iso-8601}}","env":"production","component":"{{composant}}","version":"{{version}}","result":"success","duration_s":null,"by":"{{operateur-ou-pipeline}}","note":"{{note}}"}
```

`result` ∈ `success` | `rollback` | `failed`. Champs inconnus : `null`.

---

*Responsable : {{responsable}} — Dernière mise à jour : {{date}}*
