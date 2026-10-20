# Déploiement — {{composant}} (profil `vps-compose`)

<!-- Procédure destinée à docs/ops/deploy-{{composant}}.md (skill deploy-procedure).
     Remplacer les marqueurs {{…}} par les valeurs du projet, puis supprimer les
     consignes en commentaire. -->

## 1. Prérequis

- [ ] La tâche de contrôles `scripts/ci.sh` est **verte** (lint, tests,
      couverture ≥ `ci.coverage_min`, aucune vulnérabilité bloquante).
- [ ] Le gate **go/no-go** est validé par le responsable (`gates.go_no_go`).
- [ ] L'artefact est construit et **taggé de façon immuable** :
      `{{composant}}:{{version}}`.
- [ ] L'accès SSH à l'hôte `{{hote}}` est disponible.
- [ ] Le fichier `compose.yml` de production est à jour dans le dépôt.
- [ ] La **sauvegarde de la base** a été faite (voir § 5), si une migration est
      prévue.
- [ ] Le plan de rollback (§ 4) est confirmé : tag précédent connu
      (`{{version-precedente}}`).

## 2. Étapes de déploiement

1. Se connecter à l'hôte : `ssh {{utilisateur}}@{{hote}}`.
2. Se placer dans le répertoire de la pile : `cd {{repertoire-compose}}`.
3. Récupérer le nouveau fichier `compose.yml` (ou la variable de tag mise à
   jour) : `{{commande-recuperation-compose}}`.
4. Mettre à jour le tag dans l'environnement : `{{composant}}_TAG={{version}}`.
5. Télécharger l'image : `docker compose pull {{composant}}`.
6. Appliquer les migrations (si nécessaire) : `{{commande-migration}}`.
7. Redémarrer les services : `docker compose up -d`.
8. Vérifier l'état : `docker compose ps`.

## 3. Vérifications

- [ ] Tous les conteneurs sont `Up` ou `Up (healthy)` : `docker compose ps`.
- [ ] Les journaux ne montrent pas d'erreur : `docker compose logs --since 5m {{composant}}`.
- [ ] La route de santé répond : `curl -fsS {{url-sante}}`.
- [ ] Un parcours critique manuel fonctionne : `{{parcours-critique}}`.
- [ ] La version déployée est la bonne : `{{commande-verification-version}}`.

## 4. Rollback

1. Repasser le tag sur la version précédente :
   `{{composant}}_TAG={{version-precedente}}`.
2. Relancer : `docker compose up -d`.
3. Si une migration est en cause, restaurer la base depuis la sauvegarde (§ 5).
4. Rejouer les vérifications du § 3.

> Le rollback est un déploiement : il est journalisé avec `result: "rollback"`.

## 5. Sauvegarde

Avant toute migration de schéma, exécuter la skill **`vps-db-backup`** :

```sh
# dump chiffré + envoi vers Bunny Storage + rétention
{{commande-de-sauvegarde-vps-db-backup}}
```

Vérifier la fraîcheur et l'intégrité avant de migrer (la skill fournit
`--list` / `--verify` / `--status`).

## 6. Journalisation

Ajouter une ligne (une par déploiement) dans `docs/journal/deploys.jsonl`,
format § 12 :

```json
{"ts":"{{horodatage-iso-8601}}","env":"production","component":"{{composant}}","version":"{{version}}","result":"success","duration_s":null,"by":"{{operateur-ou-pipeline}}","note":"{{note}}"}
```

`result` ∈ `success` | `rollback` | `failed`. Les champs inconnus valent `null`,
jamais une valeur inventée.

---

*Responsable : {{responsable}} — Dernière mise à jour : {{date}}*
