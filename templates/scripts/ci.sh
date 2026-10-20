#!/usr/bin/env bash
# scripts/ci.sh — contrôles uniques du framework SDLC (local et CI).
#
# Ce script est LA définition des contrôles (§ 10 de .sdlc/workflow-sdlc.md).
# Le pipeline de l'outil de CI ne fait que l'appeler. Il écrit ses sorties dans reports/.
#
# Sorties produites (contrat § 10) :
#   reports/junit/*.xml        tests (JUnit)
#   reports/coverage/          couverture (Cobertura XML, lcov, JaCoCo XML ou coverage.py JSON)
#   reports/security/*.sarif   analyse de code, dépendances, conteneurs, secrets (SARIF 2.1.0)
#   reports/lint/*.txt         lint (sortie texte) + code de sortie
#   reports/summary.json       résumé machine lu par le tableau de bord
#   reports/thresholds.json    détail du calcul des seuils (couverture, vulnérabilités)
#
# Usage :
#   scripts/ci.sh [--only <contrôle>]... [--skip <contrôle>]... [--help]
#
#   <contrôle> ∈ lint | tests | coverage | sast | deps | secrets | build
#   --only et --skip acceptent plusieurs valeurs séparées par des virgules ou répétées.
#
# Seuils : lus dans sdlc.config.yaml (§ 4) — ci.coverage_min et ci.block_on.
#   Si yq est installé, il est utilisé ; sinon lecture simple par grep/sed.
#   Valeurs par défaut documentées si la config ou la clé est absente :
#     ci.coverage_min = 80
#     ci.block_on     = critique, haute
#   Note : ci.block_on utilise « faible » ; le résumé machine utilise « basse »
#   (synonymes). Aucune autre valeur n'est reconnue.
#
# Variables d'environnement (surcharge, toutes optionnelles) :
#   SDLC_ROOT           Racine du projet (défaut : dossier parent de ce script).
#   SDLC_CONFIG         Chemin de sdlc.config.yaml (défaut : $SDLC_ROOT/sdlc.config.yaml).
#   SDLC_REPORTS_DIR    Dossier des rapports (défaut : paths.reports, sinon dashboard.reports_dir, sinon « reports »).
#   SDLC_COVERAGE_MIN   Seuil de couverture (défaut : ci.coverage_min, sinon 80).
#   SDLC_BLOCK_ON       Sévérités bloquantes (défaut : ci.block_on, sinon « critique,haute »).
#   SDLC_<CONTRÔLE>_CMD  Commande explicite pour un contrôle, exécutée via `bash -c`.
#                        Contrôles : LINT, TEST, COVERAGE, SAST, DEPS, SECRETS, BUILD.
#
# Règle : un outil absent produit un avertissement et un statut « not_run » (jamais un
# faux succès). Un contrôle « fail » bloque la sortie (code de sortie non nul).
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Localisation, journalisation
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${SDLC_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
CONFIG="${SDLC_CONFIG:-$ROOT/sdlc.config.yaml}"

log()  { printf '%s\n' "$*"; }
warn() { printf 'AVERTISSEMENT : %s\n' "$*" >&2; }
die()  { printf 'ERREUR : %s\n' "$*" >&2; exit 2; }

have() { command -v "$1" >/dev/null 2>&1; }

# Écrit un log de commande dans un fichier.
log_cmd() { printf '\n$ %s\n' "$*" >>"$1"; }

# ---------------------------------------------------------------------------
# Lecture de la configuration (yq si présent, sinon grep/sed)
# ---------------------------------------------------------------------------
read_config_value() {
  # $1 = clé pointée (ex. ci.coverage_min) ; $2 = valeur par défaut.
  local key="$1" default="$2" leaf value=""
  if [ -f "$CONFIG" ]; then
    if have yq; then
      value="$(yq -r ".${key} // empty" "$CONFIG" 2>/dev/null || true)"
    fi
    if [ -z "$value" ] || [ "$value" = "null" ]; then
      leaf="${key##*.}"
      value="$(sed -n "s/^[[:space:]]*${leaf}[[:space:]]*:[[:space:]]*\(.*\)$/\1/p" "$CONFIG" 2>/dev/null \
        | head -1 \
        | sed 's/[[:space:]]*#.*$//; s/^[[:space:]]*//; s/[[:space:]]*$//; s/^"//; s/"$//; s/^'"'"'//; s/'"'"'$//')"
    fi
  fi
  if [ -z "$value" ]; then printf '%s' "$default"; else printf '%s' "$value"; fi
}

normalize_words() { printf '%s' "$1" | tr ',\n' '  ' | tr -s ' ' | sed 's/^ //; s/ $//'; }

# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------
ALL_CONTROLS="lint tests coverage sast deps secrets build"
ONLY=""
SKIPPED=""

usage() {
  sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --only)  [ $# -ge 2 ] || die "--only attend un contrôle"; ONLY="$ONLY $(normalize_words "$2")"; shift 2;;
    --only=*) ONLY="$ONLY $(normalize_words "${1#*=}")"; shift;;
    --skip)  [ $# -ge 2 ] || die "--skip attend un contrôle"; SKIPPED="$SKIPPED $(normalize_words "$2")"; shift 2;;
    --skip=*) SKIPPED="$SKIPPED $(normalize_words "${1#*=}")"; shift;;
    -h|--help) usage; exit 0;;
    *) die "option inconnue : $1 (voir --help)";;
  esac
