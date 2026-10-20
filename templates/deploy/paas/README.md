# Profil `paas` — plateforme applicative managée

## Quand le choisir

Quand l'application est déployée sur une **plateforme managée** qui gère le
build, les certificats, le routage et la mise à l'échelle (Heroku, Scalingo,
Render, Railway, Fly.io, Clever Cloud…). Profil adapté pour livrer vite sans
administrer de serveur.

## Préproduction

Créer une **application de préproduction** distincte sur la plateforme
(`{{app-preprod}}`) :

- mêmes variables de configuration, valeurs et secrets distincts ;
- base de données de préproduction (souvent un addon) ;
- déployer d'abord sur la préproduction, puis promouvoir l'artefact identique
  vers la production.

## Stratégie de rollback

- Les plateformes PaaS conservent un **historique de releases** : revenir à la
  release précédente est une opération native
  (ex. `{{commande-rollback-release}}`).
- Alternative : redéployer le commit de `{{version-precedente}}`.
- Les migrations de base doivent rester rétrocompatibles (déployer le schéma
  avant/après le code).

## Sauvegarde

- **Base de données** : activer les sauvegardes de l'addon managé et vérifier
  leur rétention. Avant migration, faire un export additionnel
  (`{{commande-export-base}}`).
- **Configuration** : les variables vivent dans l'interface/CLI de la
  plateforme ; en conserver une trace (hors secrets).
- Le code vient du dépôt : ne pas compter sur la plateforme comme source de
  vérité.

## Points d'attention

- Les plateformes redémarrent l'app à chaque déploiement : prévoir une courte
  interruption ou un déploiement sans coupure si disponible.
- Surveiller les quotas (temps de build, connexions base, bande passante).
