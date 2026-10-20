#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Copie vendorisée — source : skill suivi-taches (/Users/hkairi/.claude/skills/suivi-taches/scripts/generate_multi.py)
# Copiée le 2026-10-19. Ne pas éditer ici : éditer la source, puis re-générer la copie
# avec `python3 scripts/suivi/sync_from_skill.py --write`.
# Contrôle de dérive : `python3 scripts/suivi/sync_from_skill.py --check`.
# ---------------------------------------------------------------------------
"""Génère (ou régénère) un fichier de suivi HTML MULTI-CHANTIERS à partir de plusieurs tasks.md.

Suivi de plusieurs features / changes OpenSpec dans une seule page, avec suivi détaillé
par tâche et rétention de l'état de sélection (chantiers cochés, filtres, groupe, vue,
tâche ouverte) dans l'URL + le navigateur.

Usage :
  generate_multi.py --out docs/suivi-multi.html --manifest docs/suivi-multi.json
  generate_multi.py --out docs/suivi-multi.html \
      --tasks openspec/changes/archive-abandoned-purchases/tasks.md \
      --tasks openspec/changes/add-bpay-payment-provider/tasks.md

Manifeste JSON (toutes les clés sont optionnelles sauf features) :
  {
    "title": "...", "h1": "...", "eyebrow": "...", "subtitle": "<html>",
    "storage_key": "...", "lang": "fr", "footer": "<html>",
    "sources": {"proposal": "../openspec/.../proposal.md"},
    "features": [
      "openspec/changes/<id>/tasks.md",
      {"id":"bpay","tasks":"...","name":"Intégration B-PAY","change":"add-bpay-payment-provider",
       "color":"#1379b0","objective":"<markdown inline>","updated":"2026-10-10",
       "sources": {"proposal":"..."},
       "details": {"1.1": {"prio":"Haute","files":["..."],"acceptance":"...","tests":"...",
                           "note":"...","deps":"—","history":[{"date":"...","status":"done","note":"..."}]}}}
    ]
  }

Format tasks.md : `## 1. Titre du lot` puis `- [ ] 1.1 Texte` (comme generate.py).
Régénérer est sans perte : statut, date, note, historique, fichiers, critères et tests de
chaque tâche déjà présents dans --out sont conservés ; une case [x] force « done ».
"""
import argparse
import datetime
import html
import json
import os
import re
import sys
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import phases as ph
SKILL_DIR = os.path.dirname(HERE)
TEMPLATE = os.path.join(SKILL_DIR, "assets", "template-multi.html")
PALETTE = ["#0f4c81", "#1379b0", "#2b6cb0", "#7d3c98", "#1f9d55", "#b7791f", "#0f766e", "#c0392b", "#4a5568", "#6b46c1", "#2f855a", "#b45309"]

# Réutilise le parseur de tasks.md de generate.py (sans exécuter son main).
_spec = importlib.util.spec_from_file_location("suivi_generate", os.path.join(HERE, "generate.py"))
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def slug(text):
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")


def prettify(fid):
    return fid.replace("-", " ").replace("_", " ").strip().capitalize()


