#!/usr/bin/env bash
# detect.sh — détection de l'environnement d'un projet pour la skill `sdlc-init`.
#
# Renvoie sur **stdout** un objet JSON (rien d'autre sur stdout) décrivant :
#   - les CLI d'agents installées (`claude`, `codex`, `opencode`, via `command -v`) ;
#   - le type de projet (`new` ou `existing`) ;
#   - la stack détectée (indices de fichiers) ;
#   - l'outil de CI existant, s'il y en a un ;
#   - la présence d'un déploiement existant ;
#   - les commandes existantes de test, de lint et de couverture, proposées en
#     variables `SDLC_<CONTRÔLE>_CMD` (SDLC_TEST_CMD, SDLC_LINT_CMD,
#     SDLC_COVERAGE_CMD) pour `scripts/ci.sh`.
#
# Les diagnostics et les avertissements vont sur stderr.
#
# Usage :
#   detect.sh [RACINE]
#
#   RACINE   racine du projet à analyser (défaut : répertoire courant).
#
# Code de sortie :
#   0  détection effectuée (le JSON est valide) ;
#   2  erreur d'usage (racine introuvable) ;
#   3  `python3` absent (utilisé seulement pour valider/assembler le JSON).

set -euo pipefail

usage() {
  sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

ROOT="${1:-.}"
if [ ! -d "$ROOT" ]; then
  printf 'detect.sh : racine introuvable : %s\n' "$ROOT" >&2
  exit 2
fi

# Normalise en chemin absolu.
ROOT="$(cd "$ROOT" && pwd)"

# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

# Échappe une chaîne pour une valeur JSON (sans les guillemets).
json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/ }"
  s="${s//$'\r'/ }"
  s="${s//$'\t'/ }"
  printf '%s' "$s"
}

# Vrai si la commande est installée.
cli_installed() {
  command -v "$1" >/dev/null 2>&1
}

# Vrai si au moins un des fichiers/globs existe dans la racine (maxdepth 2 pour les globs).
exists_any() {
  local pattern
  for pattern in "$@"; do
    # shellcheck disable=SC2086
    if compgen -G "$ROOT/$pattern" >/dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}

# Vrai si le dossier existe et contient au moins un fichier.
dir_has_files() {
  [ -d "$ROOT/$1" ] || return 1
  # shellcheck disable=SC2046
  [ -n "$(find "$ROOT/$1" -mindepth 1 -maxdepth 1 -type f -print -quit 2>/dev/null)" ]
}

