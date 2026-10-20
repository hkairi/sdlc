#!/usr/bin/env python3
"""generate.py — lit un ou plusieurs tasks.md, fusionne l'état dans `state.json`, rend le HTML.

Usage :
  generate.py --out docs/suivi-<id>.html --tasks openspec/changes/<id>/tasks.md \
      [--title "…"] [--h1 "…"] [--eyebrow "…"] [--subtitle "…"] \
      [--source "proposal=openspec/changes/<id>/proposal.md" …] \
      [--objective "<markdown inline>"] [--id <feature>] [--storage-key <clé>] [--state docs/suivi/state.json]

  # plusieurs chantiers d'un coup :
  generate.py --out docs/suivi-multi.html \
      --tasks openspec/changes/<a>/tasks.md --tasks openspec/changes/<b>/tasks.md
  generate.py --out docs/suivi-multi.html --manifest docs/suivi-multi.json

Format tasks.md attendu :
  ## 1. Titre du lot          (ou "## 6bis. Titre")
  - [ ] 1.1 Texte de la tâche (markdown inline : `code`, **gras**)
  - [x] 1.2 Tâche déjà faite
  Une étiquette **[XXX]** en tête de texte devient un badge de dépendance.

La fusion est **sans perte** : statut, note, historique, rôles, fichiers, critères, tests et
phases déjà présents dans `state.json` sont conservés ; une case [x] force « done ». Les
features déjà présentes dans l'état mais non régénérées sont conservées telles quelles.
Le rendu HTML est produit par `render.py` (gabarit mono si une feature, multi sinon).
"""
import argparse
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import phases as ph          # noqa: E402
import state_io as sio       # noqa: E402

SKILL_DIR = os.path.dirname(HERE)
PALETTE = ["#5c6b7a", "#0f4c81", "#1379b0", "#2b6cb0", "#7d3c98", "#1f9d55",
           "#b7791f", "#0f766e", "#c0392b", "#4a5568", "#6b46c1", "#2f855a"]

LOT_RE = re.compile(r"^##\s+([0-9]+[a-z]*)\.\s+(.*\S)\s*$")
TASK_RE = re.compile(r"^\s*-\s+\[([ xX])\]\s+([0-9]+[a-z]*\.[0-9]+[a-z]*)\s+(.*\S)\s*$")
DEP_RE = re.compile(r"^\*\*\[([^\]]+)\]\*\*\s*")


