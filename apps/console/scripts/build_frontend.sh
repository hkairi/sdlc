#!/usr/bin/env bash
# Construit le frontend puis l'embarque dans le paquet Python.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root/web"
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
npm run build
rm -rf "$root/src/sdlc_console/web/dist"
mkdir -p "$root/src/sdlc_console/web"
cp -R "$root/web/dist" "$root/src/sdlc_console/web/dist"
echo "Frontend embarqué dans src/sdlc_console/web/dist"