# Vrai si un fichier texte contient un motif (lecture seule).
file_contains() {
  local file="$1" pattern="$2"
  [ -f "$ROOT/$file" ] && grep -Eq "$pattern" "$ROOT/$file" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Détection de la stack
# ---------------------------------------------------------------------------
STACK=()

add_stack() {
  local value="$1" existing
  for existing in ${STACK[@]+"${STACK[@]}"}; do
    [ "$existing" = "$value" ] && return 0
  done
  STACK+=("$value")
}

detect_stack() {
  # Ruby / Rails
  if exists_any "Gemfile" "*.gemspec" "config/application.rb"; then
    if [ -f "$ROOT/config/application.rb" ]; then
      add_stack "rails"
    fi
    add_stack "ruby"
  fi
  # Node / JS / TS
  if [ -f "$ROOT/package.json" ]; then
    add_stack "node"
    [ -f "$ROOT/angular.json" ] && add_stack "angular"
    exists_any "next.config.js" "next.config.mjs" "next.config.ts" && add_stack "nextjs"
    exists_any "nuxt.config.js" "nuxt.config.ts" && add_stack "nuxt"
    exists_any "svelte.config.js" && add_stack "svelte"
    exists_any "vite.config.js" "vite.config.ts" && add_stack "vite"
    [ -f "$ROOT/nest-cli.json" ] && add_stack "nestjs"
  fi
  # Python / Django
  if exists_any "pyproject.toml" "requirements.txt" "setup.py" "setup.cfg" "Pipfile"; then
    [ -f "$ROOT/manage.py" ] && add_stack "django"
    add_stack "python"
  fi
  # Go
  [ -f "$ROOT/go.mod" ] && add_stack "go"
  # Java
  [ -f "$ROOT/pom.xml" ] && add_stack "maven"
  exists_any "build.gradle" "build.gradle.kts" && add_stack "gradle"
  # PHP
  if [ -f "$ROOT/composer.json" ]; then
    [ -f "$ROOT/artisan" ] && add_stack "laravel"
    add_stack "php"
  fi
  # .NET
  exists_any "*.csproj" "*.sln" && add_stack "dotnet"
  # Rust
  [ -f "$ROOT/Cargo.toml" ] && add_stack "rust"
  # Dart / Flutter
  [ -f "$ROOT/pubspec.yaml" ] && add_stack "dart"
  # Conteneurs (transversal)
  exists_any "Dockerfile" "docker-compose.yml" "docker-compose.yaml" "compose.yml" "compose.yaml" && add_stack "docker"
}

# ---------------------------------------------------------------------------
# Détection de la CI existante
# ---------------------------------------------------------------------------
CI_TOOL="none"
CI_FILES=()

detect_ci() {
  if dir_has_files ".github/workflows"; then
    CI_TOOL="github-actions"
    for f in "$ROOT/.github/workflows/"*.yml "$ROOT/.github/workflows/"*.yaml; do
      [ -f "$f" ] || continue
      CI_FILES+=(".github/workflows/$(basename "$f")")
    done
  fi
  if [ -f "$ROOT/.gitlab-ci.yml" ]; then
    CI_TOOL="gitlab-ci"
    CI_FILES+=(".gitlab-ci.yml")
  fi
  if dir_has_files ".forgejo/workflows"; then
    CI_TOOL="forgejo-actions"
    CI_FILES+=(".forgejo/workflows/")
  elif dir_has_files ".gitea/workflows"; then
    CI_TOOL="forgejo-actions"
    CI_FILES+=(".gitea/workflows/")
  fi
  if [ -f "$ROOT/Jenkinsfile" ]; then
    CI_TOOL="jenkins"
    CI_FILES+=("Jenkinsfile")
  fi
}

# ---------------------------------------------------------------------------
# Détection d'un déploiement existant
# ---------------------------------------------------------------------------
DEPLOY_SIGNALS=()

detect_deploy() {
  local f
  if exists_any "docker-compose.yml" "docker-compose.yaml" "compose.yml" "compose.yaml"; then
    DEPLOY_SIGNALS+=("docker-compose")
  fi
  if [ -d "$ROOT/k8s" ] || [ -d "$ROOT/kubernetes" ] || [ -d "$ROOT/manifests" ]; then
    DEPLOY_SIGNALS+=("kubernetes")
  fi
  exists_any "serverless.yml" "serverless.yaml" && DEPLOY_SIGNALS+=("serverless")
  exists_any "fly.toml" "render.yaml" "Procfile" "heroku.yml" "app.yaml" "railway.json" && DEPLOY_SIGNALS+=("paas")
  exists_any "netlify.toml" "vercel.json" && DEPLOY_SIGNALS+=("static")
  # Indices dans la CI existante (étape de déploiement).
  for f in ${CI_FILES[@]+"${CI_FILES[@]}"}; do
    if file_contains "$f" '(^|[^a-z])(deploy|kubectl|helm|ansible|rsync|ssh)' ; then
      DEPLOY_SIGNALS+=("ci-deploy")
      break
    fi
  done
}

# ---------------------------------------------------------------------------
# Détection des commandes existantes (test, lint, couverture)
# ---------------------------------------------------------------------------
CMD_TEST="" CMD_LINT="" CMD_COVERAGE=""

# Vrai si le script npm nommé existe dans package.json.
pkg_has_script() {
  [ -f "$ROOT/package.json" ] && grep -Eq "\"$1\"[[:space:]]*:" "$ROOT/package.json" 2>/dev/null
}

# Vrai si la cible Makefile existe.
make_has_target() {
  [ -f "$ROOT/Makefile" ] && grep -Eq "^$1[[:space:]]*:" "$ROOT/Makefile" 2>/dev/null
}

detect_commands() {
  # Node / npm : scripts package.json.
  if [ -f "$ROOT/package.json" ]; then
    if pkg_has_script test; then CMD_TEST="npm test"; fi
    if pkg_has_script lint; then CMD_LINT="npm run lint"; fi
    if pkg_has_script coverage; then
      CMD_COVERAGE="npm run coverage"
    elif pkg_has_script "test:coverage"; then
      CMD_COVERAGE="npm run test:coverage"
    fi
  fi
  # Makefile : cibles usuelles.
  if [ -f "$ROOT/Makefile" ]; then
    if [ -z "$CMD_TEST" ] && make_has_target test; then CMD_TEST="make test"; fi
    if [ -z "$CMD_LINT" ] && make_has_target lint; then CMD_LINT="make lint"; fi
    if [ -z "$CMD_COVERAGE" ]; then
      if make_has_target coverage; then CMD_COVERAGE="make coverage"
      elif make_has_target cover; then CMD_COVERAGE="make cover"; fi
    fi
  fi
  # Python : pytest et coverage.
  if [ -z "$CMD_TEST" ]; then
    if [ -f "$ROOT/pytest.ini" ] || [ -f "$ROOT/tox.ini" ] \
      || { [ -f "$ROOT/pyproject.toml" ] && grep -Eq "pytest" "$ROOT/pyproject.toml" 2>/dev/null; } \
      || { [ -f "$ROOT/requirements.txt" ] && grep -Eq "pytest" "$ROOT/requirements.txt" 2>/dev/null; } \
      || { [ -f "$ROOT/setup.cfg" ] && grep -Eq "pytest" "$ROOT/setup.cfg" 2>/dev/null; } \
      || [ -d "$ROOT/tests" ]; then
      CMD_TEST="python3 -m pytest"
    fi
  fi
  if [ -z "$CMD_COVERAGE" ]; then
    if [ -f "$ROOT/.coveragerc" ] \
      || { [ -f "$ROOT/pyproject.toml" ] && grep -Eq "coverage" "$ROOT/pyproject.toml" 2>/dev/null; } \
      || { [ -f "$ROOT/requirements.txt" ] && grep -Eq "coverage" "$ROOT/requirements.txt" 2>/dev/null; }; then
      CMD_COVERAGE="python3 -m coverage run -m pytest && python3 -m coverage report"
    fi
  fi
  # Ruby : rspec et rubocop.
  if [ -z "$CMD_TEST" ] && [ -f "$ROOT/Gemfile" ]; then
    if [ -d "$ROOT/spec" ] || [ -f "$ROOT/.rspec" ]; then CMD_TEST="bundle exec rspec"; fi
    if [ -z "$CMD_LINT" ] && [ -f "$ROOT/.rubocop.yml" ]; then CMD_LINT="bundle exec rubocop"; fi
  fi
  # Go.
  if [ -z "$CMD_TEST" ] && [ -f "$ROOT/go.mod" ]; then
    CMD_TEST="go test ./..."
    if [ -z "$CMD_LINT" ]; then CMD_LINT="go vet ./..."; fi
    if [ -z "$CMD_COVERAGE" ]; then CMD_COVERAGE="go test -coverprofile=coverage.out ./..."; fi
  fi
  # Java : Maven et Gradle.
  if [ -z "$CMD_TEST" ]; then
    if [ -f "$ROOT/pom.xml" ]; then
      if [ -x "$ROOT/mvnw" ]; then CMD_TEST="./mvnw test"; else CMD_TEST="mvn test"; fi
    elif [ -f "$ROOT/build.gradle" ] || [ -f "$ROOT/build.gradle.kts" ]; then
      if [ -x "$ROOT/gradlew" ]; then CMD_TEST="./gradlew test"; else CMD_TEST="gradle test"; fi
    fi
  fi
  # Lean : pour Python, proposer la couverture si pytest est utilisé mais qu'aucun
  # outil de couverture n'est configuré.
  if [ -z "$CMD_COVERAGE" ] && [ "$CMD_TEST" = "python3 -m pytest" ]; then
    CMD_COVERAGE="python3 -m coverage run -m pytest && python3 -m coverage report"
  fi
}

# ---------------------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------------------
HAS_CODE=false
if detect_stack; then :; fi

# Code applicatif : un manifeste de stack ou un dossier source typique.
if [ "${#STACK[@]}" -gt 0 ] \
  || [ -d "$ROOT/src" ] || [ -d "$ROOT/app" ] || [ -d "$ROOT/lib" ] \
  || [ -d "$ROOT/tests" ] || [ -d "$ROOT/test" ]; then
  HAS_CODE=true
fi

detect_ci
detect_deploy
detect_commands

CLAUDE_CLI=false; cli_installed claude && CLAUDE_CLI=true
CODEX_CLI=false;  cli_installed codex && CODEX_CLI=true
OPENCODE_CLI=false; cli_installed opencode && OPENCODE_CLI=true

# Nom du projet : nom de package.json s'il existe, sinon nom du dossier.
PROJECT_NAME="$(basename "$ROOT")"
if [ -f "$ROOT/package.json" ]; then
  PKG_NAME="$(grep -E '"name"[[:space:]]*:' "$ROOT/package.json" 2>/dev/null | head -n1 | sed -E 's/.*"name"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/')"
  [ -n "$PKG_NAME" ] && PROJECT_NAME="$PKG_NAME"
fi

# Type de projet.
if [ "$HAS_CODE" = true ] || [ "$CI_TOOL" != "none" ] || [ "${#DEPLOY_SIGNALS[@]}" -gt 0 ]; then
  PROJECT_KIND="existing"
else
  PROJECT_KIND="new"
fi

# Assemblage du JSON (via python3 pour garantir l'échappement).
if ! command -v python3 >/dev/null 2>&1; then
  printf 'detect.sh : python3 est requis pour assembler le JSON\n' >&2
  exit 3
fi

STACK_JSON="$(printf '%s\n' ${STACK[@]+"${STACK[@]}"})"
CI_FILES_JSON="$(printf '%s\n' ${CI_FILES[@]+"${CI_FILES[@]}"})"
DEPLOY_JSON="$(printf '%s\n' ${DEPLOY_SIGNALS[@]+"${DEPLOY_SIGNALS[@]}"})"

ROOT="$ROOT" PROJECT_NAME="$PROJECT_NAME" PROJECT_KIND="$PROJECT_KIND" \
HAS_CODE="$HAS_CODE" CLAUDE_CLI="$CLAUDE_CLI" CODEX_CLI="$CODEX_CLI" \
OPENCODE_CLI="$OPENCODE_CLI" CI_TOOL="$CI_TOOL" \
STACK_JSON="$STACK_JSON" CI_FILES_JSON="$CI_FILES_JSON" DEPLOY_JSON="$DEPLOY_JSON" \
CMD_TEST="$CMD_TEST" CMD_LINT="$CMD_LINT" CMD_COVERAGE="$CMD_COVERAGE" \
python3 - <<'PY'
import json
import os

def lines(name):
    return [line for line in os.environ.get(name, "").splitlines() if line]

def boolean(name):
    return os.environ.get(name, "false").lower() == "true"

def scalar(name):
    value = os.environ.get(name, "").strip()
    return value or None

commands = {
    "test": scalar("CMD_TEST"),
    "lint": scalar("CMD_LINT"),
    "coverage": scalar("CMD_COVERAGE"),
}
env_commands = {}
for control, var in (("test", "SDLC_TEST_CMD"), ("lint", "SDLC_LINT_CMD"),
                     ("coverage", "SDLC_COVERAGE_CMD")):
    if commands[control]:
        env_commands[var] = commands[control]

payload = {
    "tool": "detect",
    "found": True,
    "root": os.environ["ROOT"],
    "project": {
        "name": os.environ["PROJECT_NAME"],
        "kind": os.environ["PROJECT_KIND"],
        "has_code": boolean("HAS_CODE"),
        "stack": lines("STACK_JSON"),
    },
    "cli": {
        "claude": boolean("CLAUDE_CLI"),
        "codex": boolean("CODEX_CLI"),
        "opencode": boolean("OPENCODE_CLI"),
    },
    "ci": {
        "detected": os.environ["CI_TOOL"],
        "files": lines("CI_FILES_JSON"),
    },
    "deploy": {
        "detected": bool(lines("DEPLOY_JSON")),
        "signals": lines("DEPLOY_JSON"),
    },
    "commands": commands,
    "env": env_commands,
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY
