#!/usr/bin/env bash
# scripts/ci.sh — contrôles uniques de la Console SDLC.
#
# Usage : scripts/ci.sh [--only lint,tests] [--skip sast] [--help]
# Contrôles : lint, typecheck, tests, coverage, sast, deps, secrets, build.
# Sorties : reports/lint, reports/coverage, reports/security, reports/build,
#           reports/summary.json.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONSOLE="$ROOT/apps/console"
WEB="$CONSOLE/web"
VENV="${SDLC_VENV:-$CONSOLE/.venv}"
PY="$VENV/bin/python"
REPORTS="$ROOT/reports"
ONLY=""
SKIP=""
CONTROLS="lint typecheck tests coverage sast deps secrets build"

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --only) ONLY="${2//,/ }"; shift 2 ;;
    --skip) SKIP="${2//,/ }"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "option inconnue : $1" >&2; exit 2 ;;
  esac
done

if [ ! -x "$PY" ]; then
  echo "environnement Python introuvable : $VENV" >&2
  echo "créez-le avec : python3 -m venv $VENV && $VENV/bin/pip install -e '$CONSOLE[dev]'" >&2
  exit 2
fi

mkdir -p "$REPORTS/lint" "$REPORTS/coverage" "$REPORTS/security" "$REPORTS/build"
STATUS_FILE="$(mktemp "${TMPDIR:-/tmp}/sdlc-ci-status.XXXXXX")"
trap 'rm -f "$STATUS_FILE"' EXIT
FAILED=0

should_run() {
  local name="$1"
  if [ -n "$ONLY" ] && [[ " $ONLY " != *" $name "* ]]; then
    return 1
  fi
  if [ -n "$SKIP" ] && [[ " $SKIP " == *" $name "* ]]; then
    return 1
  fi
  return 0
}

record() {
  printf '%s=%s\n' "$1" "$2" >> "$STATUS_FILE"
}

run_control() {
  local name="$1" label="$2"
  shift 2
  if ! should_run "$name"; then
    record "$name" "skipped"
    echo "[$name] ignoré"
    return 0
  fi
  echo "[$name] $label"
  set +e
  ( set -euo pipefail; "$@" )
  local rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then
    record "$name" "pass"
    echo "[$name] OK"
  else
    record "$name" "fail"
    echo "[$name] ÉCHEC" >&2
    FAILED=1
  fi
}

control_lint() {
  cd "$CONSOLE" || return 1
  "$VENV/bin/ruff" check src tests 2>&1 | tee "$REPORTS/lint/ruff.txt"
}

control_typecheck() {
  cd "$CONSOLE" || return 1
  "$VENV/bin/mypy" src 2>&1 | tee "$REPORTS/lint/mypy.txt"
}

control_tests() {
  cd "$CONSOLE" || return 1
  "$PY" -m unittest discover -s tests 2>&1 | tee "$REPORTS/junit-unittest.txt"
  cd "$WEB" || return 1
  npm test -- --run 2>&1 | tee "$REPORTS/junit-vitest.txt"
}

control_coverage() {
  cd "$CONSOLE" || return 1
  "$PY" -m coverage erase
  "$PY" -m coverage run --source=src/sdlc_console -m unittest discover -s tests 2>&1 | tee "$REPORTS/coverage/run.txt"
  "$PY" -m coverage report --fail-under=80 2>&1 | tee "$REPORTS/coverage/report.txt"
  "$PY" -m coverage xml -o "$REPORTS/coverage/coverage.xml"
  "$PY" -m coverage json -o "$REPORTS/coverage/coverage.json"
}

control_sast() {
  cd "$CONSOLE" || return 1
  "$PY" -m bandit -q -r src -f json -o "$REPORTS/security/bandit.json" -lll
}

control_deps() {
  cd "$CONSOLE" || return 1
  "$PY" -m pip check 2>&1 | tee "$REPORTS/security/pip-check.txt"
  "$PY" -m pip_audit --format=json --output "$REPORTS/security/pip-audit.json" --progress-spinner=off
  cd "$WEB" || return 1
  npm audit --omit=dev --audit-level=high --json > "$REPORTS/security/npm-audit.json"
}

control_secrets() {
  cd "$ROOT" || return 1
  if command -v gitleaks >/dev/null 2>&1; then
    gitleaks dir apps/console/src --no-banner --redact --report-format json \
      --report-path "$REPORTS/security/gitleaks.json"
  else
    # Repli local : recherche de motifs de clés privées et de jetons connus.
    if rg -n --hidden -g '!**/.venv/**' -g '!**/node_modules/**' \
      -e 'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY' -e 'AKIA[0-9A-Z]{16}' \
      -e 'gh[pousr]_[A-Za-z0-9]{20,}' apps/console/src; then
      echo "motifs de secrets détectés" >&2
      return 1
    fi
  fi
}

control_build() {
  cd "$CONSOLE" || return 1
  cd "$WEB" || return 1
  npm run build 2>&1 | tee "$REPORTS/build/frontend.txt"
  cd "$CONSOLE" || return 1
  rm -rf src/sdlc_console/web/dist
  mkdir -p src/sdlc_console/web
  cp -R web/dist src/sdlc_console/web/dist
  "$PY" -m build --wheel --outdir "$REPORTS/build" 2>&1 | tee "$REPORTS/build/package.txt"
}

run_control lint "Ruff" control_lint
run_control typecheck "mypy" control_typecheck
run_control tests "tests Python et Vitest" control_tests
run_control coverage "couverture ≥ 80 %" control_coverage
run_control sast "Bandit" control_sast
run_control deps "pip check, pip-audit, npm audit" control_deps
run_control secrets "gitleaks" control_secrets
run_control build "frontend + roue Python" control_build

"$PY" - "$STATUS_FILE" "$REPORTS/summary.json" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path, output_path = (Path(sys.argv[1]), Path(sys.argv[2]))
controls = {}
for line in status_path.read_text(encoding="utf-8").splitlines():
    if "=" in line:
        name, status = line.split("=", 1)
        controls[name] = status
failed = [name for name, status in controls.items() if status == "fail"]
summary = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "controls": controls,
    "failed": failed,
    "passed": not failed,
}
output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY

if [ "$FAILED" -ne 0 ]; then
  echo "contrôles en échec ; voir reports/" >&2
  exit 1
fi
echo "tous les contrôles sont verts"
