# Profil `vps-compose` — Docker Compose sur machine virtuelle

## Quand le choisir

Quand l'application est conteneurisée (`Dockerfile`, `compose.yml`) et tourne
sur une ou plusieurs machines virtuelles administrées par l'équipe (VPS, serveur
dédié). Profil adapté aux petites et moyennes applications, à un coût maîtrisé,
sans orchestration Kubernetes. C'est le profil des projets de type « api
conteneurisée + base de données » hébergés sur un VPS.

## Préproduction

Prévoir une **seconde pile Compose** isolée sur le même hôte (ports et noms de
projets distincts) ou un **VPS de préproduction** dédié :

- variables d'environnement distinctes (jamais les mêmes secrets qu'en
  production) ;
- base de données de préproduction, restaurée depuis une sauvegarde récente de
  production si nécessaire ;
- mêmes images qu'en production, identifiées par un **tag immuable** (jamais
  `latest` en production).

## Stratégie de rollback

- Déployer par **tag d'image immuable** (`{{composant}}:vX.Y.Z`).
- Conserver les N dernières images sur l'hôte (`docker image prune` maîtrisé).
- Revenir en arrière = repointer la variable de tag vers la version précédente
  puis `docker compose up -d` (voir `deploy.md`).
- La base de données suit une procédure de **migration réversible** ou une
  restauration depuis la sauvegarde faite avant migration.

## Sauvegarde

**Avant toute migration de schéma ou déploiement risqué**, effectuer la
sauvegarde chiffrée de la base PostgreSQL avec la **skill `vps-db-backup`**
(dump chiffré AES-256 envoyé vers Bunny Storage, rétention automatique). Voir
`.vps-backup.conf` à la racine du projet.

Compléter par la sauvegarde du fichier `compose.yml` et des variables
d'environnement (hors secrets, qui vivent chez l'humain ou dans la CI).

## Points d'attention

- Un seul déploiement à la fois par hôte (verrou simple ou fenêtre de
  maintenance).
- Surveiller l'espace disque (`docker system df`, images accumulées).
- Vérifier l'expiration des certificats TLS (revers proxy, Certbot).
