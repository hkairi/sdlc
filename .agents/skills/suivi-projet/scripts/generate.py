#!/usr/bin/env python3
"""generate.py — écrit le tableau de bord « suivi-projet » depuis les JSON collectés.

Usage :
    python3 generate.py [RACINE_DU_PROJET] [--out FICHIER] [--open]

Injecte docs/suivi/project-data.json et docs/suivi/docs-data.json dans le gabarit
assets/template.html (marqueurs __PROJECT_DATA__ et __DOCS_DATA__), en échappant « </ »
en « <\\/ », puis écrit le fichier du tableau de bord (dashboard.file de
sdlc.config.yaml, défaut docs/suivi-projet.html). --open affiche le chemin final.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
TEMPLATE = os.path.join(SKILL_DIR, "assets", "template.html")


def load_yaml_dashboard_file(root):
    """Lit dashboard.file dans sdlc.config.yaml (PyYAML si présent)."""
    path = os.path.join(root, "sdlc.config.yaml")
    if not os.path.isfile(path):
        return None
    try:
        sys.path.insert(0, HERE)
        import collect as _c
        cfg = _c.load_yaml_file(path)
        return ((cfg.get("dashboard") or {}).get("file")) or None
    except Exception:
        return None


def resolve_suivi_dir(root, default="docs/suivi"):
    """Dossier de l'état et des JSON collectés : `paths.suivi` (§ 13.3), sinon défaut."""
    path = os.path.join(root, "sdlc.config.yaml")
    try:
        sys.path.insert(0, HERE)
        import collect as _c
        return _c.resolve_paths(_c.load_yaml_file(path))["suivi"]
    except Exception:
        return default


def embed(value):
    """Sérialise une valeur en JSON sûr pour un bloc <script>."""
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".", help="racine du projet (défaut : répertoire courant)")
    ap.add_argument("--out", help="fichier HTML de sortie (défaut : dashboard.file de la config)")
    ap.add_argument("--template", default=TEMPLATE, help="gabarit HTML")
    ap.add_argument("--open", action="store_true", dest="do_open", help="afficher (ouvrir) le chemin final")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)

    project_path = os.path.join(root, resolve_suivi_dir(root), "project-data.json")
    docs_path = os.path.join(root, resolve_suivi_dir(root), "docs-data.json")
    for p in (project_path, docs_path):
        if not os.path.isfile(p):
            sys.exit("Fichier manquant : %s — lancer collect.py d'abord." % p)
    project_data = json.load(open(project_path, encoding="utf-8"))
    docs_data = json.load(open(docs_path, encoding="utf-8"))

    template = open(args.template, encoding="utf-8").read()
    for marker in ("__PROJECT_DATA__", "__DOCS_DATA__"):
        if marker not in template:
            sys.exit("Marqueur %s absent du gabarit %s." % (marker, args.template))
    out = template.replace("__PROJECT_DATA__", embed(project_data)).replace("__DOCS_DATA__", embed(docs_data))
    leftover = [m for m in re.findall(r"__[A-Z_]+__", out)]
    if leftover:
        sys.exit("Marqueurs non remplacés : %s" % ", ".join(sorted(set(leftover))))

    rel_out = args.out or load_yaml_dashboard_file(root) or "docs/suivi-projet.html"
    out_path = rel_out if os.path.isabs(rel_out) else os.path.join(root, rel_out)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(out)
    print("Tableau de bord écrit : %s" % out_path)
    if args.do_open:
        try:
            import webbrowser
            webbrowser.open("file://" + out_path)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
