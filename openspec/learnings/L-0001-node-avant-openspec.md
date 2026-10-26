+++
id = "L-0001"
title = "Vérifier node avant de conclure qu'openspec échoue"
kind = "tooling"
created = "2026-10-26"
status = "active"
scope = ["scripts", ".githooks", ".github/workflows", ".opencode"]
tags = ["node", "openspec", "homebrew", "simdjson", "toolchain"]
source_change = "audit-chaine-ia-2026-10-26"

[[evidence]]
cmd = "openspec --version"
result = "dyld: Library not loaded: libsimdjson.33.dylib — 0 sortie"

[[evidence]]
cmd = "zsh -c 'node -v; openspec --version'"
result = "v22.14.0 puis 0.18.0 — fonctionne via ~/.zshenv"
+++

## Règle

Avant de conclure qu'un script OpenSpec, npm ou npx échoue, exécuter
`node -v` dans le **même** shell : si le Node Homebrew est cassé, le problème
n'est pas dans le script.

## Pourquoi

Le 2026-10-26, `openspec validate --all --strict` sortait une erreur `dyld`
alors que les 28 items étaient valides. Le binaire Homebrew `node 26.9.0` est
lié à `libsimdjson.33` et le seul simdjson installé fournit `.34`. `node` et
`llvm` sont épinglés dans Homebrew, donc `brew upgrade node` refuse. Les shells
non interactifs (hooks, scripts, OpenCode) ne lisaient pas `~/.zshrc` et
prenaient le Node cassé ; `~/.zshenv` + `~/.zlogin` chargent nvm 22.14.

## Comment vérifier

```sh
zsh -c 'node -v; openspec --version'     # doit afficher v22.14.0 et 0.18.0
zsh -lc 'node -v'                        # idem en shell de login (RVM réécrit PATH)
```

Si `brew upgrade node` est de nouveau possible (pins levés), cette entrée peut
passer `status = "retired"` avec la raison « node Homebrew réparé ».
