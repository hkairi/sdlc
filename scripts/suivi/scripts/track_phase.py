#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Copie vendorisée — source : skill suivi-taches (/Users/hkairi/.claude/skills/suivi-taches/scripts/track_phase.py)
# Copiée le 2026-10-19. Ne pas éditer ici : éditer la source, puis re-générer la copie
# avec `python3 scripts/suivi/sync_from_skill.py --write`.
# Contrôle de dérive : `python3 scripts/suivi/sync_from_skill.py --check`.
# ---------------------------------------------------------------------------
"""Met à jour l'état d'un item de checklist de phase dans un fichier de suivi.

Fonctionne pour les deux gabarits :
  - multi-chantiers (bloc <script id="feature-data">) : préciser le chantier (--feature) s'il y en a plusieurs ;
  - un chantier (bloc <script id="phase-data">).

Usage :
  track_phase.py --file docs/suivi-multi.html --feature bpay deploy.migrations doing "Migration en écriture."
  track_phase.py --file docs/suivi-<id>.html validation.tests done "36 runs, 0 échec."
  track_phase.py --file docs/suivi-multi.html bpay:validation.review done

- pose le statut (todo|doing|blocked|done), la date (aujourd'hui) et, si fournie, la note de l'item ;
- renseigne data-file-updated sur <body>.
Phases : cadrage, plan, impl (dérivée des tâches, non modifiable), validation, deploy, cloture.
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sourcedocs  # noqa: E402

MULTI_RE = re.compile(r'(<script type="application/json" id="feature-data">)(\{.*?)(</script>)', re.S)
MONO_RE = re.compile(r'(<script type="application/json" id="phase-data">)(\{.*?)(</script>)', re.S)


def split_ident(ident):
    if "." not in ident:
        sys.exit(f"Identifiant attendu : <phase>.<item> (reçu « {ident} »).")
    pid, iid = ident.split(".", 1)
    return pid, iid


def pick_feature(features, wanted):
    if wanted:
        feat = next((f for f in features if f.get("id") == wanted), None)
        if not feat:
            sys.exit(f"Chantier '{wanted}' introuvable.")
        return feat
    if len(features) == 1:
        return features[0]
    ids = ", ".join(f.get("id", "?") for f in features)
    sys.exit(f"Plusieurs chantiers : préciser --feature (ou 'feature:phase.item'). Candidats : {ids}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True)
    ap.add_argument("--feature", help="identifiant du chantier (fichier multi)")
    ap.add_argument("ident", help="<phase>.<item> ou <feature>:<phase>.<item>")
    ap.add_argument("status", choices=["todo", "doing", "blocked", "done"])
    ap.add_argument("note", nargs="?")
    args = ap.parse_args()
    today = datetime.date.today().isoformat()

    src = open(args.file, encoding="utf-8").read()
    ident = args.ident
    feature_id = args.feature
    if ":" in ident and "." in ident.split(":", 1)[1]:
        feature_id, ident = ident.split(":", 1)
    pid, iid = split_ident(ident)

    m = MULTI_RE.search(src)
    if m:
        data = json.loads(m.group(2).replace("\\u003c", "<"))
        feat = pick_feature(data.get("features", []), feature_id)
        phases = feat.get("phases", [])
        scope = f"{feat.get('id')}:{pid}.{iid}"
    else:
        m = MONO_RE.search(src)
        if not m:
            sys.exit(f"Bloc feature-data ou phase-data introuvable dans {args.file}")
        data = json.loads(m.group(2).replace("\\u003c", "<"))
        phases = data.get("phases", [])
        scope = f"{pid}.{iid}"

    phase = next((p for p in phases if p.get("id") == pid), None)
    if not phase:
        sys.exit(f"Phase '{pid}' introuvable.")
    if pid == "impl":
        sys.exit("La phase 'impl' est dérivée des tâches : mettre à jour les tâches (track.py / track_multi.py).")
    item = next((i for i in phase.get("items", []) if i.get("id") == iid), None)
    if not item:
        sys.exit(f"Item '{iid}' introuvable dans la phase '{pid}'.")

    item["status"] = args.status
    item["updated"] = today
    if args.note is not None:
        item["note"] = args.note

    payload = json.dumps(data, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    src = src[:m.start(2)] + payload + src[m.end(2):]
    src = re.sub(r'data-file-updated="[^"]*"', f'data-file-updated="{today}"', src, count=1)
    open(args.file, "w", encoding="utf-8").write(sourcedocs.refresh(src, args.file))
    print(f"{scope} -> {args.status}")


if __name__ == "__main__":
    main()
