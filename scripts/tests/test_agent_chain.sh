#!/usr/bin/env bash
#
# Tests de la chaîne d'agents : contrat de handoff (`handoff_check.py`) et
# registre d'apprentissages (`learnings.py`).
#
# Chaque cas construit une arborescence jetable dans $TMPDIR, exécute le script
# avec `--root`, et vérifie le code de sortie ET le message attendu. Aucun
# fichier du dépôt n'est modifié.
#
# Usage : bash scripts/tests/test_agent_chain.sh
# Sortie : 0 si tous les cas passent, 1 sinon.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/agent-chain.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
FAILS=0
CASES=0

pass() { printf 'ok   %s\n' "$1"; }
fail() { printf 'FAIL %s\n' "$1"; FAILS=$((FAILS + 1)); }

# run <libellé> <code attendu> <motif attendu> <commande…>
run() {
  local label="$1" expected="$2" pattern="$3"
  shift 3
  local output code
  output="$("$@" 2>&1)"
  code=$?
  CASES=$((CASES + 1))
  if [ "$code" -ne "$expected" ]; then
    fail "$label (code $code, attendu $expected)"
    printf '%s\n' "$output" | sed 's/^/       /'
    return
  fi
  if [ -n "$pattern" ] && ! printf '%s\n' "$output" | grep -q -- "$pattern"; then
    fail "$label (message attendu absent : $pattern)"
    printf '%s\n' "$output" | sed 's/^/       /'
    return
  fi
  pass "$label"
}

# --- Registre d'apprentissages ---------------------------------------------
run "registre réel valide" 0 "active(s)" \
  python3 "$REPO_ROOT/scripts/learnings.py" --check

LEDGER="$TMP/ledger"
mkdir -p "$LEDGER/openspec/learnings"
cat > "$LEDGER/openspec/learnings/L-0001-sans-preuve.md" <<'EOF'
+++
id = "L-0001"
title = "Règle sans preuve"
kind = "practice"
created = "2026-10-26"
status = "active"
scope = ["src"]
tags = ["x"]
evidence = []
+++

## Règle
Faire.
## Pourquoi
Parce que.
## Comment vérifier
Rien.
EOF
run "entrée sans preuve refusée" 1 "aucune preuve" \
  python3 "$REPO_ROOT/scripts/learnings.py" --root "$LEDGER" --check

cat > "$LEDGER/openspec/learnings/L-0002-retiree.md" <<'EOF'
+++
id = "L-0002"
title = "Règle périmée"
kind = "pitfall"
created = "2026-10-26"
status = "retired"
scope = ["src"]
tags = ["y"]
evidence = [{ cmd = "true", result = "0" }]
+++

## Règle
Faire.
## Pourquoi
Parce que.
## Comment vérifier
Rien.
EOF
run "entrée retirée sans motif refusée" 1 "retired_reason" \
  python3 "$REPO_ROOT/scripts/learnings.py" --root "$LEDGER" --check

# --- Contrat de handoff -----------------------------------------------------
CHANGE="$TMP/repo/openspec/changes/demo"
mkdir -p "$CHANGE/handoff" "$TMP/repo/openspec/learnings"
cat > "$TMP/repo/openspec/learnings/L-0001-ok.md" <<'EOF'
+++
id = "L-0001"
title = "Une règle"
kind = "pitfall"
created = "2026-10-26"
status = "active"
scope = ["src"]
tags = ["z"]
evidence = [{ cmd = "true", result = "0" }]
+++

## Règle
Faire.
## Pourquoi
Parce que.
## Comment vérifier
Rien.
EOF
cat > "$CHANGE/tasks.md" <<'EOF'
## 1. Cadrage

- [x] 1.1 Trancher.
  - Tests : `openspec validate demo --strict`

## 2. Implémentation

- [x] 2.1 Implémenter.
  - Tests : `bundle exec rspec spec/x_spec.rb`
EOF
cat > "$CHANGE/handoff/10-spec.md" <<'EOF'
+++
change = "demo"
stage = "spec"
revision = 1
from = "spec"
to = "impl"
status = "ready"
created = "2026-10-26T09:00:00Z"
tasks = ["1.1"]
files = ["openspec/changes/demo/tasks.md"]
evidence = [{ cmd = "openspec validate demo --strict", result = "Change 'demo' is valid" }]
open_questions = []
+++

## Décisions
A.
EOF
cat > "$CHANGE/handoff/20-impl.md" <<'EOF'
+++
change = "demo"
stage = "impl"
revision = 1
from = "impl"
to = "test"
status = "ready"
created = "2026-10-26T10:00:00Z"
tasks = ["2.1"]
files = []
evidence = [{ cmd = "bundle exec rspec spec/x_spec.rb", result = "12 examples, 0 failures" }]
open_questions = []
+++

## Décisions
B.
EOF
run "chaîne valide" 0 "tâche(s) couverte(s)" \
  python3 "$REPO_ROOT/scripts/handoff_check.py" --root "$TMP/repo" --all

sed -i.bak 's/^status = "ready"/status = "ready"/' "$CHANGE/handoff/20-impl.md"
printf '\n- [x] 2.2 Non couverte.\n  - Tests : `go test ./...`\n' >> "$CHANGE/tasks.md"
run "tâche cochée non couverte refusée" 1 "couverte par aucun artefact" \
  python3 "$REPO_ROOT/scripts/handoff_check.py" --root "$TMP/repo" --all

sed -i.bak 's#bundle exec rspec spec/x_spec.rb#bundle exec rspec spec/autre_spec.rb#' "$CHANGE/handoff/20-impl.md"
run "preuve hors Tests refusée" 1 "ne correspond à aucun champ Tests" \
  python3 "$REPO_ROOT/scripts/handoff_check.py" --root "$TMP/repo" --all

cat > "$CHANGE/handoff/40-review.md" <<'EOF'
+++
change = "demo"
stage = "review"
revision = 1
from = "review"
to = "docs"
status = "ready"
created = "2026-10-26T11:00:00Z"
tasks = ["2.1"]
files = ["src/x.rb"]
evidence = [{ cmd = "git diff --name-only", result = "1 fichier" }]
open_questions = []
+++

## Décisions
C.
EOF
run "review en écriture refusée" 1 "lecture seule" \
  python3 "$REPO_ROOT/scripts/handoff_check.py" --root "$TMP/repo" --all

# --- Résumé -----------------------------------------------------------------
printf '\n%s cas, %s échec(s)\n' "$CASES" "$FAILS"
[ "$FAILS" -eq 0 ]
