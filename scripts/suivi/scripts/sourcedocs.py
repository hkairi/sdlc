# ---------------------------------------------------------------------------
# Copie vendorisée — source : skill suivi-taches (/Users/hkairi/.claude/skills/suivi-taches/scripts/sourcedocs.py)
# Copiée le 2026-10-19. Ne pas éditer ici : éditer la source, puis re-générer la copie
# avec `python3 scripts/suivi/sync_from_skill.py --write`.
# Contrôle de dérive : `python3 scripts/suivi/sync_from_skill.py --check`.
# ---------------------------------------------------------------------------
"""Documents sources (.md) embarqués dans un fichier de suivi.

Un navigateur ne peut pas lire un fichier local voisin depuis une page ouverte en
file:// ; le contenu des sources Markdown est donc copié dans le fichier, dans le bloc
<script type="application/json" id="source-docs">, et rendu par la page dans un lecteur.
generate.py remplit le bloc ; track.py et track_phase.py le rafraîchissent à chaque
mise à jour, pour que tasks.md (cases cochées) reste fidèle.
"""
import datetime
import json
import os
import re

BLOCK_RE = re.compile(r'(<script type="application/json" id="source-docs">)(.*?)(</script>)', re.S)


def _snapshot(path):
    return datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")


def collect(sources, out_dir):
    """sources : liste de « libellé=url ». Ne garde que les .md lisibles (url relative au suivi)."""
    docs = {}
    for s in sources:
        if "=" not in s:
            continue
        label, href = s.split("=", 1)
        if not href.lower().split("#", 1)[0].endswith(".md") or re.match(r"^[a-z]+:", href, re.I):
            continue
        path = os.path.normpath(os.path.join(out_dir, href.split("#", 1)[0]))
        if os.path.isfile(path):
            docs[label] = {"href": href, "md": open(path, encoding="utf-8").read(), "snapshot": _snapshot(path)}
    return docs


def to_json(docs):
    return json.dumps(docs, ensure_ascii=False).replace("<", "\\u003c")


def refresh(html_src, html_path):
    """Relit chaque document embarqué ; renvoie le HTML mis à jour (inchangé sans bloc)."""
    m = BLOCK_RE.search(html_src)
    if not m:
        return html_src
    try:
        docs = json.loads(m.group(2) or "{}")
    except ValueError:
        return html_src
    out_dir = os.path.dirname(os.path.abspath(html_path))
    for doc in docs.values():
        path = os.path.normpath(os.path.join(out_dir, doc.get("href", "").split("#", 1)[0]))
        if os.path.isfile(path):
            doc["md"] = open(path, encoding="utf-8").read()
            doc["snapshot"] = _snapshot(path)
    return html_src[:m.start(2)] + to_json(docs) + html_src[m.end(2):]
