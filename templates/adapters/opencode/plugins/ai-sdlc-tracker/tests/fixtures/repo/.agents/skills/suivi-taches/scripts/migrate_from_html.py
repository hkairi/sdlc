#!/usr/bin/env python3
"""migrate_from_html.py — importe un fichier de suivi HTML existant vers `state.json`.

Usage :
  migrate_from_html.py --file docs/suivi-<id>.html [--state docs/suivi/state.json] \
      [--id <feature>] [--name "<nom>"] [--change <change>] [--tasks openspec/changes/<id>/tasks.md]

Formats acceptés (détectés automatiquement) :
  1. **nouveau** : bloc `<script id="state-data">` (déjà au format commun) — recopié tel quel ;
  2. **multi** : bloc `<script id="feature-data">` (gabarit template-multi.html) ;
  3. **mono** : attributs `data-status` / `data-updated` / note `<em class="note">` des
     `<div class="task">`, lots `data-lot` / `data-name`, phases du bloc `<script id="phase-data">`.

Outre les tâches, l'import mono relit les **métadonnées du HTML** : `title`, `h1`, `eyebrow`,
`sous-titre` (dans `meta`), l'objectif, les décisions et les sources avec leurs liens (sur la
feature). `--tasks <tasks.md>` recharge, depuis le `tasks.md`, le **texte complet** et le **titre
court** de chaque tâche (le statut, la note, l'historique et les rôles sont conservés).

L'import ne perd rien de ce qui est présent dans le HTML (statut, date, note, historique, rôles,
lots, phases). Les champs absents restent `null`. Affiche un résumé. N'écrit jamais le HTML.
"""
import argparse
import html as html_mod
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import generate as gen       # noqa: E402  (parse_tasks / short_title : source unique)
import state_io as sio       # noqa: E402

STATE_RE = re.compile(r'<script type="application/json" id="state-data">(.*?)</script>', re.S)
FEATURE_RE = re.compile(r'<script type="application/json" id="feature-data">(.*?)</script>', re.S)
PHASE_RE = re.compile(r'<script type="application/json" id="phase-data">(.*?)</script>', re.S)
TASK_RE = re.compile(
    r'<div class="task"[^>]*?data-id="([^"]+)"[^>]*?data-lot="([^"]*)"[^>]*?data-status="([a-z]+)"[^>]*?data-updated="([^"]*)"',
    re.S)
LOT_RE = re.compile(r'<section class="lot"[^>]*?data-lot="([^"]+)"[^>]*?data-name="([^"]*)"', re.S)
H3_RE = re.compile(r'<h3>(.*?)</h3>', re.S)
NOTE_RE = re.compile(r'<em class="note">(.*?)</em>', re.S)
TITLE_RE = re.compile(r'<title>(.*?)</title>', re.S)
H1_RE = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S)
EYEBROW_RE = re.compile(r'<div class="eyebrow">(.*?)</div>', re.S)
HEADER_RE = re.compile(r'<header class="top">(.*?)</header>', re.S)
P_RE = re.compile(r'<p\b(?![^>]*class="extra")[^>]*>(.*?)</p>', re.S)
EXTRA_P_RE = re.compile(r'<p\b[^>]*class="extra"[^>]*>(.*?)</p>', re.S)
CARD_RE = re.compile(r'<section class="banner card[^"]*" data-card="([^"]+)"[^>]*>(.*?)</section>', re.S)
CARD_BODY_RE = re.compile(r'<div class="card-body">(.*?)</div>', re.S)
ANCHOR_RE = re.compile(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.S)


def _inline_html(chunk):
    """HTML inline court → markdown inline : `<code>` → backticks, `<b>` → `**…**`."""
    if not chunk:
        return ""
    chunk = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", chunk, flags=re.S)
    chunk = re.sub(r"<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>", r"**\1**", chunk, flags=re.S)
    chunk = re.sub(r"<[^>]+>", "", chunk)
    chunk = html_mod.unescape(chunk)
    return re.sub(r"\s+", " ", chunk).strip()


def _plain(chunk):
    return html_mod.unescape(re.sub(r"<[^>]+>", "", chunk or "")).strip()


def _card_list(body):
    return [_inline_html(m.group(1)) for m in re.finditer(r"<li[^>]*>(.*?)</li>", body or "", re.S)]


