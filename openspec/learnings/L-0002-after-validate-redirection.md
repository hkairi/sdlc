+++
id = "L-0002"
title = "after-validate prend une redirection shell pour un id de change"
kind = "pitfall"
created = "2026-10-26"
status = "active"
scope = [".opencode/plugins/ai-sdlc-tracker"]
tags = ["hook", "parsing", "openspec", "pipeline", "exit-code"]
source_change = "audit-chaine-ia-2026-10-26"

[[evidence]]
cmd = "openspec validate optimize-dashboard-read-queries --strict 2>&1 | tail -3"
result = "affiche « suivi non créé pour 2>&1 (code 1) » alors que la validation passe (1 change valide, 0 échec)"

[[evidence]]
cmd = "openspec list 2>&1 | head -20"
result = "même message parasite, 1 occurrence par commande contenant « validate »"

[[evidence]]
cmd = "cd .opencode/plugins/ai-sdlc-tracker && npm test"
result = "9 cas de parsing dans hooks/shared.test.ts, 0 échec (2>&1, pipe, variable, --type spec, --all)"
+++

## Règle

Dans `after-validate`, découper la commande shell en segments avant d'extraire
l'identifiant du change, et ne jamais déduire le succès du code de sortie d'un
pipeline.

*État au 2026-10-26 : corrigé dans le plugin 0.3.0 (découpage par segment et par
redirection, identifiant devant commencer par une lettre, `--specs` et
`--type spec` ignorés, existence du change exigée). La règle reste écrite ici
pour que la correction ne soit pas défaite par une réécriture du hook ; elle
pourra passer `retired` après une vérification en session réelle.*

## Pourquoi

Le hook reçoit la chaîne complète (`for c in …; do openspec validate "$c" … 2>&1 | tail -5; done`).
Il cherche « validate », prend le token suivant et tombe sur `2>&1`. Comme le
code du pipeline est celui de `tail` (0), il croit la validation réussie et
lance une génération de suivi pour un change inexistant. Deux défauts : tokens
non filtrés, et statut du pipeline au lieu de celui de la commande.

## Comment vérifier

```sh
openspec validate <change> --strict 2>&1 | tail -1
# doit afficher « Change '<change>' is valid » et AUCUN message ai-sdlc-tracker
```

Un test `node --test` sur `openspecValidateChange` avec
`"openspec validate x --strict 2>&1 | tail"` doit retourner `x`, pas `2>&1`.
