# Installation de la Console SDLC

## Prérequis

- Python 3.12 ou plus récent ;
- Node.js 22+ et npm pour construire l'interface React (build uniquement) ;
- Git pour l'ingestion des dépôts ;
- `uv` ou `pipx` pour l'installation de la commande.

## Installation locale

Depuis `apps/console/` :

```bash
./scripts/build_frontend.sh
uv tool install .
# ou
pipx install .
```

La commande unique est ensuite `sdlc-console` :

```bash
sdlc-console init
sdlc-console doctor
sdlc-console serve --open-suivi
```

`init` applique les migrations Alembic. `serve` vérifie que le schéma est à jour
avant de démarrer et refuse toute écoute hors de `127.0.0.0/8`.

## Jeu de démonstration

```bash
sdlc-console init --demo
sdlc-console serve --demo
```

Le jeu est idempotent : un second appel ne duplique ni le projet ni les données.
Il crée deux dépôts, une feature, cinq tâches, cinq runs, cinq déploiements et
sept gates avec preuves.

## WSL2

`127.0.0.2` n'est pas joignable depuis Windows en mode NAT WSL2. Deux solutions
sont documentées :

1. **Mode miroir (recommandé)** : ajouter dans `%UserProfile%\.wslconfig` :

   ```ini
   [wsl2]
   networkingMode=mirrored
   ```

   puis `wsl --shutdown`. Le navigateur Windows peut alors utiliser
   `http://127.0.0.2:8765`.

2. **Navigateur dans WSL** : lancer `sdlc-console serve` dans WSL puis ouvrir
   `http://127.0.0.2:8765` avec un navigateur exécuté dans la distribution
   (WSLg ou navigateur en mode X).

Le proxy de port Windows n'est pas recommandé : l'application refuse par
principe d'écouter sur une interface LAN ou sur `0.0.0.0`.

## Vérification

```bash
sdlc-console doctor
curl --fail http://127.0.0.2:8765/api/health
```

Ne déposez jamais de jeton GitHub/GitLab dans `sdlc.config.yaml` ou dans un
fichier `.env` du projet : les runs d'agents sont purgés de ces variables.