done
ONLY="$(normalize_words "$ONLY")"
SKIPPED="$(normalize_words "$SKIPPED")"

is_enabled() {
  # $1 = nom du contrôle
  case " $SKIPPED " in *" $1 "*) return 1;; esac
  if [ -n "$ONLY" ]; then
    case " $ONLY " in *" $1 "*) return 0;; *) return 1;; esac
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Configuration effective et dossiers
# ---------------------------------------------------------------------------
cd "$ROOT"

if [ -f "$CONFIG" ]; then
  COVERAGE_MIN="${SDLC_COVERAGE_MIN:-$(read_config_value ci.coverage_min 80)}"
  BLOCK_ON_RAW="${SDLC_BLOCK_ON:-$(read_config_value ci.block_on 'critique, haute')}"
  # Dossier des rapports : paths.reports (§ 13.3), sinon dashboard.reports_dir, sinon « reports ».
  REPORTS="${SDLC_REPORTS_DIR:-$(read_config_value paths.reports "$(read_config_value dashboard.reports_dir reports)")}"
else
  warn "sdlc.config.yaml absent ($CONFIG) : valeurs par défaut appliquées."
  COVERAGE_MIN="${SDLC_COVERAGE_MIN:-80}"
  BLOCK_ON_RAW="${SDLC_BLOCK_ON:-critique, haute}"
  REPORTS="${SDLC_REPORTS_DIR:-reports}"
fi

case "$COVERAGE_MIN" in
  ''|*[!0-9.]*) warn "ci.coverage_min invalide (« $COVERAGE_MIN ») : 80 utilisé."; COVERAGE_MIN=80;;
esac
BLOCK_ON="$(printf '%s' "$BLOCK_ON_RAW" | tr -d '[]"' | tr ',\n' ' ' | tr -s ' ' | sed 's/^ //; s/ $//')"

REPORTS="${REPORTS%/}"
[ -n "$REPORTS" ] || REPORTS="reports"

LINT_DIR="$REPORTS/lint"
JUNIT_DIR="$REPORTS/junit"
COV_DIR="$REPORTS/coverage"
SEC_DIR="$REPORTS/security"
SUMMARY_FILE="$REPORTS/summary.json"
THRESHOLDS_FILE="$REPORTS/thresholds.json"

mkdir -p "$REPORTS"
SUMMARY_LOG=""

