"""Bac à sable des agents : environnement purgé et Git en lecture seule."""

from __future__ import annotations

import json
import os
import shlex
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import Project, TaskRun
from .audit import append_audit

# Fragments de noms de variables qui ne doivent jamais être hérités. On ne
# filtre pas « KEY » seul pour conserver PATH, HOME, etc.
SENSITIVE_ENV_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "credential",
)
EXACT_SENSITIVE_ENV = frozenset(
    {
        "SSH_AUTH_SOCK",
        "GPG_AGENT_INFO",
        "GIT_ASKPASS",
        "GIT_CONFIG_PARAMETERS",
    }
)

# Sous-commandes Git qui ne modifient ni les objets, ni les refs, ni le worktree.
GIT_READ_ONLY = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "rev-parse",
        "describe",
        "ls-files",
        "blame",
        "cat-file",
        "grep",
        "version",
        "help",
        "rev-list",
        "shortlog",
        "whatchanged",
    }
)


def is_sensitive_env(name: str) -> bool:
    """Vrai si la variable peut contenir un secret du serveur."""
    upper = name.upper()
    if upper in EXACT_SENSITIVE_ENV:
        return True
    lowered = name.lower()
    return any(fragment in lowered for fragment in SENSITIVE_ENV_FRAGMENTS)


def sanitized_environment(
    base: Mapping[str, str] | None = None,
    *,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Copie l'environnement en retirant jetons, mots de passe et secrets."""
    source = dict(os.environ if base is None else base)
    clean = {name: value for name, value in source.items() if not is_sensitive_env(name)}
    if extra:
        for name, value in extra.items():
            if not is_sensitive_env(name):
                clean[name] = value
    return clean


def _guard_script(real_git: str) -> str:
    quoted_git = shlex.quote(real_git)
    return f"""#!/bin/sh
# Généré par la Console SDLC : refuse les écritures Git des agents.
real_git={quoted_git}
audit="$SDLC_GIT_AUDIT_LOG"
run_id="$SDLC_RUN_ID"
refuse() {{
  printf '{{"run_id":"%s","command":"git %s","reason":"git_write_refused"}}\\n' \
    "$run_id" "$*" >> "$audit"
  echo "git en écriture refusé par la Console SDLC" >&2
  exit 126
}}
if [ "$#" -eq 0 ]; then
  refuse ""
fi
cmd="$1"
shift
case "$cmd" in
  status|diff|log|show|rev-parse|describe|ls-files|blame|cat-file|grep|version|help|rev-list|shortlog|whatchanged)
    exec "$real_git" "$cmd" "$@"
    ;;
  branch)
    if [ "$#" -eq 0 ] || [ "$1" = "--list" ] || [ "$1" = "-l" ] || [ "$1" = "-a" ]; then
      exec "$real_git" "$cmd" "$@"
    fi
    refuse "branch $*"
    ;;
  tag)
    if [ "$#" -eq 0 ] || [ "$1" = "--list" ] || [ "$1" = "-l" ]; then
      exec "$real_git" "$cmd" "$@"
    fi
    refuse "tag $*"
    ;;
  remote)
    if [ "$#" -eq 0 ] || [ "$1" = "-v" ] || [ "$1" = "show" ] || [ "$1" = "get-url" ]; then
      exec "$real_git" "$cmd" "$@"
    fi
    refuse "remote $*"
    ;;
  config)
    if [ "$#" -gt 0 ]; then
      case "$1" in
        --get|--list|-l|--get-regexp)
          exec "$real_git" "$cmd" "$@"
          ;;
      esac
    fi
    refuse "config $*"
    ;;
  *)
    refuse "$cmd $*"
    ;;
esac
"""


def install_git_guard(
    root: str | Path,
    run_id: str,
    *,
    base_env: Mapping[str, str] | None = None,
    read_only: bool = False,
) -> tuple[dict[str, str], Path, Path | None]:
    """Installe un `git` de garde et retourne l'environnement et le journal d'audit."""
    root_path = Path(root).resolve()
    guard_dir = root_path / "reports" / "runs" / f"{run_id}-git"
    guard_dir.mkdir(parents=True, exist_ok=True)
    audit_path = guard_dir / "refusals.jsonl"
    audit_path.touch(exist_ok=True)
    env = sanitized_environment(
        base_env,
        extra={
            "SDLC_GIT_AUDIT_LOG": str(audit_path),
            "SDLC_RUN_ID": run_id,
            "SDLC_READ_ONLY": "1" if read_only else "0",
        },
    )
    real_git = shutil.which("git")
    if real_git is None:
        return env, audit_path, None
    guard = guard_dir / "git"
    guard.write_text(_guard_script(real_git), encoding="utf-8")
    guard.chmod(0o755)
    env["PATH"] = f"{guard_dir}{os.pathsep}{env.get('PATH', '')}"
    return env, audit_path, guard


def git_refusals(audit_path: str | Path) -> list[dict[str, Any]]:
    """Lit les tentatives d'écriture Git consignées par le garde."""
    path = Path(audit_path)
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            entries.append(value)
    return entries


def audit_git_refusals(
    session: Session,
    project: Project,
    run: TaskRun,
    *,
    root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Audite une seule fois les refus Git d'un run, puis marque le journal."""
    root_path = Path(root or Path.cwd()).resolve()
    audit_path = root_path / "reports" / "runs" / f"{run.run_id}-git" / "refusals.jsonl"
    entries = git_refusals(audit_path)
    if not entries:
        return []
    for entry in entries:
        append_audit(
            session,
            project_id=project.id,
            action="agent.git_write_refused",
            object_type="run",
            object_id=run.run_id,
            actor_label=f"agent {run.agent_id or 'inconnu'}",
            payload={
                "command": str(entry.get("command") or ""),
                "reason": str(entry.get("reason") or "git_write_refused"),
                "read_only": bool(run.role == "reviewer"),
            },
        )
    audit_path.write_text("", encoding="utf-8")
    return entries
