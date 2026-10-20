# Déploiement — {{composant}} (profil `paas`)

<!-- Procédure destinée à docs/ops/deploy-{{composant}}.md (skill deploy-procedure).
     Remplacer les marqueurs {{…}} puis supprimer les consignes. -->

## 1. Prérequis

- [ ] `scripts/ci.sh` est **vert**.
- [ ] Le gate **go/no-go** est validé (`gates.go_no_go`).
- [ ] L'application de préproduction `{{app-preprod}}` a été testée avec succès.
- [ ] La plateforme est accessible (CLI authentifiée : `{{commande-login}}`).
- [ ] Les variables d'environnement de production sont à jour.
- [ ] La **sauvegarde de la base** a été faite (§ 5) si une migration est prévue.
- [ ] La release précédente est identifiée (`{{release-precedente}}`) pour le
      rollback.

## 2. Étapes de déploiement

1. Construire/valider l'artefact : `{{commande-build}}`.
2. Déployer d'abord en préproduction : `{{commande-deploiement-preprod}}`.
3. Vérifier la préproduction (voir § 3 sur `{{url-sante-preprod}}`).
4. Déployer en production : `{{commande-deploiement-production}}`.
5. Exécuter les migrations : `{{commande-migration}}`.

## 3. Vérifications

- [ ] Le déploiement est `succeeded` dans la plateforme.
- [ ] La route de santé répond : `curl -fsS {{url-sante}}`.
- [ ] Les journaux ne montrent pas d'erreur : `{{commande-journaux}}`.
- [ ] Parcours critique OK : `{{parcours-critique}}`.
- [ ] La version déployée est la bonne : `{{commande-verification-version}}`.

## 4. Rollback

1. Revenir à la release précédente : `{{commande-rollback-release}}`.
2. Si une migration est en cause, restaurer la base depuis la sauvegarde (§ 5).
3. Rejouer le § 3.

> Journaliser le rollback avec `result: "rollback"`.

## 5. Sauvegarde

1. Vérifier que les sauvegardes automatiques de l'addon sont actives et
   récentes : `{{commande-verification-sauvegardes}}`.
2. Faire un export ponctuel avant migration :
   `{{commande-export-base}}`.

## 6. Journalisation

Ajouter une ligne dans `docs/journal/deploys.jsonl`, format § 12 :

```json
{"ts":"{{horodatage-iso-8601}}","env":"production","component":"{{composant}}","version":"{{version}}","result":"success","duration_s":null,"by":"{{operateur-ou-pipeline}}","note":"{{note}}"}
```

`result` ∈ `success` | `rollback` | `failed`. Champs inconnus : `null`.

---

*Responsable : {{responsable}} — Dernière mise à jour : {{date}}*
