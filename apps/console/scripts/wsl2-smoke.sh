#!/usr/bin/env bash
# Smoke test WSL2 de la Console SDLC.
# À exécuter dans WSL2, depuis apps/console : bash scripts/wsl2-smoke.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "WSL2 : $(uname -a)"
python3 --version

python3 -m venv .venv-wsl
. .venv-wsl/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e ".[dev]"
python -m unittest discover -s tests -v

echo "OK : tests exécutés dans WSL2."
echo "Démarrer le serveur : sdlc-console serve --host 127.0.0.2"
echo "Depuis Windows : curl http://localhost:8765/api/health"
echo "Si 127.0.0.2 n'est pas joignable en NAT, activer le mode réseau miroir WSL2."