def load_manifest(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def feature_spec(entry, index, base_dir):
    """Normalise une entrée de manifeste (chaîne ou objet) en dictionnaire."""
    if isinstance(entry, str):
        entry = {"tasks": entry}
    tasks_path = entry["tasks"]
    if not os.path.isabs(tasks_path):
        # Résolution tolérante : d'abord relatif au répertoire courant (racine du dépôt),
        # sinon relatif au dossier du manifeste.
        if os.path.exists(tasks_path):
            pass
        elif base_dir:
            tasks_path = os.path.normpath(os.path.join(base_dir, tasks_path))
    change = entry.get("change") or os.path.basename(os.path.dirname(tasks_path))
    fid = entry.get("id") or slug(change)
    return {
        "id": fid,
        "change": change,
        "name": entry.get("name") or prettify(fid),
        "color": entry.get("color") or PALETTE[index % len(PALETTE)],
        "updated": entry.get("updated", ""),
        "objective": entry.get("objective", ""),
        "tasks_path": tasks_path,
        "tasks_rel": entry["tasks"],
        "phases": entry.get("phases"),
        "sources": entry.get("sources", {}),
        "details": entry.get("details", {}),
    }


def parse_state(path):
    """État conservé depuis un fichier --out existant : tâches et features (phases)."""
    if not os.path.exists(path):
        return {}, None, {}, {}
    src = open(path, encoding="utf-8").read()
    m = re.search(r'<script type="application/json" id="feature-data">(\{.*?)</script>', src, re.S)
    state, prev_features = {}, {}
    if m:
        try:
            data = json.loads(m.group(1).replace("\\u003c", "<"))
            for feat in data.get("features", []):
                prev_features[feat.get("id")] = feat
                for t in feat.get("tasks", []):
                    state[(feat.get("id"), t.get("id"))] = t
        except (ValueError, AttributeError):
            pass
    fu = re.search(r'data-file-updated="([^"]*)"', src)
    return state, (fu.group(1) if fu else None), prev_features, src


def _html_list(items):
    if not items:
        return ""
    if len(items) == 1:
        return gen.md_inline(items[0])
    return "<ul>" + "".join(f"<li>{gen.md_inline(i)}</li>" for i in items) + "</ul>"


def parsed_details(task):
    """Détails lus sous la tâche dans tasks.md (Technique, Fichiers, Acceptation, Tests)."""
    d = task.get("details") or gen.empty_details()
    return {
        "tech": _html_list(d["tech"]),
        "files": list(d["files"]),
        "acceptance": _html_list(d["acceptance"]),
        "tests": _html_list(d["tests"]),
    }


def build_feature(spec, state, prev_feature):
    lots = gen.parse_tasks(spec["tasks_path"])
    if not lots:
        sys.exit(f"Aucune tâche trouvée dans {spec['tasks_path']} (attendu : '## N. Titre' puis '- [ ] N.M texte').")
    details = spec["details"] or {}
    out_lots, out_tasks = [], []
    for i, lot in enumerate(lots):
        lot_id = f"L{lot['num']}"
        out_lots.append({"id": lot_id, "name": lot["name"]})
        for t in lot["tasks"]:
            prev = state.get((spec["id"], t["id"]), {})
            det = details.get(t["id"], {})
            parsed = parsed_details(t)
            status = "done" if t["checked"] else (prev.get("status") or det.get("status") or "todo")
            out_tasks.append({
                "id": t["id"],
                "lot": lot_id,
                "title": t["title"],
                "status": status,
                "updated": prev.get("updated") or det.get("updated") or "",
                "prio": prev.get("prio") or det.get("prio") or "",
                "deps": prev.get("deps") or det.get("deps") or (t["dep"] or "—"),
                "note": prev.get("note") or det.get("note") or "",
                "objective": gen.md_inline(t["text"]),
                # tasks.md (sous-puces de détail) fait foi, puis le manifeste, puis l'ancien fichier.
                "tech": parsed["tech"] or det.get("tech") or prev.get("tech") or "",
                "files": parsed["files"] or det.get("files") or prev.get("files") or [],
                "acceptance": parsed["acceptance"] or det.get("acceptance") or prev.get("acceptance") or "",
                "tests": parsed["tests"] or det.get("tests") or prev.get("tests") or "",
                "history": prev.get("history") or det.get("history") or [],
            })
    updated = spec["updated"] or max((t["updated"] for t in out_tasks if t["updated"]), default="")
    return {
        "id": spec["id"], "name": spec["name"], "change": spec["change"],
        "color": spec["color"], "updated": updated, "objective": spec["objective"],
        "tasks_file": spec["tasks_rel"], "lots": out_lots, "tasks": out_tasks,
        "phases": ph.build_phases(spec.get("phases"), (prev_feature or {}).get("phases")),
    }


def sources_html(sources):
    if not sources:
        return ""
    return " · ".join(
        f'<a href="{html.escape(v)}">{html.escape(k)}</a>' for k, v in sources.items()
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", help="manifeste JSON des chantiers")
    ap.add_argument("--tasks", action="append", default=[], help="tasks.md d'un chantier (répétable, mode rapide)")
    ap.add_argument("--title")
    ap.add_argument("--h1")
    ap.add_argument("--eyebrow")
    ap.add_argument("--subtitle")
    ap.add_argument("--storage-key")
    ap.add_argument("--lang", default=None)
    ap.add_argument("--strict-details", action="store_true",
                    help="échoue si une tâche n'a pas de détails techniques ou de critères d'acceptation")
    args = ap.parse_args()

    if not args.manifest and not args.tasks:
        sys.exit("Fournir --manifest ou au moins un --tasks.")

    manifest, base_dir = {}, None
    if args.manifest:
        manifest = load_manifest(args.manifest)
        base_dir = os.path.dirname(os.path.abspath(args.manifest))
    entries = list(manifest.get("features", []))
    entries += [{"tasks": p} for p in args.tasks]

    state, previous_updated, prev_features, _ = parse_state(args.out)
    features = []
    for i, e in enumerate(entries):
        spec = feature_spec(e, i, base_dir)
        features.append(build_feature(spec, state, prev_features.get(spec["id"])))

    incomplete = False
    for f in features:
        for key, label in (("tech", "détails techniques"), ("acceptance", "critères d'acceptation")):
            ids = [t["id"] for t in f["tasks"] if not t.get(key)]
            if ids:
                incomplete = True
                print(f"⚠ {f['id'] or f['name']} : {len(ids)} tâche(s) sans {label} : {', '.join(ids)}", file=sys.stderr)
    if args.strict_details and incomplete:
        sys.exit("--strict-details : compléter les tasks.md (sous-puces « Technique : » et « Acceptation : ») ou le manifeste.")

    total = sum(len(f["tasks"]) for f in features)
    lots_total = sum(len(f["lots"]) for f in features)
    today = datetime.date.today().isoformat()

    title = args.title or manifest.get("title") or "Suivi multi-chantiers"
    h1 = args.h1 or manifest.get("h1") or f"{title} — fichier de suivi"
    eyebrow = args.eyebrow or manifest.get("eyebrow") or "Suivi multi-chantiers"
    lang = args.lang or manifest.get("lang") or "fr"
    file_updated = previous_updated or manifest.get("file_updated") or today
    storage_key = args.storage_key or manifest.get("storage_key") or slug(os.path.splitext(os.path.basename(args.out))[0]) + "-v1"

    if args.subtitle:
        subtitle = args.subtitle
    elif manifest.get("subtitle"):
        subtitle = manifest["subtitle"]
    else:
        subtitle = (f'{len(features)} chantiers · {total} tâches · {lots_total} lots. '
                    "Cochez un ou plusieurs chantiers dans le rail de gauche ; "
                    "l'espace de travail les affiche ensemble, avec le détail par tâche.")

    sources = sources_html(manifest.get("sources", {}))
    footer = manifest.get("footer") or (
        f'Fichier de suivi multi-chantiers · état de référence <b>dans ce fichier</b> '
        f'(bloc <code>feature-data</code>) · brouillon local et sélection mémorisés '
        f'(clé <code>{html.escape(storage_key)}</code>)'
        + (f" · sources : {sources}" if sources else "")
    )

    features_json = json.dumps({"features": features}, ensure_ascii=False, indent=2).replace("<", "\\u003c")

    values = {
        "LANG": html.escape(lang), "TITLE": html.escape(title), "H1": html.escape(h1),
        "EYEBROW": html.escape(eyebrow), "SUBTITLE_HTML": subtitle,
        "FILE_UPDATED": html.escape(file_updated), "STORAGE_KEY": storage_key,
        "FEATURES_JSON": features_json, "FOOTER_HTML": footer,
    }
    out = open(TEMPLATE, encoding="utf-8").read()
    for key, val in values.items():
        out = out.replace("{{" + key + "}}", val)
    leftover = re.findall(r"\{\{[A-Z0-9_]+\}\}", out)
    if leftover:
        sys.exit(f"Marqueurs non remplacés : {leftover}")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(out)

    kept = sum(1 for f in features for t in f["tasks"] if (f["id"], t["id"]) in state)
    print(f"{args.out} : {len(features)} chantiers, {total} tâches, {lots_total} lots ({kept} états conservés)")


if __name__ == "__main__":
    main()
