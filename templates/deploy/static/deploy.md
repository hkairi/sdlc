# Déploiement — {{composant}} (profil `static`)

<!-- Procédure destinée à docs/ops/deploy-{{composant}}.md (skill deploy-procedure).
     Remplacer les marqueurs {{…}} puis supprimer les consignes. -->

## 1. Prérequis

- [ ] `scripts/ci.sh` est **vert** (lint, tests, build).
- [ ] Le gate **go/no-go** est validé (`gates.go_no_go`).
- [ ] L'artefact statique a été construit : `{{commande-build}}`.
- [ ] L'URL de préproduction est disponible et a été vérifiée.
- [ ] Les redirections et en-têtes (`{{fichier-config-hebergeur}}`) sont à jour.
- [ ] La sauvegarde (§ 5) est assurée : sources committées, artefact précédent
      identifié (`{{version-precedente}}`).

## 2. Étapes de déploiement

1. Construire l'artefact : `{{commande-build}}`.
2. Publier en préproduction : `{{commande-publication-preprod}}`.
3. Ouvrir `{{url-preprod}}` et vérifier (§ 3).
4. Promouvoir le même artefact en production :
   `{{commande-publication-production}}`.
5. Invalider le cache CDN : `{{commande-invalidation-cdn}}`.

## 3. Vérifications

- [ ] La page d'accueil répond : `curl -fsS {{url-production}}`.
- [ ] Les en-têtes de sécurité sont présents :
      `curl -sSI {{url-production}} | grep -iE 'content-security-policy|strict-transport-security'`.
- [ ] Les ressources critiques (CSS/JS) sont servies et non obsolètes.
- [ ] Les redirections fonctionnent (`{{redirection-test}}`).
- [ ] Le certificat TLS est valide : `{{domaine}}`.

## 4. Rollback

1. Repartir de l'artefact ou du commit précédent : `{{version-precedente}}`.
2. Republier : `{{commande-publication-production}}`.
3. Invalider le cache CDN : `{{commande-invalidation-cdn}}`.

> Journaliser le rollback avec `result: "rollback"`.

## 5. Sauvegarde

- Vérifier que les sources sont bien committées et poussées (aucune modification
  hors dépôt).
- Conserver l'artefact publié du déploiement courant (tag de release).
- Exporter les règles CDN/redirections si elles sont configurées hors dépôt.

## 6. Journalisation

Ajouter une ligne dans `docs/journal/deploys.jsonl`, format § 12 :

```json
{"ts":"{{horodatage-iso-8601}}","env":"production","component":"{{composant}}","version":"{{version}}","result":"success","duration_s":null,"by":"{{operateur-ou-pipeline}}","note":"{{note}}"}
```

`result` ∈ `success` | `rollback` | `failed`. Champs inconnus : `null`.

---

*Responsable : {{responsable}} — Dernière mise à jour : {{date}}*
