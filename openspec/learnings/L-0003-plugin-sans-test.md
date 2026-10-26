+++
id = "L-0003"
title = "Le plugin ai-sdlc-tracker n'a aucun test"
kind = "pitfall"
created = "2026-10-26"
status = "active"
scope = [".opencode/plugins/ai-sdlc-tracker"]
tags = ["tests", "plugin", "node-test", "typecheck"]
source_change = "audit-chaine-ia-2026-10-26"

[[evidence]]
cmd = "cd .opencode/plugins/ai-sdlc-tracker && npm test"
result = "TAP 1..0 — 0 test, 0 suite, 0 pass"
+++

## Règle

Toute modification de `tools/` ou `hooks/` du plugin doit être accompagnée d'un
test `node --test` qui exerce le comportement. `tsc --noEmit` ne compte pas.

## Pourquoi

Le plugin écrit `tasks.md`, génère les suivis HTML et **bloque les commits**.
`npm test` sort `1..0` : la suite est vide. Le typecheck valide les types, pas
la logique — c'est précisément ainsi que le bug de parsing `2>&1` (L-0002) et
la couverture manquante ont pu vivre sans alerte.

## Comment vérifier

```sh
cd .opencode/plugins/ai-sdlc-tracker && npm test
# doit afficher un nombre de tests > 0 et 0 échec
```

Si la suite reste vide, l'entrée est toujours valide : ne pas la retirer.
