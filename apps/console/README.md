# Console SDLC

## Installation

```bash
uv tool install .
# ou
pipx install .
```

Le build frontend embarqué est produit par :

```bash
./scripts/build_frontend.sh
```

## Commande unique

```bash
sdlc-console init
sdlc-console doctor
sdlc-console serve --open-suivi
```

Le serveur écoute uniquement sur `127.0.0.2`. Si le build frontend embarqué est présent,
`/` sert l'interface React ; les routes `/api/*` restent prioritaires.