# ---------------------------------------------------------------------------
# Détection des stacks
# ---------------------------------------------------------------------------
STACKS=""
[ -f package.json ] && STACKS="$STACKS node"
[ -f Gemfile ] && STACKS="$STACKS ruby"
{ [ -f pyproject.toml ] || [ -f requirements.txt ]; } && STACKS="$STACKS python"
[ -f go.mod ] && STACKS="$STACKS go"
{ [ -f pom.xml ] || [ -f build.gradle ] || [ -f build.gradle.kts ]; } && STACKS="$STACKS java"
STACKS="$(printf '%s' "$STACKS" | sed 's/^ //')"

PY="false"
have python3 && PY="true"

# ---------------------------------------------------------------------------
# Contrôles
# ---------------------------------------------------------------------------
LINT_RAN=0 LINT_RC=0
TESTS_RAN=0 TESTS_RC=0
COVERAGE_RAN=0 COVERAGE_RC=0
SAST_RAN=0 SAST_RC=0
DEPS_RAN=0 DEPS_RC=0
SECRETS_RAN=0 SECRETS_RC=0
BUILD_RAN=0 BUILD_RC=0

run_lint() {
  mkdir -p "$LINT_DIR"
  local log="$LINT_DIR/lint.txt"
  : >"$log"
  if [ -n "${SDLC_LINT_CMD:-}" ]; then
    LINT_RAN=1; log_cmd "$log" "$SDLC_LINT_CMD"
    bash -c "$SDLC_LINT_CMD" >>"$log" 2>&1 || LINT_RC=1
    return 0
  fi
  local stack
  for stack in $STACKS; do
    case "$stack" in
      node)
        if grep -q '"lint"' package.json 2>/dev/null; then
          LINT_RAN=1; log_cmd "$log" "npm run lint"; npm run --silent lint >>"$log" 2>&1 || LINT_RC=1
        elif have npx; then
          LINT_RAN=1; log_cmd "$log" "npx --no-install eslint ."; npx --no-install eslint . >>"$log" 2>&1 || LINT_RC=1
        fi ;;
      ruby)
        if have bundle; then
          LINT_RAN=1; log_cmd "$log" "bundle exec rubocop"; bundle exec rubocop >>"$log" 2>&1 || LINT_RC=1
        fi ;;
      python)
        if have ruff; then
          LINT_RAN=1; log_cmd "$log" "ruff check ."; ruff check . >>"$log" 2>&1 || LINT_RC=1
        elif have flake8; then
          LINT_RAN=1; log_cmd "$log" "flake8"; flake8 >>"$log" 2>&1 || LINT_RC=1
        fi ;;
      go)
        if have gofmt; then
          LINT_RAN=1
          local unformatted
          unformatted="$(gofmt -l . 2>/dev/null || true)"
          if [ -n "$unformatted" ]; then
            LINT_RC=1
            { log_cmd "$log" "gofmt -l ."; printf '%s\n' "$unformatted"; } >>"$log"
          fi
        fi
        if have go; then
          LINT_RAN=1; log_cmd "$log" "go vet ./..."; go vet ./... >>"$log" 2>&1 || LINT_RC=1
        fi ;;
    esac
  done
}

