# Console SDLC

Application web **locale** de pilotage du framework SDLC : tableau de bord, gates, revue
indépendante, équipe, processus, agents et documentation.

> **État : lot L0 — socle.** Le backend FastAPI, le frontend React et la CLI sont des
> squelettes. La base SQLite, les migrations et les 12 vues arrivent dans les lots suivants.

## Prérequis

- Python 3.12+ (sur ce poste : `python3.14`)
- Node 22+ (build frontend uniquement)
- SQLite 3.45+ (fourni avec Python)

## Installation

```bash
cd apps/console
python3.14 -m venv .venv   # ou python3.12 / python3.13
. .venv/bin/activate
pip install -e ".[dev]"

cd web
npm install
```

## Lancer

```bash
# backend local (127.0.0.2:8765, sans authentification)
cd apps/console
PYTHONPATH=src python3 -m sdlc_console.cli doctor
PYTHONPATH=src python3 -m sdlc_console.cli serve

# frontend de développement (127.0.0.2:5173, proxy /api vers 8765)
cd apps/console/web
npm run dev
```

## Configuration

Le fichier `sdlc.config.yaml` est validé au démarrage contre
`src/sdlc_console/config.schema.json` (JSON Schema 2020-12). Un fichier absent, un YAML
invalide ou une clé obligatoire manquante produit un message explicite et un code de sortie
non nul.

```bash
PYTHONPATH=src python3 -m sdlc_console.cli doctor --config ../../sdlc.config.example.yaml
```

## Base de données

SQLite est configuré en WAL, clés étrangères actives, `synchronous=NORMAL` et
`busy_timeout=5000`. Les migrations sont gérées par Alembic.

```bash
cd apps/console
. .venv/bin/activate
alembic upgrade head                 # applique les migrations
alembic downgrade base               # retour arrière (tests)
alembic revision --autogenerate -m "..."  # nouvelle migration
```

## Tester

```bash
cd apps/console
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Les tests FastAPI sont ignorés si `fastapi` et `httpx` ne sont pas installés.

## Sécurité

- Écoute uniquement sur `127.0.0.2` (boucle locale).
- Aucune authentification en MVP ; aucune donnée sortante par défaut.
- Tout bind hors `127.0.0.0/8` est refusé par la CLI.
- Validation `Host`/`Origin`/`Referer`, CSRF signé, `Content-Type: application/json`, CSP.

## WSL2

`127.0.0.2` n'est pas garanti depuis le navigateur de l'hôte Windows en mode NAT.
Solutions : activer le **mode réseau miroir** WSL2, lancer le navigateur dans WSL, ou
utiliser `localhost` (forwarding). Smoke test :

```bash
# dans WSL2, depuis apps/console
bash scripts/wsl2-smoke.sh
```

Le workflow `.github/workflows/console.yml` exécute ce smoke test en *best effort* sur
`windows-latest` ; la joignabilité réelle depuis l'hôte doit être validée sur un poste
Windows/WSL2.

## Références

- Cahier des charges : `../../docs/00-cadrage/cahier-des-charges-web.md`
- Change OpenSpec : `../../openspec/changes/console-sdlc/`
- ADR : `../../docs/architecture/adr/`
- Suivi : `../../docs/suivi-console.html`
