#!/usr/bin/env python3
"""Modèle de phases partagé par les gabarits et scripts de la skill suivi-taches.

Un chantier (un change OpenSpec) traverse six phases :

  1. cadrage    — proposition, deltas de specs, design, décisions, validation, approbation
  2. plan       — tasks.md, dépendances, fichier de suivi
  3. impl       — implémentation (état DÉRIVÉ des tâches, pas de checklist propre)
  4. validation — tests, linter, typecheck, critères d'acceptation, revue, conformité aux specs
  5. deploy     — migrations, env/secrets, runbook, production, smoke test
  6. cloture    — archive OpenSpec, docs (features/architecture/runbook), suivi post-déploiement, retour

Chaque phase (sauf impl) porte une checklist d'items ; le statut d'une phase est dérivé de
ses items (done si tout est done, blocked si un item est blocked, doing si un item est
doing/done, sinon todo). L'état de référence de chaque item (statut, date, note) vit dans
le fichier de suivi ; le script track_phase.py le met à jour.
"""
import copy

STATUSES = ("todo", "doing", "blocked", "done")
LABELS = {"todo": "À faire", "doing": "En cours", "blocked": "Bloqué", "done": "Terminé"}

# Couleurs par phase (segments du bandeau, pastilles).
PHASE_COLORS = {
    "cadrage": "#5c6b7a", "plan": "#0f4c81", "impl": "#2b6cb0",
    "validation": "#b7791f", "deploy": "#7d3c98", "cloture": "#1f9d55",
}

# Checklist par défaut (générique, alignée sur le workflow OpenSpec et les règles du projet).
DEFAULT_PHASES = [
    {"id": "cadrage", "name": "Cadrage", "items": [
        ("proposal", "Proposition rédigée (proposal.md : Why / What / Impact)"),
        ("deltas", "Deltas de specs (## ADDED|MODIFIED|REMOVED, ≥1 scénario)"),
        ("design", "design.md si changement transversal, dépendance externe ou modèle de données"),
        ("validate", "openspec validate <id> --strict sans erreur"),
        ("decisions", "Décisions tranchées consignées"),
        ("approval", "Proposition approuvée avant implémentation"),
    ]},
    {"id": "plan", "name": "Planification", "items": [
        ("tasks", "tasks.md découpé en lots et tâches"),
        ("deps", "Dépendances externes identifiées"),
        ("tracking", "Fichier de suivi généré"),
    ]},
    {"id": "impl", "name": "Implémentation", "items": []},  # état dérivé des tâches
    {"id": "validation", "name": "Validation", "items": [
        ("tests", "Tests relancés (suites concernées, 0 échec)"),
        ("lint", "Linter / formateur : 0 offense"),
        ("typecheck", "Compilation / typecheck OK sur les surfaces touchées"),
        ("acceptance", "Critères d'acceptation vérifiés"),
        ("review", "Revue de code / relecture"),
        ("specs", "Comportement conforme aux deltas de specs"),
    ]},
    {"id": "deploy", "name": "Déploiement", "items": [
        ("migrations", "Migrations réversibles, up/down testés"),
        ("env", "Variables d'environnement et secrets à jour"),
        ("runbook", "Étapes de déploiement / runbook à jour"),
        ("prod", "Déployé en production"),
        ("smoke", "Smoke test post-déploiement"),
    ]},
    {"id": "cloture", "name": "Clôture", "items": [
        ("archive", "Change archivé (openspec archive)"),
        ("docs_features", "features.md à jour"),
        ("docs_architecture", "architecture.md à jour si archi / infra"),
        ("docs_runbook", "runbook.md à jour si setup / env / procédure"),
        ("monitoring", "Suivi post-déploiement (logs, métriques, incidents)"),
        ("retro", "Écarts et retour consignés"),
    ]},
]