run_tests() {
  mkdir -p "$JUNIT_DIR"
  local log="$JUNIT_DIR/tests.txt"
  : >"$log"
  if [ -n "${SDLC_TEST_CMD:-}" ]; then
    TESTS_RAN=1; log_cmd "$log" "$SDLC_TEST_CMD"
    bash -c "$SDLC_TEST_CMD" >>"$log" 2>&1 || TESTS_RC=1
    return 0
  fi
  local stack
  for stack in $STACKS; do
    case "$stack" in
      node)
        if grep -q '"test"' package.json 2>/dev/null; then
          TESTS_RAN=1; log_cmd "$log" "npm test"; npm test >>"$log" 2>&1 || TESTS_RC=1
        fi ;;
      ruby)
        if have bundle; then
          TESTS_RAN=1; log_cmd "$log" "bundle exec rspec"; bundle exec rspec >>"$log" 2>&1 || TESTS_RC=1
        fi ;;
      python)
        if [ "$PY" = "true" ] && python3 -c 'import pytest' >/dev/null 2>&1; then
          TESTS_RAN=1; log_cmd "$log" "python3 -m pytest"
          python3 -m pytest --junitxml="$JUNIT_DIR/pytest.xml" >>"$log" 2>&1 || TESTS_RC=1
        fi ;;
      go)
        if have go; then
          if have gotestsum; then
            TESTS_RAN=1; log_cmd "$log" "gotestsum"
            gotestsum --junitfile "$JUNIT_DIR/go.xml" -- ./... >>"$log" 2>&1 || TESTS_RC=1
          else
            TESTS_RAN=1; log_cmd "$log" "go test ./..."; go test ./... >>"$log" 2>&1 || TESTS_RC=1
          fi
        fi ;;
      java)
        if [ -x ./mvnw ]; then
          TESTS_RAN=1; log_cmd "$log" "./mvnw test"; ./mvnw -q test >>"$log" 2>&1 || TESTS_RC=1
        elif [ -x ./gradlew ]; then
          TESTS_RAN=1; log_cmd "$log" "./gradlew test"; ./gradlew test >>"$log" 2>&1 || TESTS_RC=1
        fi ;;
    esac
  done
}

run_coverage() {
  mkdir -p "$COV_DIR"
  local log="$JUNIT_DIR/coverage.txt"
  : >"$log"
  if [ -n "${SDLC_COVERAGE_CMD:-}" ]; then
    COVERAGE_RAN=1; log_cmd "$log" "$SDLC_COVERAGE_CMD"
    bash -c "$SDLC_COVERAGE_CMD" >>"$log" 2>&1 || COVERAGE_RC=1
    return 0
  fi
  local stack
  for stack in $STACKS; do
    case "$stack" in
      python)
        if [ "$PY" = "true" ] && python3 -c 'import coverage, pytest' >/dev/null 2>&1; then
          COVERAGE_RAN=1
          log_cmd "$log" "python3 -m coverage run -m pytest"
          python3 -m coverage run -m pytest >>"$log" 2>&1 || COVERAGE_RC=1
          python3 -m coverage xml -o "$COV_DIR/coverage.xml" >>"$log" 2>&1 || COVERAGE_RC=1
          python3 -m coverage json -o "$COV_DIR/coverage.json" >>"$log" 2>&1 || COVERAGE_RC=1
        fi ;;
      node)
        if have npx; then
          if npx --no-install c8 --version >/dev/null 2>&1; then
            COVERAGE_RAN=1; log_cmd "$log" "c8"
            npx --no-install c8 --reporter=lcov --reporter=json --report-dir="$COV_DIR" npm test >>"$log" 2>&1 || COVERAGE_RC=1
          elif npx --no-install nyc --version >/dev/null 2>&1; then
            COVERAGE_RAN=1; log_cmd "$log" "nyc"
            npx --no-install nyc --reporter=lcov --reporter=cobertura --report-dir="$COV_DIR" npm test >>"$log" 2>&1 || COVERAGE_RC=1
          fi
        fi ;;
      go)
        if have go; then
          COVERAGE_RAN=1; log_cmd "$log" "go test -coverprofile"
          go test -coverprofile="$COV_DIR/coverage.out" ./... >>"$log" 2>&1 || COVERAGE_RC=1
          if have gocov && have gocov-xml; then
            gocov convert "$COV_DIR/coverage.out" 2>>"$log" | gocov-xml >"$COV_DIR/coverage.xml" 2>>"$log" || true
          fi
        fi ;;
      java)
        if [ -x ./mvnw ] && grep -q jacoco pom.xml 2>/dev/null; then
          COVERAGE_RAN=1; log_cmd "$log" "./mvnw test jacoco:report"
          ./mvnw -q test jacoco:report >>"$log" 2>&1 || COVERAGE_RC=1
          [ -f target/site/jacoco/jacoco.xml ] && cp target/site/jacoco/jacoco.xml "$COV_DIR/jacoco.xml" || true
        elif [ -x ./gradlew ]; then
          COVERAGE_RAN=1; log_cmd "$log" "./gradlew test jacocoTestReport"
          ./gradlew test jacocoTestReport >>"$log" 2>&1 || COVERAGE_RC=1
          find . -path '*/jacocoTestReport/*.xml' -exec cp {} "$COV_DIR/" \; 2>/dev/null || true
        fi ;;
    esac
  done
}

