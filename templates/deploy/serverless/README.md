# Profil `serverless` — fonctions managées

## Quand le choisir

Quand le livrable est composé de **fonctions managées** déclenchées par des
événements (AWS Lambda, Google Cloud Functions, Cloudflare Workers, Azure
Functions…) avec une infrastructure décrite en IaC (Serverless Framework, SAM,
SST, Terraform…). Profil adapté aux charges irrégulières et aux API événementielles.

## Préproduction

Déployer sur un **stage** ou un ensemble de fonctions distinct
(`{{stage-preprod}}`) :

- mêmes définitions IaC, variables et ressources distinctes ;
- données de test isolées ;
- déployer puis tester en préproduction avant de promouvoir en production.

## Stratégie de rollback

- Déployer en publiant des **versions immuables** de fonctions et un **alias**
  (`{{alias-production}}`) pointant la version active.
- Rollback = repointer l'alias sur la version précédente
  (`{{commande-rollback-alias}}`), sans redéployer de code.
- Conserver les N dernières versions de chaque fonction.

## Sauvegarde

- Les fonctions sont décrites en IaC (dépôt) : c'est la sauvegarde du code.
- Les **données** vivent dans des services managés : activer la sauvegarde à
  point dans le temps (PITR) et les exports.
- Sauvegarder la configuration des déclencheurs (événements, files, DLQ).

## Points d'attention

- Surveiller les temps de démarrage à froid (cold start) et le dimensionnement
  mémoire (qui influe sur le CPU).
- Configurer une **file de lettres mortes (DLQ)** pour les événements en échec.
- Maîtriser les coûts : les invocations et la durée se paient à l'usage.
