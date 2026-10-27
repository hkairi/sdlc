#!/usr/bin/env python3
"""state_io.py — lecture, écriture atomique et utilitaires de `docs/suivi/state.json`.

Le format est décrit dans `references/state-format.md` (format commun partagé avec la
skill `suivi-projet`, qui le lit en lecture seule). Ce module est la brique commune des scripts
`generate.py`, `render.py`, `track*.py` et `migrate_from_html.py` : ils n'écrivent jamais
le HTML directement, ils mettent à jour l'état puis le rendent.
"""
import datetime
import json
import os
import re
import tempfile

DEFAULT_STATE_PATH = os.path.join("docs", "suivi", "state.json")
DEFAULT_CONFIG_PATH = "sdlc.config.yaml"
STATUSES = ("todo", "doing", "blocked", "done")


def today():
    return datetime.date.today().isoformat()


def default_state():
    """État vide conforme au schéma (rien d'inventé)."""
    return {
        "schema": 1,
        "meta": {},
        "file_updated": None,
        "features": [],
        "actions": [],
        "envs": [],
    }


def load_state(path):
    """Lit `state.json`. Fichier absent ou illisible → état vide (jamais d'erreur bloquante)."""
    if not path or not os.path.isfile(path):
        return default_state()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return default_state()
    if not isinstance(data, dict):
        return default_state()
    data.setdefault("schema", 1)
    data.setdefault("meta", {})
    data.setdefault("file_updated", None)
    if not isinstance(data.get("features"), list):
        data["features"] = []
    if not isinstance(data.get("actions"), list):
        data["actions"] = []
    if not isinstance(data.get("envs"), list):
        data["envs"] = []
    return data


def save_state(path, state):
    """Écrit `state.json` de façon **atomique** : fichier temporaire puis renommage."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def read_max_review_iterations(config_path=DEFAULT_CONFIG_PATH, default=3):
    """Lit `organisation.max_review_iterations` dans `sdlc.config.yaml` (défaut 3).

    Lecture minimale et tolérante (pas de dépendance à PyYAML) : on cherche la clé
    `max_review_iterations` à n'importe quelle indentation sous `organisation`.
    """
    if not config_path or not os.path.isfile(config_path):
        return default
    try:
        with open(config_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return default
    m = re.search(r"^\s*max_review_iterations\s*:\s*([0-9]+)\s*(?:#.*)?$", text, re.M)
    return int(m.group(1)) if m else default


def find_feature(state, fid):
    for feature in state.get("features") or []:
        if feature.get("id") == fid:
            return feature
    return None


def find_task(feature, tid):
    for task in feature.get("tasks") or []:
        if task.get("id") == tid:
            return task
    return None


def task_stats(tasks):
    counts = {"todo": 0, "doing": 0, "blocked": 0, "done": 0, "total": 0}
    for task in tasks or []:
        status = task.get("status", "todo")
        if status not in STATUSES:
            status = "todo"
        counts[status] += 1
        counts["total"] += 1
    return counts


def add_history(task, status, note, date=None):
    """Ajoute une entrée d'historique datée (idempotente sur le dernier état identique)."""
    date = date or today()
    history = task.setdefault("history", [])
    last = history[-1] if history else None
    if last and last.get("status") == status and last.get("note") == note and last.get("date") == date:
        return
    history.append({"date": date, "status": status, "note": note})