run_sast() {
  mkdir -p "$SEC_DIR"
  local log="$REPORTS/security-sast.txt"
  : >"$log"
  if [ -n "${SDLC_SAST_CMD:-}" ]; then
    SAST_RAN=1; log_cmd "$log" "$SDLC_SAST_CMD"
    bash -c "$SDLC_SAST_CMD" >>"$log" 2>&1 || SAST_RC=1
    return 0
  fi
  if have semgrep; then
    SAST_RAN=1; log_cmd "$log" "semgrep"
    semgrep --sarif --config "${SDLC_SEMGREP_CONFIG:-auto}" --output "$SEC_DIR/semgrep.sarif" . >>"$log" 2>&1 || SAST_RC=1
  fi
}

run_deps() {
  mkdir -p "$SEC_DIR"
  local log="$REPORTS/security-deps.txt"
  : >"$log"
  if [ -n "${SDLC_DEPS_CMD:-}" ]; then
    DEPS_RAN=1; log_cmd "$log" "$SDLC_DEPS_CMD"
    bash -c "$SDLC_DEPS_CMD" >>"$log" 2>&1 || DEPS_RC=1
    return 0
  fi
  if have trivy; then
    DEPS_RAN=1; log_cmd "$log" "trivy fs"
    trivy fs --format sarif --output "$SEC_DIR/trivy-fs.sarif" . >>"$log" 2>&1 || DEPS_RC=1
  elif have osv-scanner; then
    DEPS_RAN=1; log_cmd "$log" "osv-scanner"
    osv-scanner --format sarif --output "$SEC_DIR/osv.sarif" -r . >>"$log" 2>&1 || DEPS_RC=1
  fi
}

run_secrets() {
  mkdir -p "$SEC_DIR"
  local log="$REPORTS/security-secrets.txt"
  : >"$log"
  if [ -n "${SDLC_SECRETS_CMD:-}" ]; then
    SECRETS_RAN=1; log_cmd "$log" "$SDLC_SECRETS_CMD"
    bash -c "$SDLC_SECRETS_CMD" >>"$log" 2>&1 || SECRETS_RC=1
    return 0
  fi
  if have gitleaks; then
    SECRETS_RAN=1; log_cmd "$log" "gitleaks detect"
    gitleaks detect --source . --no-banner \
      --report-format sarif --report-path "$SEC_DIR/gitleaks.sarif" >>"$log" 2>&1 || SECRETS_RC=1
  fi
}

run_build() {
  local log="$REPORTS/build.txt"
  : >"$log"
  if [ -n "${SDLC_BUILD_CMD:-}" ]; then
    BUILD_RAN=1; log_cmd "$log" "$SDLC_BUILD_CMD"
    bash -c "$SDLC_BUILD_CMD" >>"$log" 2>&1 || BUILD_RC=1
    return 0
  fi
  local stack
  for stack in $STACKS; do
    case "$stack" in
      node)
        if grep -q '"build"' package.json 2>/dev/null; then
          BUILD_RAN=1; log_cmd "$log" "npm run build"; npm run --silent build >>"$log" 2>&1 || BUILD_RC=1
        fi ;;
      python)
        if [ "$PY" = "true" ] && python3 -c 'import build' >/dev/null 2>&1; then
          BUILD_RAN=1; log_cmd "$log" "python3 -m build"; python3 -m build >>"$log" 2>&1 || BUILD_RC=1
        fi ;;
      go)
        if have go; then
          BUILD_RAN=1; log_cmd "$log" "go build ./..."; go build ./... >>"$log" 2>&1 || BUILD_RC=1
        fi ;;
      java)
        if [ -x ./mvnw ]; then
          BUILD_RAN=1; log_cmd "$log" "./mvnw package"; ./mvnw -q -DskipTests package >>"$log" 2>&1 || BUILD_RC=1
        elif [ -x ./gradlew ]; then
          BUILD_RAN=1; log_cmd "$log" "./gradlew assemble"; ./gradlew assemble >>"$log" 2>&1 || BUILD_RC=1
        fi ;;
    esac
  done
}