def parse_mono_meta(text):
    """Relit les métadonnées du gabarit mono : titre, fil d'Ariane, sous-titre, sources, cartes."""
    meta = {}
    m = TITLE_RE.search(text)
    if m:
        meta["title"] = html_mod.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
    m = EYEBROW_RE.search(text)
    if m:
        meta["eyebrow"] = _plain(m.group(1))
    m = H1_RE.search(text)
    if m:
        meta["h1"] = _plain(m.group(1))
    header = HEADER_RE.search(text)
    if header:
        m = P_RE.search(header.group(1))
        if m:
            meta["subtitle"] = _plain(m.group(1))
    # Sources : dans le paragraphe « Sources : … » de l'en-tête (liens label → href).
    sources = {}
    if header:
        for m in EXTRA_P_RE.finditer(header.group(1)):
            if "Sources" not in m.group(1):
                continue
            for a in ANCHOR_RE.finditer(m.group(1)):
                label = _plain(a.group(2))
                href = html_mod.unescape(a.group(1)).strip()
                if label and href:
                    sources[label] = href
    return meta, sources


def parse_mono_cards(text):
    """Cartes d'information du gabarit mono : objectif, décisions, sources."""
    out = {"objective": None, "decisions": [], "sources": {}}
    for m in CARD_RE.finditer(text):
        cid, block = m.group(1), m.group(2)
        body = CARD_BODY_RE.search(block)
        body = body.group(1) if body else block
        if cid == "objectif" and out["objective"] is None:
            out["objective"] = _inline_html(body)
        elif cid == "decisions":
            out["decisions"] = _card_list(body)
        elif cid == "sources":
            for a in ANCHOR_RE.finditer(body):
                label = _plain(a.group(2))
                href = html_mod.unescape(a.group(1)).strip()
                if label and href:
                    out["sources"][label] = href
    return out


def _json_block(regex, text):
    m = regex.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1).replace("\\u003c", "<").replace("<\\/", "</"))
    except ValueError:
        return None


def normalize_task(t):
    return {
        "id": t.get("id"),
        "lot": t.get("lot"),
        "title": t.get("title"),
        "text": t.get("text"),
        "status": t.get("status") or "todo",
        "updated": t.get("updated") or "",
        "note": t.get("note") or "",
        "history": t.get("history") or [],
        "executor": t.get("executor"),
        "reviewer": t.get("reviewer"),
        "review_iteration": t.get("review_iteration"),
        "escalated": bool(t.get("escalated")),
        "ready_to_commit": bool(t.get("ready_to_commit")),
        "commit_message": t.get("commit_message"),
        "files": t.get("files") or [],
        "acceptance": t.get("acceptance"),
        "tests": t.get("tests"),
    }


def normalize_feature(f):
    tasks = [normalize_task(t) for t in (f.get("tasks") or []) if isinstance(t, dict)]
    return {
        "id": f.get("id"),
        "name": f.get("name") or f.get("id"),
        "color": f.get("color"),
        "change": f.get("change"),
        "objective": f.get("objective"),
        "decisions": f.get("decisions") or [],
        "tasks_file": f.get("tasks_file"),
        "sources": f.get("sources") or {},
        "phases": f.get("phases") or [],
        "lots": f.get("lots") or [],
        "tasks": tasks,
        "recette": f.get("recette"),
        "version": f.get("version"),
        "delivered": f.get("delivered"),
        "blocked": sum(1 for t in tasks if t["status"] == "blocked"),
    }


def parse_state_block(text):
    data = _json_block(STATE_RE, text)
    if not isinstance(data, dict):
        return None
    data.setdefault("schema", 1)
    data["features"] = [normalize_feature(f) for f in (data.get("features") or []) if isinstance(f, dict)]
    return data


def parse_feature_block(text):
    data = _json_block(FEATURE_RE, text)
    if not isinstance(data, dict):
        return None
    state = sio.default_state()
    state["meta"] = {"title": None, "h1": None, "eyebrow": None}
    state["features"] = [normalize_feature(f) for f in (data.get("features") or []) if isinstance(f, dict)]
    return state


