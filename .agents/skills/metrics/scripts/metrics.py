#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""metrics.py — indicateurs du projet depuis les journaux du framework SDLC.

Lecture seule ; aucune dépendance externe (bibliothèque standard Python 3.9+).

Entrées (relatives à la racine du projet) :
  docs/journal/runs.jsonl      une ligne par délégation d'agent (§ 12 de la spec)
  docs/journal/deploys.jsonl   une ligne par déploiement (§ 12)
  docs/metrics/history.jsonl   instantanés du tableau de bord (skill suivi-projet)
  sdlc.config.yaml (optionnel) pour organisation.max_review_iterations et
                               organisation.task_timeout_min

Indicateurs produits
--------------------
  - tâches par agent ;
  - part validée dès la 1re revue ;
  - escalades ;
  - délai spec -> production (si calculable) ;
  - nombre de rollbacks ;
  - compteurs de contexte (runs par statut, déploiements par résultat/environnement).

Toute valeur non mesurable s'affiche « non mesuré » ; aucune valeur n'est inventée.

Conventions de calcul (documentées)
-----------------------------------
- Part validée dès la 1re revue : parmi les runs dont `review_iteration` est
  renseigné (tâches entrées en revue), part de ceux avec `review_iteration == 1`
  ET `status == "done"`.
- Escalade : run avec `status == "blocked"`, OU `review_iteration` >=
  `organisation.max_review_iterations`, OU `duration_s` > `organisation.task_timeout_min`
  x 60. Un même run peut relever de plusieurs motifs ; il n'est compté qu'une fois
  au total (le détail par motif peut donc sommer au-delà du total).