# ---------------------------------------------------------------------------
# Exécution séquentielle des contrôles activés
# ---------------------------------------------------------------------------
is_enabled lint     && run_lint     || true
is_enabled tests    && run_tests    || true
is_enabled coverage && run_coverage || true
is_enabled sast     && run_sast     || true
is_enabled deps     && run_deps     || true
is_enabled secrets  && run_secrets  || true
is_enabled build    && run_build    || true

# ---------------------------------------------------------------------------
# Calcul des seuils (couverture + vulnérabilités SARIF)
# ---------------------------------------------------------------------------
COV_PCT="null" COV_MEASURED="false" COV_OK="false"
VULN_CRITIQUE="null" VULN_HAUTE="null" VULN_MOYENNE="null" VULN_BASSE="null"
BLOCK_SAST="false" BLOCK_DEPS="false" BLOCK_SECRETS="false"

kv() { printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -1; }

if [ "$PY" = "true" ] && [ -f "$SCRIPT_DIR/check_thresholds.py" ]; then
  TH_OUT="$(python3 "$SCRIPT_DIR/check_thresholds.py" \
      --coverage-dir "$COV_DIR" \
      --sarif-dir "$SEC_DIR" \
      --coverage-min "$COVERAGE_MIN" \
      --block-on "$BLOCK_ON" \
      --json-out "$THRESHOLDS_FILE" 2>"$REPORTS/thresholds.log" || true)"
  COV_PCT="$(kv "$TH_OUT" coverage_pct)"; [ -n "$COV_PCT" ] || COV_PCT="null"
  COV_MEASURED="$(kv "$TH_OUT" coverage_measured)"; [ -n "$COV_MEASURED" ] || COV_MEASURED="false"
  COV_OK="$(kv "$TH_OUT" coverage_ok)"; [ -n "$COV_OK" ] || COV_OK="false"
  VULN_CRITIQUE="$(kv "$TH_OUT" vulns_critique)"; [ -n "$VULN_CRITIQUE" ] || VULN_CRITIQUE="null"
  VULN_HAUTE="$(kv "$TH_OUT" vulns_haute)"; [ -n "$VULN_HAUTE" ] || VULN_HAUTE="null"
  VULN_MOYENNE="$(kv "$TH_OUT" vulns_moyenne)"; [ -n "$VULN_MOYENNE" ] || VULN_MOYENNE="null"
  VULN_BASSE="$(kv "$TH_OUT" vulns_basse)"; [ -n "$VULN_BASSE" ] || VULN_BASSE="null"
  BLOCK_SAST="$(kv "$TH_OUT" control_sast_blocking)"; [ -n "$BLOCK_SAST" ] || BLOCK_SAST="false"
  BLOCK_DEPS="$(kv "$TH_OUT" control_deps_blocking)"; [ -n "$BLOCK_DEPS" ] || BLOCK_DEPS="false"
  BLOCK_SECRETS="$(kv "$TH_OUT" control_secrets_blocking)"; [ -n "$BLOCK_SECRETS" ] || BLOCK_SECRETS="false"
else
  warn "check_thresholds.py indisponible (python3 requis) : seuils de couverture et de vulnérabilités non calculés."
  warn "couverture et contrôles de sécurité seront marqués « not_run »."
fi

# ---------------------------------------------------------------------------
# Statuts des contrôles
# ---------------------------------------------------------------------------
STATUS_LINT="not_run" STATUS_TESTS="not_run" STATUS_COVERAGE="not_run"
STATUS_SAST="not_run" STATUS_DEPS="not_run" STATUS_SECRETS="not_run" STATUS_BUILD="not_run"