def md_inline(text):
    """Markdown inline minimal → HTML sûr : `code`, **gras**."""
    out = html.escape(text or "", quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    return out


def short_title(text):
    plain = re.sub(r"\*\*|`", "", DEP_RE.sub("", text))
    head = plain.split(" : ", 1)[0].split(" — ", 1)[0]
    if " (" in head and head.find(" (") > 15:
        head = head[:head.find(" (")]
    if len(head) < 12 and len(plain) > len(head):
        head = plain if len(plain) <= 100 else plain[:90].rsplit(" ", 1)[0] + "…"
    if len(head) > 100:
        head = head[:90].rsplit(" ", 1)[0] + "…"
    return head


def parse_tasks(path):
    """Lit un tasks.md et renvoie [{num, name, tasks:[{id, checked, dep, text, title}]}]."""
    lots, current = [], None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = LOT_RE.match(line)
            if m:
                current = {"num": m.group(1),
                           "name": "%s · %s" % (m.group(1), m.group(2).replace("`", "")),
                           "tasks": []}
                lots.append(current)
                continue
            m = TASK_RE.match(line)
            if m and current is not None:
                text = m.group(3)
                dep = DEP_RE.match(text)
                current["tasks"].append({
                    "id": m.group(2),
                    "checked": m.group(1).lower() == "x",
                    "dep": dep.group(1) if dep else None,
                    "text": DEP_RE.sub("", text),
                    "title": short_title(text),
                })
    return [lot for lot in lots if lot["tasks"]]


def reload_task_texts(feature, tasks_path):
    """Recharge `text` et `title` des tâches depuis un tasks.md.

    Seuls le texte complet et le titre court sont remis à jour : le statut, la note,
    l'historique et les rôles déjà présents dans l'état sont conservés. Renvoie le nombre
    de tâches effectivement modifiées.
    """
    index = {task["id"]: task for lot in parse_tasks(tasks_path) for task in lot["tasks"]}
    updated = 0
    for task in feature.get("tasks") or []:
        fresh = index.get(task.get("id"))
        if not fresh:
            continue
        if task.get("text") != fresh["text"] or task.get("title") != fresh["title"]:
            task["text"] = fresh["text"]
            task["title"] = fresh["title"]
            updated += 1
    return updated


def slug(text):
    return re.sub(r"[^a-z0-9-]+", "-", (text or "").lower()).strip("-")


def prettify(fid):
    return (fid or "").replace("-", " ").replace("_", " ").strip().capitalize()


def match_existing_id(entry_tasks, state_features):
    """Retrouve l'id d'une feature existante dont `tasks_file` correspond au tasks.md fourni."""
    target = os.path.normpath(entry_tasks)
    for feature in state_features or []:
        if not isinstance(feature, dict):
            continue
        stored = feature.get("tasks_file")
        if not stored:
            continue
        if os.path.normpath(stored) == target:
            return feature.get("id")
    return None


def feature_spec(entry, index, base_dir, state_features=None, forced_id=None):
    """Normalise une entrée (chaîne ou objet de manifeste) en dictionnaire de spéc."""
    if isinstance(entry, str):
        entry = {"tasks": entry}
    tasks_path = entry["tasks"]
    if not os.path.isabs(tasks_path) and not os.path.exists(tasks_path) and base_dir:
        tasks_path = os.path.normpath(os.path.join(base_dir, tasks_path))
    change = entry.get("change") or os.path.basename(os.path.dirname(tasks_path))
    # Rattachement : id explicite (manifeste) > `--id` forcé > feature existante dont
    # `tasks_file` correspond > identifiant déduit du chemin.
    fid = (forced_id or entry.get("id")
           or match_existing_id(entry["tasks"], state_features)
           or slug(change))
    return {
        "id": fid,
        "change": change,
        "name": entry.get("name") or prettify(fid),
        "color": entry.get("color") or PALETTE[index % len(PALETTE)],
        "objective": entry.get("objective"),
        "tasks_path": tasks_path,
        "tasks_rel": entry["tasks"],
        "phases": entry.get("phases"),
        "sources": entry.get("sources") or {},
        "details": entry.get("details") or {},
    }


def build_feature(existing, spec):
    """Fusionne un tasks.md dans une feature existante (ou nouvelle), sans perte."""
    lots = parse_tasks(spec["tasks_path"])
    if not lots:
        sys.exit("Aucune tâche trouvée dans %s (attendu : '## N. Titre' puis '- [ ] N.M texte')."
                 % spec["tasks_path"])
    prev = existing or {}
    prev_tasks = {t.get("id"): t for t in (prev.get("tasks") or []) if isinstance(t, dict)}
    details = spec["details"]

    out_lots, out_tasks = [], []
    for lot in lots:
        lot_id = "L%s" % lot["num"]
        out_lots.append({"id": lot_id, "name": lot["name"]})
        for task in lot["tasks"]:
            old = prev_tasks.get(task["id"], {})
            det = details.get(task["id"], {})
            status = "done" if task["checked"] else (old.get("status") or det.get("status") or "todo")
            out_tasks.append({
                "id": task["id"],
                "lot": lot_id,
                "title": task["title"],
                "text": task["text"],
                "status": status,
                "updated": old.get("updated") or det.get("updated") or "",
                "note": old.get("note") or det.get("note") or "",
                "history": old.get("history") or det.get("history") or [],
                "executor": old.get("executor"),
                "reviewer": old.get("reviewer"),
                "review_iteration": old.get("review_iteration"),
                "escalated": bool(old.get("escalated")),
                "ready_to_commit": bool(old.get("ready_to_commit")),
                "commit_message": old.get("commit_message"),
                "files": old.get("files") or det.get("files") or [],
                "acceptance": old.get("acceptance") or det.get("acceptance") or None,
                "tests": old.get("tests") or det.get("tests") or None,
            })

    phases = ph.build_phases(spec.get("phases"), prev.get("phases"))
    ph.refresh_statuses(phases, out_tasks)
    return {
        "id": spec["id"],
        "name": spec["name"],
        "color": spec["color"],
        "change": spec["change"],
        "objective": spec.get("objective") or prev.get("objective") or None,
        "tasks_file": spec["tasks_rel"],
        "sources": spec.get("sources") or prev.get("sources") or {},
        "phases": phases,
        "lots": out_lots,
        "tasks": out_tasks,
        "recette": prev.get("recette"),
        "version": prev.get("version"),
        "delivered": prev.get("delivered"),
        "blocked": sum(1 for t in out_tasks if t["status"] == "blocked"),
    }


def merge_into_state(state, entries, base_dir, forced_id=None):
    """Fusionne les entrées dans l'état ; renvoie le nombre de features mises à jour."""
    by_id = {f.get("id"): f for f in state["features"] if isinstance(f, dict)}
    order = [f.get("id") for f in state["features"] if isinstance(f, dict)]
    touched = 0
    for index, entry in enumerate(entries):
        spec = feature_spec(entry, index, base_dir, state.get("features"), forced_id)
        merged = build_feature(by_id.get(spec["id"]), spec)
        by_id[spec["id"]] = merged
        if spec["id"] not in order:
            order.append(spec["id"])
        touched += 1
    state["features"] = [by_id[fid] for fid in order if fid in by_id]
    return touched


def load_manifest(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="fichier HTML de sortie")
    ap.add_argument("--tasks", action="append", default=[], help="tasks.md d'un chantier (répétable)")
    ap.add_argument("--manifest", help="manifeste JSON des chantiers (titre, sources, détails…)")
    ap.add_argument("--state", default=sio.DEFAULT_STATE_PATH, help="chemin de state.json")
    ap.add_argument("--title")
    ap.add_argument("--h1")
    ap.add_argument("--eyebrow")
    ap.add_argument("--subtitle")
    ap.add_argument("--source", action="append", default=[], help="libellé=chemin (répétable)")
    ap.add_argument("--objective")
    ap.add_argument("--id", dest="fid", help="force l'identifiant de la feature rattachée")
    ap.add_argument("--storage-key")
    ap.add_argument("--lang", default="fr")
    ap.add_argument("--template", help="gabarit HTML (sinon auto : mono/multi)")
    args = ap.parse_args(argv)

    if not args.manifest and not args.tasks:
        sys.exit("Fournir --manifest ou au moins un --tasks.")

    manifest, base_dir = {}, None
    if args.manifest:
        manifest = load_manifest(args.manifest)
        base_dir = os.path.dirname(os.path.abspath(args.manifest))
    entries = list(manifest.get("features", []))
    entries += [{"tasks": p} for p in args.tasks]
    if not entries:
        sys.exit("Aucune feature dans le manifeste ni via --tasks.")

    # Métadonnées : arguments de ligne de commande > manifeste > existant.
    single = len(entries) == 1
    if single:
        entry = entries[0]
        if isinstance(entry, str):
            entries[0] = {"tasks": entry}
            entry = entries[0]
        if args.objective:
            entry["objective"] = args.objective
        if args.source:
            entry.setdefault("sources", {})
            for item in args.source:
                if "=" in item:
                    label, path = item.split("=", 1)
                    entry["sources"][label] = path

    state = sio.load_state(args.state)
    merge_into_state(state, entries, base_dir, args.fid)

    meta = state.setdefault("meta", {})
    meta["title"] = args.title or manifest.get("title") or meta.get("title")
    meta["h1"] = args.h1 or manifest.get("h1") or meta.get("h1")
    meta["eyebrow"] = args.eyebrow or manifest.get("eyebrow") or meta.get("eyebrow")
    meta["subtitle"] = args.subtitle or manifest.get("subtitle") or meta.get("subtitle")
    meta["storage_key"] = args.storage_key or manifest.get("storage_key") or meta.get("storage_key")
    meta["lang"] = args.lang or manifest.get("lang") or meta.get("lang") or "fr"
    state["file_updated"] = sio.today()

    sio.save_state(args.state, state)

    import render as rnd
    rnd.render(state=state, out=args.out, state_path=args.state, template=args.template)
    total = sum(len(f.get("tasks") or []) for f in state["features"])
    print("%s : %d feature(s), %d tâche(s) — état %s" % (args.out, len(state["features"]), total, args.state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