def _normalize_item(raw):
    if isinstance(raw, str):
        return {"id": raw, "label": raw, "status": "todo", "updated": "", "note": ""}
    if isinstance(raw, (tuple, list)):
        return {"id": raw[0], "label": raw[1] if len(raw) > 1 else raw[0], "status": "todo", "updated": "", "note": ""}
    return {
        "id": raw["id"],
        "label": raw.get("label", raw["id"]),
        "status": raw.get("status", "todo"),
        "updated": raw.get("updated", ""),
        "note": raw.get("note", ""),
    }


def _normalize_phase(raw, index):
    items = raw.get("items", [])
    return {
        "id": raw["id"],
        "name": raw.get("name") or raw["id"].capitalize(),
        "color": raw.get("color") or PHASE_COLORS.get(raw["id"]) or "#5c6b7a",
        "order": raw.get("order", index + 1),
        "items": [_normalize_item(i) for i in items],
    }


def default_phases():
    """Phases par défaut, items à « todo »."""
    return [_normalize_phase(p, i) for i, p in enumerate(copy.deepcopy(DEFAULT_PHASES))]


def build_phases(override=None, prev=None):
    """Construit les phases d'un chantier en conservant l'état des items d'une version précédente.

    override : liste de phases du manifeste (remplace les défauts) ; None → défauts.
    prev     : phases déjà présentes dans le fichier --out (état conservé : status/updated/note).
    """
    base = default_phases() if not override else [_normalize_phase(p, i) for i, p in enumerate(override)]
    prev_index = {}
    for p in (prev or []):
        for it in p.get("items", []):
            prev_index[(p.get("id"), it.get("id"))] = it
        prev_index[("__phase__", p.get("id"))] = p
    for phase in base:
        prev_phase = prev_index.get(("__phase__", phase["id"]))
        if prev_phase:
            if prev_phase.get("name"):
                phase["name"] = prev_phase["name"]
            if prev_phase.get("color"):
                phase["color"] = prev_phase["color"]
        for item in phase["items"]:
            old = prev_index.get((phase["id"], item["id"]))
            if old:
                item["status"] = old.get("status", item["status"])
                item["updated"] = old.get("updated", "")
                item["note"] = old.get("note", "")
    return base


def impl_status(stats):
    """Statut de la phase Implémentation, dérivé des tâches."""
    if not stats or not stats.get("total"):
        return "todo"
    if stats["done"] >= stats["total"]:
        return "done"
    if stats.get("blocked", 0) > 0:
        return "blocked"
    if stats.get("doing", 0) > 0 or stats["done"] > 0:
        return "doing"
    return "todo"


def phase_status(phase, stats=None):
    """Statut d'une phase : dérivé des tâches pour « impl », sinon de ses items."""
    if phase.get("id") == "impl":
        return impl_status(stats)
    statuses = [i.get("status", "todo") for i in phase.get("items", [])]
    if not statuses:
        return "todo"
    if all(s == "done" for s in statuses):
        return "done"
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s in ("doing", "done") for s in statuses):
        return "doing"
    return "todo"


def phase_progress(phase, stats=None):
    """(faits, total) d'une phase."""
    if phase.get("id") == "impl":
        return (stats.get("done", 0), stats.get("total", 0)) if stats else (0, 0)
    items = phase.get("items", [])
    return (sum(1 for i in items if i.get("status") == "done"), len(items))


def current_phase(phases, stats=None):
    """Phase en cours : première non terminée, sinon la dernière."""
    for phase in phases:
        if phase_status(phase, stats) != "done":
            return phase
    return phases[-1] if phases else None


def task_stats(tasks):
    """Compteurs de tâches dérivés : {"todo", "doing", "blocked", "done", "total"}."""
    counts = {"todo": 0, "doing": 0, "blocked": 0, "done": 0, "total": 0}
    for task in tasks or []:
        status = task.get("status", "todo")
        if status not in ("todo", "doing", "blocked", "done"):
            status = "todo"
        counts[status] += 1
        counts["total"] += 1
    return counts


def refresh_statuses(phases, tasks=None):
    """Recalcule et pose `status` sur chaque phase (dérivé des items et des tâches)."""
    stats = task_stats(tasks)
    for phase in phases or []:
        phase["status"] = phase_status(phase, stats)
    return phases