set_if_enabled() {
  # $1 = contrôle, $2 = statut : n'écrit que si le contrôle est activé.
  is_enabled "$1" || return 0
  case "$1" in
    lint) STATUS_LINT="$2";;
    tests) STATUS_TESTS="$2";;
    coverage) STATUS_COVERAGE="$2";;
    sast) STATUS_SAST="$2";;
    deps) STATUS_DEPS="$2";;
    secrets) STATUS_SECRETS="$2";;
    build) STATUS_BUILD="$2";;
  esac
}

simple_status() { # $1 = ran, $2 = rc
  if [ "$1" -eq 0 ]; then printf 'not_run'; elif [ "$2" -ne 0 ]; then printf 'fail'; else printf 'pass'; fi
}

set_if_enabled lint     "$(simple_status "$LINT_RAN" "$LINT_RC")"
set_if_enabled tests    "$(simple_status "$TESTS_RAN" "$TESTS_RC")"
set_if_enabled build    "$(simple_status "$BUILD_RAN" "$BUILD_RC")"

# Couverture : le statut dépend de la mesure.
if is_enabled coverage; then
  if [ "$COVERAGE_RAN" -eq 1 ] && [ "$COVERAGE_RC" -ne 0 ]; then
    STATUS_COVERAGE="fail"
  elif [ "$COV_MEASURED" = "true" ] && [ "$COV_OK" = "true" ]; then
    STATUS_COVERAGE="pass"
  elif [ "$COV_MEASURED" = "true" ]; then
    STATUS_COVERAGE="fail"
  else
    STATUS_COVERAGE="not_run"
    [ "$COVERAGE_RAN" -eq 1 ] && warn "couverture non mesurable : aucun rapport lisible dans $COV_DIR."
  fi
fi

# Sécurité : un outil présent qui tourne mais ne produit pas de SARIF est signalé.
security_status() { # $1 = ran, $2 = rc, $3 = fichier SARIF attendu (peut être vide)
  local ran="$1" rc="$2" sarif="$3"
  [ "$ran" -eq 0 ] && { printf 'not_run'; return; }
  if [ "$rc" -ne 0 ] && { [ -z "$sarif" ] || [ ! -s "$sarif" ]; }; then
    printf 'fail'; return
  fi
  if [ -n "$sarif" ] && [ ! -s "$sarif" ]; then
    warn "aucun rapport SARIF produit ($sarif) : contrôle non vérifiable."
  fi
  printf 'pass'
}

SAST_SARIF="$SEC_DIR/semgrep.sarif"
[ -n "${SDLC_SAST_CMD:-}" ] && SAST_SARIF=""
DEPS_SARIF="$SEC_DIR/trivy-fs.sarif"; [ -s "$DEPS_SARIF" ] || DEPS_SARIF="$SEC_DIR/osv.sarif"
[ -n "${SDLC_DEPS_CMD:-}" ] && DEPS_SARIF=""
SECRETS_SARIF="$SEC_DIR/gitleaks.sarif"
[ -n "${SDLC_SECRETS_CMD:-}" ] && SECRETS_SARIF=""

set_if_enabled sast    "$(security_status "$SAST_RAN" "$SAST_RC" "$SAST_SARIF")"
set_if_enabled deps    "$(security_status "$DEPS_RAN" "$DEPS_RC" "$DEPS_SARIF")"
set_if_enabled secrets "$(security_status "$SECRETS_RAN" "$SECRETS_RC" "$SECRETS_SARIF")"

# Les seuils de vulnérabilités priment sur le statut « pass » des contrôles de sécurité.
if [ "$BLOCK_SAST" = "true" ]; then set_if_enabled sast fail; fi
if [ "$BLOCK_DEPS" = "true" ]; then set_if_enabled deps fail; fi
if [ "$BLOCK_SECRETS" = "true" ]; then set_if_enabled secrets fail; fi

# Si python3 est absent, les contrôles de sécurité ne sont pas exploitables.
if [ "$PY" != "true" ]; then
  set_if_enabled sast not_run
  set_if_enabled deps not_run
  set_if_enabled secrets not_run
