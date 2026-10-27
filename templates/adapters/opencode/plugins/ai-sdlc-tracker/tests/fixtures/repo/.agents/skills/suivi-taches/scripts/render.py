#!/usr/bin/env python3
"""render.py — rend `state.json` en fichier de suivi HTML.

Usage :
  render.py [--state docs/suivi/state.json] [--out docs/suivi-<id>.html] \
      [--template assets/template.html] [--root .]

- Gabarit choisi automatiquement : **mono** (`assets/template.html`) si une seule feature,
  **multi** (`assets/template-multi.html`) sinon ; `--template` force un gabarit.
- Le HTML porte la mention « fichier généré par la skill suivi-taches, ne pas modifier » et
  embarque l'état complet en **lecture seule** (bloc `state-data`), plus le contenu des `.md`
  liés (bloc `docs-data`) pour le lecteur Markdown.
- `markdown-it` est embarqué depuis `assets/vendor/markdown-it.min.js` (copie locale, aucune
  dépendance à une autre skill).
"""
import argparse
import glob
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import state_io as sio  # noqa: E402

SKILL_DIR = os.path.dirname(HERE)
ASSETS = os.path.join(SKILL_DIR, "assets")
MONO_TEMPLATE = os.path.join(ASSETS, "template.html")
MULTI_TEMPLATE = os.path.join(ASSETS, "template-multi.html")
VENDOR = os.path.join(ASSETS, "vendor", "markdown-it.min.js")
READER_JS = os.path.join(ASSETS, "reader.js")


def embed(value):
    """Sérialise une valeur en JSON sûr pour un bloc `<script>` (« </ » échappé)."""
    return json.dumps(value, ensure_ascii=False, indent=2).replace("</", "<\\/")


def slug(text):
    return re.sub(r"[^a-z0-9-]+", "-", (text or "").lower()).strip("-")


def read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def doc_title(content, path):
    m = re.search(r"^#\s+(.+?)\s*$", content or "", re.M)
    if m:
        return m.group(1).strip()
    return os.path.basename(path)


def collect_docs(state, root):
    """Lit les `.md` liés (sources des features + deltas de spec OpenSpec) pour le lecteur."""
    paths = []
    seen = set()

    def add(rel):
        if not rel or rel in seen:
            return
        seen.add(rel)
        paths.append(rel)

    for feature in state.get("features") or []:
        for rel in (feature.get("sources") or {}).values():
            add(rel)
        change = feature.get("change") or feature.get("id")
        if change:
            pattern = os.path.join(root, "openspec", "changes", change, "specs", "**", "*.md")
            for path in sorted(glob.glob(pattern, recursive=True)):
                add(os.path.relpath(path, root).replace(os.sep, "/"))

    files = {}
    for rel in paths:
        content = read_text(os.path.join(root, rel))
        if content is None:
            continue
        files[rel] = {"title": doc_title(content, rel), "content": content}
    return {"files": files, "embedded_at": sio.today(),
            "warnings": [p for p in paths if p not in files]}


def choose_template(state, template):
    if template:
        return template
    return MONO_TEMPLATE if len(state.get("features") or []) <= 1 else MULTI_TEMPLATE


def compute_meta(state, out):
    features = state.get("features") or []
    meta = state.get("meta") or {}
    total = sum(len(f.get("tasks") or []) for f in features)
    lots = sum(len(f.get("lots") or []) for f in features)
    if len(features) <= 1:
        name = (features[0].get("name") if features else None) or "Suivi"
        title = meta.get("title") or "Suivi d'avancement — %s" % name
        h1 = meta.get("h1") or "%s — fichier de suivi" % name
        eyebrow = meta.get("eyebrow") or "Suivi d'avancement"
        subtitle = meta.get("subtitle") or ("%d tâches · %d lots" % (total, lots))
    else:
        title = meta.get("title") or "Suivi multi-chantiers"
        h1 = meta.get("h1") or "%s — fichier de suivi" % title
        eyebrow = meta.get("eyebrow") or "Suivi multi-chantiers"
        subtitle = meta.get("subtitle") or (
            "%d chantiers · %d tâches · %d lots" % (len(features), total, lots))
    storage_key = meta.get("storage_key") or (
        slug(os.path.splitext(os.path.basename(out))[0]) + "-v1")
    return {
        "title": title, "h1": h1, "eyebrow": eyebrow, "subtitle": subtitle,
        "storage_key": storage_key, "lang": meta.get("lang") or "fr",
        "name": name if len(features) <= 1 else None,
    }


def compute_shell(state, meta):
    """Projet, marque et change affichés dans la coquille (barre latérale)."""
    features = state.get("features") or []
    eyebrow = meta.get("eyebrow") or ""
    project = eyebrow.split("·")[0].strip() if eyebrow else ""
    if not project:
        project = (features[0].get("name") if features else None) or "Suivi"
    if len(features) == 1:
        change = features[0].get("change") or features[0].get("id") or project
    else:
        change = "%d chantiers" % len(features)
    mark = (project[0] if project else "S").upper()
    return {"project": project, "mark": mark, "change": change}