- Délai spec -> production : pour chaque fonctionnalité ayant un `spec_freeze_ts`
  (champ optionnel d'un run ou d'un instantané d'historique) ET un déploiement de
  production (`env` dans prod/production/prd/pro) portant le même champ `feature`
  (champ optionnel, hors § 12), on calcule la durée entre les deux. Sinon : non mesuré.

Usage :
  python3 metrics.py [RACINE] [--out FICHIER] [--config FICHIER] [--stdout] [--help]

  RACINE         racine du projet (défaut : répertoire courant).
  --out FICHIER  fichier Markdown de sortie
                 (défaut : <RACINE>/docs/metrics/indicateurs.md).
  --config       chemin de sdlc.config.yaml (défaut : <RACINE>/sdlc.config.yaml).
  --stdout       écrit le Markdown sur la sortie standard au lieu d'un fichier.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

PROD_ENVS = {"prod", "production", "prd", "pro"}
DEFAULT_MAX_REVIEWS = 3
DEFAULT_TIMEOUT_MIN = 30

NON_MESURE = "non mesuré"


# --------------------------------------------------------------------------
# Lecture
# --------------------------------------------------------------------------
def _read_text(path) -> "str | None":
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def load_jsonl(path):
    """Renvoie (lignes, erreurs).

    - fichier absent  -> lignes = None, erreurs = [] ;
    - ligne vide      -> ignorée ;
    - ligne invalide  -> message d'erreur, ligne ignorée.
    """
    text = _read_text(path)
    if text is None:
        return None, []
    lines = []
    errors = []
    for num, raw in enumerate(text.splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append("{}:{}: JSON invalide ({})".format(path, num, exc.msg))
            continue
        if isinstance(obj, dict):
            lines.append(obj)
        else:
            errors.append("{}:{}: objet JSON attendu".format(path, num))
    return lines, errors


def read_config_int(config_path, key, default):
    """Lit un entier de premier niveau dans le YAML par une recherche simple."""
    text = _read_text(config_path)
    if not text:
        return default
    match = re.search(
        r"^[ \t]*" + re.escape(key) + r"[ \t]*:[ \t]*(\d+)[ \t]*$",
        text,
        re.MULTILINE,
    )
    return int(match.group(1)) if match else default


def read_config_str(config_path, key, default):
    """Lit un scalaire `paths.<key>` dans le YAML (défaut si absent)."""
    text = _read_text(config_path)
    if not text:
        return default
    match = re.search(
        r"^[ \t]*" + re.escape(key) + r"[ \t]*:[ \t]*[\"']?([^\"'\n#]+)",
        text,
        re.MULTILINE,
    )
    return match.group(1).strip() if match else default


def parse_ts(value):
    """Parse un horodatage ISO 8601 ; renvoie un datetime ou None."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _dt.datetime.fromisoformat(text)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Analyse
# --------------------------------------------------------------------------
def analyze(root, config_path=None) -> dict:
    root = Path(root)
    cfg = Path(config_path) if config_path else root / "sdlc.config.yaml"
    journal = read_config_str(cfg, "journal", "docs/journal")
    metrics = read_config_str(cfg, "metrics", "docs/metrics")
    runs_path = root / journal / "runs.jsonl"
    deploys_path = root / journal / "deploys.jsonl"
    history_path = root / metrics / "history.jsonl"

    runs_raw, err_runs = load_jsonl(runs_path)
    deploys_raw, err_dep = load_jsonl(deploys_path)
    history_raw, err_hist = load_jsonl(history_path)
    warnings = err_runs + err_dep + err_hist

    max_reviews = read_config_int(cfg, "max_review_iterations", DEFAULT_MAX_REVIEWS)
    timeout_min = read_config_int(cfg, "task_timeout_min", DEFAULT_TIMEOUT_MIN)
    timeout_s = timeout_min * 60

    runs = runs_raw or []
    deploys = deploys_raw or []
    history = history_raw or []

    tasks_by_agent = Counter()
    runs_by_status = Counter()
    for run in runs:
        tasks_by_agent[run.get("agent") or "inconnu"] += 1
        runs_by_status[run.get("status") or "inconnu"] += 1

    reviewed = 0
    first_ok = 0
    for run in runs:
        iteration = run.get("review_iteration")
        if iteration is None:
            continue
        reviewed += 1
        if iteration == 1 and run.get("status") == "done":
            first_ok += 1

    escalation_reasons = {"bloque": 0, "revues": 0, "delai": 0}
    escalated = set()
    for index, run in enumerate(runs):
        if run.get("status") == "blocked":
            escalation_reasons["bloque"] += 1
            escalated.add(index)
        iteration = run.get("review_iteration")
        if isinstance(iteration, (int, float)) and not isinstance(iteration, bool):
            if iteration >= max_reviews:
                escalation_reasons["revues"] += 1
                escalated.add(index)
        duration = run.get("duration_s")
        if isinstance(duration, (int, float)) and not isinstance(duration, bool):
            if duration > timeout_s:
                escalation_reasons["delai"] += 1
                escalated.add(index)

    deploys_by_result = Counter(d.get("result") or "inconnu" for d in deploys)
    deploys_by_env = Counter(d.get("env") or "inconnu" for d in deploys)
    rollbacks = deploys_by_result.get("rollback", 0)

    # Délai spec -> production : nécessite un lien explicite fonctionnalité <-> déploiement.
    spec_freeze = {}
    for source in list(runs) + list(history):
        feature = source.get("feature")
        stamp = parse_ts(source.get("spec_freeze_ts"))
        if feature and stamp is not None:
            if feature not in spec_freeze or stamp < spec_freeze[feature]:
                spec_freeze[feature] = stamp

    prod_deploys = {}
    for deploy in deploys:
        if str(deploy.get("env", "")).lower() not in PROD_ENVS:
            continue
        feature = deploy.get("feature")
        stamp = parse_ts(deploy.get("ts"))
        if feature and stamp is not None:
            if feature not in prod_deploys or stamp < prod_deploys[feature]:
                prod_deploys[feature] = stamp

    lead_times = {}
    for feature, spec_ts in spec_freeze.items():
        prod_ts = prod_deploys.get(feature)
        if prod_ts is None:
            continue
        try:
            delta = prod_ts - spec_ts
        except TypeError:
            continue
        days = delta.total_seconds() / 86400.0
        if days < 0:
            continue
        lead_times[feature] = {
            "days": round(days, 1),
            "spec_freeze_ts": spec_ts.isoformat(),
            "prod_ts": prod_ts.isoformat(),
        }

    average_days = None
    if lead_times:
        average_days = round(sum(v["days"] for v in lead_times.values()) / len(lead_times), 1)

    generated_at = _dt.datetime.now().astimezone().replace(microsecond=0).isoformat()

    return {
        "generated_at": generated_at,
        "root": str(root),
        "sources": {
            "runs": runs_raw is not None,
            "deploys": deploys_raw is not None,
            "history": history_raw is not None,
            "runs_total": len(runs),
            "deploys_total": len(deploys),
            "history_total": len(history),
        },
        "tasks_by_agent": dict(tasks_by_agent),
        "runs_by_status": dict(runs_by_status),
        "runs_total": len(runs),
        "first_review": {
            "reviewed": reviewed,
            "validated": first_ok,
            "ratio": (first_ok / reviewed) if reviewed else None,
        },
        "escalations": {
            "total": len(escalated),
            "by_reason": dict(escalation_reasons),
        },
        "rollbacks": rollbacks,
        "deploys_by_result": dict(deploys_by_result),
        "deploys_by_env": dict(deploys_by_env),
        "lead_times": lead_times,
        "average_lead_days": average_days,
        "thresholds": {
            "max_review_iterations": max_reviews,
            "task_timeout_min": timeout_min,
        },
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# Rendu Markdown
# --------------------------------------------------------------------------
def _fmt_pct(ratio) -> str:
    if ratio is None:
        return NON_MESURE
    value = ratio * 100.0
    text = "{:.1f}".format(value).rstrip("0").rstrip(".")
    return text + " %"


def _fmt_days(value) -> str:
    if value is None:
        return NON_MESURE
    return "{} jour(s)".format(value)


def _kv_table(counter, empty_label=NON_MESURE) -> str:
    if not counter:
        return empty_label
    rows = ["| Clé | Valeur |", "|---|---|"]
    for key in sorted(counter):
        rows.append("| {} | {} |".format(key, counter[key]))
    return "\n".join(rows)


def render(result) -> str:
    lines = []
    lines.append("# Indicateurs projet")
    lines.append("")
    lines.append(
        "> Fichier généré — ne pas modifier. Régénérer avec "
        "`.agents/skills/metrics/scripts/metrics.py`."
    )
    lines.append("")
    sources = result["sources"]
    lines.append("- Date de génération : {}".format(result["generated_at"]))
    lines.append("- Racine : {}".format(result["root"]))
    lines.append(
        "- Sources : runs.jsonl ({} ligne(s)), deploys.jsonl ({} ligne(s)), "
        "history.jsonl ({} ligne(s))".format(
            sources["runs_total"], sources["deploys_total"], sources["history_total"]
        )
    )
    lines.append("")

    # Tâches par agent
    lines.append("## Tâches par agent")
    lines.append("")
    if not sources["runs"] or result["runs_total"] == 0:
        lines.append(NON_MESURE + " (aucun run enregistré).")
    else:
        rows = ["| Agent | Tâches |", "|---|---|"]
        for agent in sorted(result["tasks_by_agent"]):
            rows.append("| {} | {} |".format(agent, result["tasks_by_agent"][agent]))
        rows.append("| **Total** | {} |".format(result["runs_total"]))
        lines.extend(rows)
    lines.append("")

    # Part validée dès la 1re revue
    lines.append("## Part validée dès la 1re revue")
    lines.append("")
    first = result["first_review"]
    if first["reviewed"] == 0:
        lines.append(NON_MESURE + " (aucune tâche avec itération de revue renseignée).")
    else:
        lines.append("- Tâches entrées en revue : {}".format(first["reviewed"]))
        lines.append("- Validées du premier coup : {}".format(first["validated"]))
        lines.append("- Part : {}".format(_fmt_pct(first["ratio"])))
    lines.append("")

    # Escalades
    lines.append("## Escalades")
    lines.append("")
    escalations = result["escalations"]
    if not sources["runs"]:
        lines.append(NON_MESURE + " (aucun run enregistré).")
    else:
        reasons = escalations["by_reason"]
        lines.append("- Total (runs concernés) : {}".format(escalations["total"]))
        lines.append(
            "- dont bloquées : {} | itérations de revue maximales atteintes : {} | "
            "durée dépassée : {} (motifs cumulables)".format(
                reasons["bloque"], reasons["revues"], reasons["delai"]
            )
        )
        lines.append(
            "- Seuils : review_iteration >= {} ou duration_s > {} s".format(
                result["thresholds"]["max_review_iterations"],
                result["thresholds"]["task_timeout_min"] * 60,
            )
        )
    lines.append("")

    # Délai spec -> production
    lines.append("## Délai spec → production")
    lines.append("")
    if not result["lead_times"]:
        lines.append(
            NON_MESURE + " (aucun lien fonctionnalité <-> déploiement de production "
            "exploitable ; renseigner `spec_freeze_ts` et `feature`)."
        )
    else:
        rows = ["| Fonctionnalité | Spec freeze | Production | Délai (jours) |", "|---|---|---|---|"]
        for feature in sorted(result["lead_times"]):
            item = result["lead_times"][feature]
            rows.append(
                "| {} | {} | {} | {} |".format(
                    feature, item["spec_freeze_ts"], item["prod_ts"], item["days"]
                )
            )
        lines.extend(rows)
        lines.append("")
        lines.append("- Délai moyen : {}".format(_fmt_days(result["average_lead_days"])))
    lines.append("")

    # Rollbacks
    lines.append("## Rollbacks")
    lines.append("")
    if not sources["deploys"]:
        lines.append(NON_MESURE + " (aucun déploiement enregistré).")
    else:
        lines.append(
            "- Nombre de rollbacks : {} (sur {} déploiement(s))".format(
                result["rollbacks"], sources["deploys_total"]
            )
        )
    lines.append("")

    # Contexte
    lines.append("## Contexte")
    lines.append("")
    lines.append("### Runs par statut")
    lines.append("")
    lines.append(_kv_table(result["runs_by_status"]))
    lines.append("")
    lines.append("### Déploiements par résultat")
    lines.append("")
    lines.append(_kv_table(result["deploys_by_result"]))
    lines.append("")
    lines.append("### Déploiements par environnement")
    lines.append("")
    lines.append(_kv_table(result["deploys_by_env"]))
    lines.append("")

    # Avertissements
    if result["warnings"]:
        lines.append("## Avertissements de lecture")
        lines.append("")
        for warning in result["warnings"]:
            lines.append("- {}".format(warning))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if any(item in ("-h", "--help") for item in args):
        print(__doc__)
        return 0

    parser = argparse.ArgumentParser(add_help=False, description="Indicateurs du projet SDLC.")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--out", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--stdout", action="store_true")
    try:
        options, extra = parser.parse_known_args(args)
    except SystemExit:
        return 2
    if extra:
        print("avertissement : arguments ignorés : {}".format(" ".join(extra)), file=sys.stderr)

    root = Path(options.root)
    cfg = options.config or (root / "sdlc.config.yaml")
    result = analyze(root, options.config or None)
    text = render(result)

    if options.stdout:
        sys.stdout.write(text)
        return 0

    out = (Path(options.out) if options.out
           else root / read_config_str(cfg, "metrics", "docs/metrics") / "indicateurs.md")
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    except OSError as exc:
        print("erreur : écriture impossible de {} : {}".format(out, exc), file=sys.stderr)
        return 2
    print(str(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