def parse_mono(text, path, fid, name, change):
    phases = None
    data = _json_block(PHASE_RE, text)
    if isinstance(data, dict):
        phases = data.get("phases")
    lots = [{"id": m.group(1), "name": html_mod.unescape(m.group(2))} for m in LOT_RE.finditer(text)]
    tasks = []
    for m in TASK_RE.finditer(text):
        tid, lot, status, updated = m.group(1), m.group(2), m.group(3), m.group(4)
        tail = text[m.end():m.end() + 20000]
        note = NOTE_RE.search(tail)
        h3 = H3_RE.search(tail)
        title = html_mod.unescape(re.sub(r"<[^>]+>", "", h3.group(1)).strip()) if h3 else tid
        tasks.append(normalize_task({
            "id": tid, "lot": lot, "status": status, "updated": updated,
            "note": note.group(1) if note else "", "title": title, "text": title,
        }))
    if not tasks:
        return None
    meta, header_sources = parse_mono_meta(text)
    cards = parse_mono_cards(text)
    sources = dict(header_sources)
    sources.update(cards["sources"])
    # nom : argument > <h1> > identifiant
    if not name:
        if meta.get("h1"):
            name = re.sub(r"\s*—\s*fichier de suivi\s*$", "", meta["h1"]).strip()
        else:
            h1 = H1_RE.search(text)
            if h1:
                name = re.sub(r"\s*—\s*fichier de suivi\s*$", "", _plain(h1.group(1))).strip()
    state = sio.default_state()
    state["meta"] = {
        "title": meta.get("title"),
        "h1": meta.get("h1"),
        "eyebrow": meta.get("eyebrow"),
        "subtitle": meta.get("subtitle"),
    }
    state["features"] = [normalize_feature({
        "id": fid, "name": name or fid, "change": change, "phases": phases or [],
        "lots": lots, "tasks": tasks, "objective": cards["objective"],
        "decisions": cards["decisions"], "sources": sources,
    })]
    return state


def reload_task_texts(state, tasks_path):
    """Depuis un tasks.md, met à jour `text` et `title` des tâches (statut, note, rôles intacts).

    Enregistre aussi `tasks_file` sur les features qui partagent au moins un identifiant de
    tâche avec le tasks.md (rattachement des régénérations suivantes).
    """
    ids = {t["id"] for lot in gen.parse_tasks(tasks_path) for t in lot["tasks"]}
    updated = 0
    for feature in state.get("features") or []:
        updated += gen.reload_task_texts(feature, tasks_path)
        feature_ids = {t.get("id") for t in (feature.get("tasks") or []) if isinstance(t, dict)}
        if ids & feature_ids:
            feature["tasks_file"] = tasks_path
    return updated


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True, help="fichier HTML de suivi à importer")
    ap.add_argument("--state", default=sio.DEFAULT_STATE_PATH, help="state.json de sortie")
    ap.add_argument("--id", dest="fid", help="identifiant de la feature (mono)")
    ap.add_argument("--name", help="nom de la feature (mono)")
    ap.add_argument("--change", help="change OpenSpec (mono)")
    ap.add_argument("--tasks", help="tasks.md : recharge le texte complet et le titre court des tâches")
    args = ap.parse_args(argv)

    with open(args.file, encoding="utf-8") as fh:
        text = fh.read()

    source = None
    state = parse_state_block(text)
    if state is not None:
        source = "nouveau (state-data)"
    if state is None:
        state = parse_feature_block(text)
        if state is not None:
            source = "multi (feature-data)"
    if state is None:
        stem = os.path.splitext(os.path.basename(args.file))[0]
        fid = args.fid or re.sub(r"^suivi-", "", stem) or "feature"
        state = parse_mono(text, args.file, fid, args.name, args.change)
        if state is not None:
            source = "mono (data-status/phase-data)"
    if state is None:
        sys.exit("Aucun suivi reconnu dans %s (ni state-data, ni feature-data, ni data-status)." % args.file)

    updated = 0
    if args.tasks:
        if not os.path.isfile(args.tasks):
            sys.exit("tasks.md introuvable : %s" % args.tasks)
        updated = reload_task_texts(state, args.tasks)

    state["file_updated"] = sio.today()
    sio.save_state(args.state, state)

    nfeat = len(state["features"])
    ntask = sum(len(f["tasks"]) for f in state["features"])
    nphase = sum(len(f.get("phases") or []) for f in state["features"])
    print("Import %s → %s" % (source, args.state))
    print("%d feature(s), %d tâche(s), %d phase(s)." % (nfeat, ntask, nphase))
    if args.tasks:
        print("%d tâche(s) rechargée(s) depuis %s." % (updated, args.tasks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