def compute_rapports(state, root, out_dir):
    """Rapports de clôture existants, par `change` : `{change: href relatif}`.

    Convention du plugin `ai-sdlc-tracker` : `sdlc_report` écrit
    `docs/rapport-<change>.html`. On ne référence que les rapports réellement
    présents (le rapport est généré à la demande).
    """
    rapports = {}
    for feature in state.get("features") or []:
        change = feature.get("change") or feature.get("id")
        if not change:
            continue
        report_abs = os.path.join(root, "docs", "rapport-%s.html" % change)
        if os.path.isfile(report_abs):
            rapports[str(change)] = os.path.relpath(report_abs, out_dir)
    return rapports


def render(state=None, out=None, state_path=None, template=None, root="."):
    """Produit le fichier HTML de suivi à partir d'un état (chargé si absent)."""
    if state is None:
        state = sio.load_state(state_path or sio.DEFAULT_STATE_PATH)
    if not out:
        raise SystemExit("render.py : --out est obligatoire.")
    tpl_path = choose_template(state, template)
    if not os.path.isfile(tpl_path):
        raise SystemExit("Gabarit introuvable : %s" % tpl_path)

    root = os.path.abspath(root)
    out_path = os.path.abspath(out)
    out_dir = os.path.dirname(out_path) or "."
    prefix = os.path.relpath(root, out_dir).replace(os.sep, "/")
    if prefix == ".":
        prefix = ""
    elif not prefix.endswith("/"):
        prefix += "/"

    meta = compute_meta(state, out)
    docs = collect_docs(state, root)
    shell = compute_shell(state, meta)
    rapports = compute_rapports(state, root, out_dir)

    rapport_nav = ""
    rapport_btn = ""
    rapport_section = ""
    mono_change = None
    if len(state.get("features") or []) == 1:
        mono_change = (state["features"][0].get("change") or state["features"][0].get("id"))
    if mono_change and mono_change in rapports:
        href = html.escape(rapports[mono_change])
        rapport_nav = ('<a href="#rapport" data-nav="rapport">'
                       '<svg class="icon"><use href="#i-doc"/></svg>Rapport de clôture</a>')
        rapport_btn = '<a class="btn" href="#rapport">Rapport de clôture</a>'
        rapport_section = (
            '<section class="report" id="rapport" aria-label="Rapport de clôture">'
            '<div class="report-head"><h2>Rapport de clôture</h2>'
            '<a class="btn small" href="%s" target="_blank" rel="noopener">Ouvrir dans un onglet ↗</a></div>'
            '<iframe class="report-frame" src="%s" title="Rapport de clôture" loading="lazy"></iframe>'
            '</section>' % (href, href))

    mention = ("Fichier généré par la skill suivi-taches, ne pas modifier — "
               "l'état de référence vit dans %s." % (state_path or sio.DEFAULT_STATE_PATH))
    footer = ("<b>%s</b> · brouillon local et préférences mémorisés (clé <code>%s</code>)."
              % (mention, html.escape(meta["storage_key"])))

    values = {
        "LANG": html.escape(meta["lang"]),
        "TITLE": html.escape(meta["title"]),
        "H1": html.escape(meta["h1"]),
        "EYEBROW": html.escape(meta["eyebrow"]),
        "SUBTITLE_HTML": html.escape(meta["subtitle"]),
        "PROJECT": html.escape(shell["project"]),
        "MARK": html.escape(shell["mark"]),
        "CHANGE": html.escape(shell["change"]),
        "RAPPORT_NAV": rapport_nav,
        "RAPPORT_BTN": rapport_btn,
        "RAPPORT_SECTION": rapport_section,
        "RAPPORTS_JSON": embed(rapports),
        "FILE_UPDATED": html.escape(state.get("file_updated") or ""),
        "STORAGE_KEY": html.escape(meta["storage_key"]),
        "STATE_JSON": embed(state),
        "DOCS_JSON": embed(docs),
        "MARKDOWN_IT": read_text(VENDOR) or "",
        "READER_JS": read_text(READER_JS) or "",
        "ROOT_PREFIX": html.escape(prefix),
        "FOOTER_HTML": footer,
    }
    tpl = read_text(tpl_path)
    if tpl is None:
        raise SystemExit("Gabarit illisible : %s" % tpl_path)
    out_html = tpl
    for key, val in values.items():
        out_html = out_html.replace("{{" + key + "}}", val)
    leftover = re.findall(r"\{\{[A-Z0-9_]+\}\}", out_html)
    if leftover:
        raise SystemExit("Marqueurs non remplacés : %s" % ", ".join(sorted(set(leftover))))
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(out_html)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default=sio.DEFAULT_STATE_PATH)
    ap.add_argument("--out", required=True)
    ap.add_argument("--template")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    path = render(state_path=args.state, out=args.out, template=args.template, root=args.root)
    print("Fichier de suivi écrit : %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
