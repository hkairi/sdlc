# Déploiement — {{composant}} (profil `kubernetes`)

<!-- Procédure destinée à docs/ops/deploy-{{composant}}.md (skill deploy-procedure).
     Remplacer les marqueurs {{…}} puis supprimer les consignes. -->

## 1. Prérequis

- [ ] `scripts/ci.sh` est **vert** (contrôles bloquants compris).
- [ ] Le gate **go/no-go** est validé (`gates.go_no_go`).
- [ ] L'image est construite et poussée avec un **tag immuable** :
      `{{registry}}/{{composant}}:{{version}}`.
- [ ] Le contexte kubectl pointe le bon cluster : `kubectl config current-context`
      = `{{contexte-cluster}}`.
- [ ] Les manifests sont à jour dans le dépôt (`{{chemin-manifests}}`).
- [ ] Les **Secrets** requis existent dans le namespace `{{namespace}}`.
- [ ] La **sauvegarde** de la base et des volumes a été faite (§ 5) si migration.

## 2. Étapes de déploiement

1. Vérifier le contexte : `kubectl config current-context`.
2. Mettre à jour le tag d'image dans les manifests (`{{fichier-image}}`).
3. Appliquer les manifests :
   - `kubectl apply -k {{overlay-namespace}}` (Kustomize), ou
   - `helm upgrade --install {{release}} {{chart}} -n {{namespace}} -f {{values}}`.
4. Exécuter les migrations (si nécessaire) via un Job :
   `kubectl apply -f {{job-migration}}` puis suivre sa fin.
5. Suivre le rollout : `kubectl rollout status deployment/{{composant}} -n {{namespace}}`.

## 3. Vérifications

- [ ] `kubectl rollout status` se termine sans erreur.
- [ ] Les pods sont `Running` et les sondes passent :
      `kubectl get pods -n {{namespace}} -l app={{composant}}`.
- [ ] La route de santé répond : `curl -fsS {{url-sante}}`.
- [ ] Parcours critique OK : `{{parcours-critique}}`.
- [ ] Aucun événement anormal : `kubectl get events -n {{namespace}} --sort-by=.lastTimestamp`.

## 4. Rollback

1. Rollback du déploiement :
   `kubectl rollout undo deployment/{{composant}} -n {{namespace}}`
   (ou `helm rollback {{release}} {{revision-precedente}} -n {{namespace}}`).
2. Annuler la migration, ou restaurer la base depuis la sauvegarde (§ 5).
3. Rejouer le § 3.

> Journaliser le rollback avec `result: "rollback"`.

## 5. Sauvegarde

- Base de données : dump chiffré avant migration
  (`{{commande-dump-base}}`), conservé hors cluster.
- Volumes : `{{commande-sauvegarde-volumes}}` (Velero ou snapshot).

## 6. Journalisation

Ajouter une ligne dans `docs/journal/deploys.jsonl`, format § 12 :

```json
{"ts":"{{horodatage-iso-8601}}","env":"production","component":"{{composant}}","version":"{{version}}","result":"success","duration_s":null,"by":"{{operateur-ou-pipeline}}","note":"{{note}}"}
```

`result` ∈ `success` | `rollback` | `failed`. Champs inconnus : `null`.

---

*Responsable : {{responsable}} — Dernière mise à jour : {{date}}*