fi

# ---------------------------------------------------------------------------
# Fichier de synthèse reports/summary.json
# ---------------------------------------------------------------------------
get_status() {
  case "$1" in
    lint) printf '%s' "$STATUS_LINT";;
    tests) printf '%s' "$STATUS_TESTS";;
    coverage) printf '%s' "$STATUS_COVERAGE";;
    sast) printf '%s' "$STATUS_SAST";;
    deps) printf '%s' "$STATUS_DEPS";;
    secrets) printf '%s' "$STATUS_SECRETS";;
    build) printf '%s' "$STATUS_BUILD";;
  esac
}

# Un contrôle activé mais non exécuté signale un outil ou une stack absents
# (jamais un faux succès). Les contrôles désactivés par --only/--skip sont exclus.
for ctrl in $ALL_CONTROLS; do
  if is_enabled "$ctrl" && [ "$(get_status "$ctrl")" = "not_run" ]; then
    warn "contrôle « $ctrl » non exécuté : outil absent ou aucune stack le fournissant (ou mesure impossible)."
  fi
done

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BLOCKING="false"
for status in "$STATUS_LINT" "$STATUS_TESTS" "$STATUS_COVERAGE" "$STATUS_SAST" \
              "$STATUS_DEPS" "$STATUS_SECRETS" "$STATUS_BUILD"; do
  [ "$status" = "fail" ] && BLOCKING="true"
done

cat >"$SUMMARY_FILE" <<JSON
{
  "ts": "${TS}",
  "controls": {
    "lint": "${STATUS_LINT}",
    "tests": "${STATUS_TESTS}",
    "coverage": "${STATUS_COVERAGE}",
    "sast": "${STATUS_SAST}",
    "deps": "${STATUS_DEPS}",
    "secrets": "${STATUS_SECRETS}",
    "build": "${STATUS_BUILD}"
  },
  "coverage_pct": ${COV_PCT},
  "vulns": {
    "critique": ${VULN_CRITIQUE},
    "haute": ${VULN_HAUTE},
    "moyenne": ${VULN_MOYENNE},
    "basse": ${VULN_BASSE}
  },
  "blocking": ${BLOCKING}
}
JSON

# ---------------------------------------------------------------------------
# Résumé lisible
# ---------------------------------------------------------------------------
label() {
  case "$1" in
    pass) printf 'OK       ';; fail) printf 'ÉCHEC    ';; not_run) printf 'non exécuté';; *) printf '%s' "$1";;
  esac
}

{
  log ""
  log "=========================================================="
  log " Résumé des contrôles — $TS"
  log "=========================================================="
  log " Stacks détectées        : ${STACKS:-(aucune)}"
  log " Seuil de couverture     : ${COVERAGE_MIN} %"
  log " Sévérités bloquantes    : ${BLOCK_ON:-(aucune)}"
  log "----------------------------------------------------------"
  log " lint                    : $(label "$STATUS_LINT")"
  log " tests                   : $(label "$STATUS_TESTS")"
  log " coverage                : $(label "$STATUS_COVERAGE")  (${COV_PCT} %)"
  log " sast (analyse de code)  : $(label "$STATUS_SAST")"
  log " deps (dépendances)      : $(label "$STATUS_DEPS")"
  log " secrets                 : $(label "$STATUS_SECRETS")"
  log " build                   : $(label "$STATUS_BUILD")"
  log "----------------------------------------------------------"
  log " Vulnérabilités          : critique=${VULN_CRITIQUE} haute=${VULN_HAUTE} moyenne=${VULN_MOYENNE} basse=${VULN_BASSE}"
  log " Résultat                : $([ "$BLOCKING" = "true" ] && echo 'BLOQUANT' || echo 'non bloquant')"
  log " Rapports                : $SUMMARY_FILE"
  log "=========================================================="
} >&2

if [ "$BLOCKING" = "true" ]; then
  exit 1
fi
exit 0
