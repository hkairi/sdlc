#!/usr/bin/env bash
#
# Tests du ratchet de baseline (`.agents/skills/suivi-taches/scripts/baseline.py`).
#
# Le calcul est une fonction pure (`ratchet_problems`) : on l'exerce sur des
# états construits, sans toucher au dépôt ni exécuter `check_sync.py`.
#
# Usage : bash scripts/tests/test_baseline_ratchet.sh
# Sortie : 0 si tous les cas passent, 1 sinon.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

python3 - "$REPO_ROOT" <<'PY'
import importlib.util
import os
import sys

root = sys.argv[1]
path = os.path.join(root, ".agents", "skills", "suivi-taches", "scripts", "baseline.py")
spec = importlib.util.spec_from_file_location("baseline", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

failures = 0
cases = 0


def case(label, baseline, drifts, unproven, expected_resolved, expected_new):
    global failures, cases
    cases += 1
    resolved, new = module.ratchet_problems(baseline, drifts, unproven)
    ok = len(resolved) == expected_resolved and len(new) == expected_new
    if ok:
        print(f"ok   {label}")
    else:
        failures += 1
        print(f"FAIL {label} — resolved={resolved} new={new}")


BASE = {
    "drifts": ["add-x : tasks.md présent mais suivi manquant"],
    "unproven": {"add-x": ["1.1", "2.1"]},
}

case(
    "état identique : rien à signaler",
    BASE,
    ["add-x : tasks.md présent mais suivi manquant"],
    {"add-x": ["1.1", "2.1"]},
    0,
    0,
)

case(
    "dérive résorbée mais encore listée",
    BASE,
    [],
    {"add-x": ["1.1", "2.1"]},
    1,
    0,
)

case(
    "tâche désormais prouvée mais encore listée",
    BASE,
    ["add-x : tasks.md présent mais suivi manquant"],
    {"add-x": ["2.1"]},
    1,
    0,
)

case(
    "nouvelle dérive : signalée, pas comptée comme résorbée",
    BASE,
    ["add-x : tasks.md présent mais suivi manquant", "add-y : nouveau problème"],
    {"add-x": ["1.1", "2.1"]},
    0,
    1,
)

case(
    "nouvelle tâche sans preuve : signalée, pas comptée comme résorbée",
    BASE,
    ["add-x : tasks.md présent mais suivi manquant"],
    {"add-x": ["1.1", "2.1", "3.1"]},
    0,
    1,
)

case(
    "change entièrement résorbé",
    BASE,
    [],
    {},
    3,
    0,
)

case(
    "formulation changée pour le même change : pas résorbé",
    BASE,
    ["add-x : tasks.md présent mais ni docs/suivi-add-x.html ni feature dans docs/suivi-multi.html"],
    {"add-x": ["1.1", "2.1"]},
    0,
    0,
)

print(f"\n{cases} cas, {failures} échec(s)")
sys.exit(1 if failures else 0)
PY
