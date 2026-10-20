#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Copie vendorisée — source : skill suivi-taches (/Users/hkairi/.claude/skills/suivi-taches/scripts/generate.py)
# Copiée le 2026-10-19. Ne pas éditer ici : éditer la source, puis re-générer la copie
# avec `python3 scripts/suivi/sync_from_skill.py --write`.
# Contrôle de dérive : `python3 scripts/suivi/sync_from_skill.py --check`.
# ---------------------------------------------------------------------------
"""Génère (ou régénère) un fichier de suivi HTML à partir d'un tasks.md (format OpenSpec).

Usage :
  generate.py --tasks openspec/changes/<id>/tasks.md --out docs/suivi-<id>.html \
      --title "Suivi d'avancement — <titre>" --h1 "<titre> — fichier de suivi" \
      [--eyebrow "Projet · Domaine · Suivi d'avancement"] [--subtitle "<html>"] \
      [--source "proposal=../openspec/changes/<id>/proposal.md" ...] \
      [--objective "<markdown inline>"] [--decisions decisions.md] [--decisions-title "Décisions tranchées le AAAA-MM-JJ"] \
      [--storage-key <clé>] [--lang fr] [--strict-details] [--badge "Android seulement"]

Format tasks.md attendu :
  ## 1. Titre du lot          (ou "## 6bis. Titre")
  - [ ] 1.1 Texte de la tâche (markdown inline : `code`, **gras**)
    - Technique : comment faire (classes, endpoints, règles)      ← obligatoire
    - Fichiers : `chemin/a.rb`, `chemin/b.ts`
    - Acceptation : critère vérifiable                            ← obligatoire
    - Acceptation : un autre critère
    - Tests : ce qui prouve que c'est fait
  - [x] 1.2 Tâche déjà faite
  Une étiquette **[XXX]** en tête de texte devient un badge de dépendance.
  Sous-puces de détail (indentées sous la tâche, sans case à cocher) : `Technique`
  (ou « Détails techniques »), `Fichiers`, `Acceptation` (ou « Critères d'acceptation »),
  `Tests`, `Dépendances`. Une étiquette suivie de « : » sans texte prend les sous-puces
  plus indentées qui la suivent. Les tâches sans détails techniques ou sans critères
  d'acceptation sont signalées ; --strict-details fait alors échouer la génération.

Si --out existe déjà, l'état de référence (data-status, data-updated, note) de chaque
tâche est conservé ; une case [x] dans tasks.md force « done ».
"""
import argparse
import datetime
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import phases as ph
import sourcedocs

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(SKILL_DIR, "assets", "template.html")
PALETTE = ["#5c6b7a", "#0f4c81", "#1379b0", "#2b6cb0", "#7d3c98", "#1f9d55", "#b7791f", "#0f766e", "#c0392b", "#4a5568", "#6b46c1", "#2f855a"]
STATUS_LABELS = [("todo", "À faire"), ("doing", "En cours"), ("blocked", "Bloqué"), ("done", "Terminé")]

LOT_RE = re.compile(r"^##\s+([0-9]+[a-z]*)\.\s+(.*\S)\s*$")
TASK_RE = re.compile(r"^\s*-\s+\[([ xX])\]\s+([0-9]+[a-z]*\.[0-9]+[a-z]*)\s+(.*\S)\s*$")
DEP_RE = re.compile(r"^\*\*\[([^\]]+)\]\*\*\s*")
DETAIL_RE = re.compile(r"^(\s+)[-*]\s+(?!\[[ xX]\])(.*\S)\s*$")
LABEL_RE = re.compile(r"^\*{0,2}([^:*]+?)\*{0,2}\s*:\s*\*{0,2}\s*(.*)$")

# Étiquettes de détail reconnues sous une tâche → clé interne.
DETAIL_KEYS = {
    "technique": "tech", "details techniques": "tech", "detail technique": "tech", "details": "tech",
    "fichiers": "files", "fichier": "files",
    "acceptation": "acceptance", "criteres d'acceptation": "acceptance", "critere d'acceptation": "acceptance",
    "criteres": "acceptance", "critere": "acceptance",
    "tests": "tests", "test": "tests", "validation": "tests",
    "dependances": "deps", "dependance": "deps",
}
DETAIL_LABELS = {
    "tech": "Détails techniques", "files": "Fichiers", "acceptance": "Critères d'acceptation",
    "tests": "Tests / validation", "deps": "Dépendances",
}
REQUIRED_DETAILS = ("tech", "acceptance")


def _detail_key(label):
    norm = label.strip().lower().replace("’", "'")
    norm = norm.translate(str.maketrans("éèêàâîïôûùç", "eeeaaiiouuc"))
    return DETAIL_KEYS.get(norm)


def empty_details():
    return {key: [] for key in DETAIL_LABELS}


def md_inline(text):
    """Markdown inline minimal → HTML sûr : `code`, **gras**."""
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    return out


def short_title(text):
    plain = re.sub(r"\*\*|`", "", DEP_RE.sub("", text))
    head = plain.split(" : ", 1)[0].split(" — ", 1)[0]
    # Une parenthèse ouverte dans le titre court (détails, critères) est coupée
    # avant elle plutôt qu'au milieu.
    if " (" in head and head.find(" (") > 15:
        head = head[:head.find(" (")]
    # Titre trop bref (« Tests », « Docs ») : on garde la suite du texte.
    if len(head) < 12 and len(plain) > len(head):
        head = plain if len(plain) <= 100 else plain[:90].rsplit(" ", 1)[0] + "…"
    if len(head) > 100:
        head = head[:90].rsplit(" ", 1)[0] + "…"
    return head


def _add_detail(details, key, value):
    value = value.strip()
    if not value:
        return
    if key == "files":
        for part in re.split(r",\s*|\s+;\s+", value):
            part = part.strip().strip("`").strip()
            if part:
                details["files"].append(part)
    else:
        details[key].append(value)


def parse_tasks(path):
    lots, current = [], None
    task, last_key, label_indent = None, None, None
    for line in open(path, encoding="utf-8"):
        m = LOT_RE.match(line)
        if m:
            current = {"num": m.group(1), "name": f"{m.group(1)} · {m.group(2).replace('`', '')}", "tasks": []}
            lots.append(current)
            task = None
            continue
        m = TASK_RE.match(line)
        if m and current is not None:
            text = m.group(3)
            dep = DEP_RE.match(text)
            task = {
                "id": m.group(2),
                "checked": m.group(1).lower() == "x",
                "dep": dep.group(1) if dep else None,
                "text": DEP_RE.sub("", text),
                "title": short_title(text),
                "details": empty_details(),
            }
            current["tasks"].append(task)
            last_key, label_indent = None, None
            continue
        d = DETAIL_RE.match(line)
        if d and task is not None:
            indent, body = len(d.group(1)), d.group(2)
            lm = LABEL_RE.match(body)
            key = _detail_key(lm.group(1)) if lm else None
            if key:
                _add_detail(task["details"], key, lm.group(2))
                last_key, label_indent = key, indent
            elif last_key and label_indent is not None and indent > label_indent:
                _add_detail(task["details"], last_key, body)
            else:
                # Sous-puce sans étiquette : précision technique.
                _add_detail(task["details"], "tech", body)
                last_key, label_indent = None, None
            continue
        if line.strip() and not line.startswith((" ", "\t")):
            task = None
    return [lot for lot in lots if lot["tasks"]]


def missing_details(lots):
    """Tâches sans détails techniques ou sans critères d'acceptation : {clé: [ids]}."""
    out = {key: [] for key in REQUIRED_DETAILS}
    for lot in lots:
        for t in lot["tasks"]:
            for key in REQUIRED_DETAILS:
                if not t["details"][key]:
                    out[key].append(t["id"])
    return out


def details_html(details):
    """Bloc dépliable sous la tâche : détails techniques, fichiers, critères, tests."""
    if not any(details.values()):
        return ""
    counts = []
    if details["tech"]:
        counts.append("détails techniques")
    if details["acceptance"]:
        counts.append(f"{len(details['acceptance'])} critère{'s' if len(details['acceptance']) > 1 else ''} d'acceptation")
    summary = " · ".join(counts) or "détails"
    parts = []
    for key in ("tech", "files", "acceptance", "tests", "deps"):
        items = details[key]
        if not items:
            continue
        if key == "files":
            body = " ".join(f"<code>{html.escape(f)}</code>" for f in items)
            parts.append(f'<div class="kv det-files"><b>{DETAIL_LABELS[key]}</b> {body}</div>')
            continue
        lis = "".join(f"<li>{md_inline(i)}</li>" for i in items)
        parts.append(f'<div class="kv det-{key}"><b>{DETAIL_LABELS[key]}</b><ul>{lis}</ul></div>')
    return (f'\n          <details class="task-details"><summary>{html.escape(summary[0].upper() + summary[1:])}</summary>'
            + "".join(parts) + "</details>")


def read_existing_state(path):
    """Récupère l'état de référence d'un suivi existant : {id: (status, updated, note_html)}."""
    if not os.path.exists(path):
        return {}, None
    src = open(path, encoding="utf-8").read()
    state = {}
    for m in re.finditer(r'<div class="task" data-id="([^"]+)"[^>]*?data-status="([a-z]+)" data-updated="([^"]*)"', src):
        tid = m.group(1)
        start = m.end()
        note = re.search(r'<em class="note">(.*?)</em>', src[start:start + 20000], re.S)
        state[tid] = (m.group(2), m.group(3), note.group(1) if note else "")
    fu = re.search(r'data-file-updated="([^"]*)"', src)
    return state, fu.group(1) if fu else None


def read_existing_phases(path):
    """Récupère les phases d'un suivi existant (bloc <script id="phase-data">)."""
    if not os.path.exists(path):
        return None
    src = open(path, encoding="utf-8").read()
    m = re.search(r'<script type="application/json" id="phase-data">(\{.*?)</script>', src, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1).replace("\\u003c", "<")).get("phases")
    except (ValueError, AttributeError):
        return None


def task_html(task, lot_key, state):
    status, updated, note = state.get(task["id"], ("todo", "", ""))
    if task["checked"]:
        status = "done"
    options = "\n".join(
        f'            <option value="{v}"{" selected" if v == status else ""}>{label}</option>' for v, label in STATUS_LABELS
    )
    dep = f'\n          <span class="pill badge-dep">[{html.escape(task["dep"])}]</span>' if task["dep"] else ""
    return f"""      <div class="task" data-id="{task['id']}" data-lot="{lot_key}" data-prio="" data-status="{status}" data-updated="{updated}">
        <div class="side">
          <span class="id">{task['id']}</span>{dep}
          <select class="status-sel st-{status}" data-id="{task['id']}" aria-label="Statut de {task['id']}">
{options}
          </select>
        </div>
        <div class="main">
          <h3>{html.escape(task['title'])}</h3>
          <em class="note">{note}</em>
          <div class="obj">{md_inline(task['text'])}</div>{details_html(task.get('details') or empty_details())}
          <span class="draft-flag hidden">modifié localement (non reporté dans le fichier)</span>
        </div>
      </div>"""


def lots_html(lots, state):
    parts = []
    for i, lot in enumerate(lots):
        key = f"L{lot['num']}"
        color = PALETTE[i % len(PALETTE)]
        tasks = "\n".join(task_html(t, key, state) for t in lot["tasks"])
        name = html.escape(lot["name"])
        parts.append(f"""  <section class="lot" data-lot="{key}" data-name="{name}" data-color="{color}">
    <div class="head">
      <span class="dot" style="background:{color}"></span>
      <h2>{name}</h2>
      <span class="mini">0/{len(lot['tasks'])} · 0%</span>
    </div>
    <div class="lbar"><span style="width:0%;background:{color}"></span></div>
    <div class="tasks">
{tasks}
    </div>
  </section>""")
    return "\n".join(parts)


def panel(title, body_html):
    return f"""  <section class="panel">
    <h3>{html.escape(title)}</h3>
    {body_html}
  </section>"""


def decisions_items(args):
    if not args.decisions:
        return []
    return [re.sub(r"^\s*[-*]\s+", "", l).strip() for l in open(args.decisions, encoding="utf-8") if re.match(r"^\s*[-*]\s+", l)]


def context_html(args, subtitle, sources):
    """Onglet Contexte : objectif, périmètre (sous-titre), sources, décisions."""
    out = []
    if args.objective:
        out.append(panel("Objectif du chantier", f"<p style=\"margin:0\">{md_inline(args.objective)}</p>"))
    meta = f"<p style=\"margin:0 0 6px\">{subtitle}</p>" if subtitle else ""
    if sources:
        meta += f"<p style=\"margin:0\">Sources : {sources}</p>"
    if meta:
        out.append(panel("Périmètre et sources", meta))
    items = decisions_items(args)
    if items:
        body = "<ul>" + "".join(f"<li>{md_inline(i)}</li>" for i in items) + "</ul>"
        out.append(panel(args.decisions_title, body))
    return "\n".join(out) or panel("Contexte", "<p style=\"margin:0\">Aucun contexte renseigné.</p>")


def info_html(args, subtitle, sources):
    """Menu « Infos » de l'en-tête : l'essentiel du contexte, à un clic."""
    parts = []
    if args.objective:
        parts.append(f"<h6>Objectif</h6><p>{md_inline(args.objective)}</p>")
    if subtitle:
        parts.append(f"<h6>Périmètre</h6><p>{subtitle}</p>")
    if sources:
        parts.append(f"<h6>Sources</h6><p>{sources}</p>")
    n = len(decisions_items(args))
    if n:
        parts.append(f"<h6>Décisions</h6><p>{n} décision{'s' if n > 1 else ''} — <a href=\"#onglet=contexte\">voir l'onglet Contexte</a></p>")
    return "".join(parts) or "<p>Aucune information complémentaire.</p>"


def procedure_html(tasks_rel):
    body = f"""<p style="margin:0">Après chaque progression (tâche commencée, terminée ou bloquée), lancer <code>scripts/track.py</code> de la skill <code>suivi-taches</code> — ou éditer directement ce fichier :</p>
    <ol>
      <li>le <code>data-status</code> de la tâche (<code>todo</code> | <code>doing</code> | <code>blocked</code> | <code>done</code>) ;</li>
      <li>son <code>data-updated</code> (date de dernière modification) ;</li>
      <li>la note <code>&lt;em class="note"&gt;</code> sous le libellé (ce qui a été fait, écarts, vérifications) ;</li>
      <li>la date de dernière mise à jour du fichier (<code>data-file-updated</code> sur <code>&lt;body&gt;</code>) ;</li>
      <li>cocher la tâche dans <code>{html.escape(tasks_rel)}</code>.</li>
    </ol>
    <p style="margin:8px 0 0">Les détails techniques et critères d'acceptation se modifient dans <code>{html.escape(tasks_rel)}</code>, puis on régénère le suivi (sans perte). Les phases se mettent à jour avec <code>scripts/track_phase.py</code>. Le navigateur ne conserve qu'un <b>brouillon local</b> (localStorage), jamais la vérité : seul ce fichier fait foi.</p>"""
    return panel("Procédure de mise à jour", body)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--h1", required=True)
    ap.add_argument("--eyebrow", default="Suivi d'avancement")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--source", action="append", default=[], help="libellé=url (répétable)")
    ap.add_argument("--objective", default="")
    ap.add_argument("--decisions", help="fichier markdown de puces")
    ap.add_argument("--decisions-title", default="Décisions tranchées")
    ap.add_argument("--badge", default="", help="pastille courte à côté du titre (ex. « Android seulement »)")
    ap.add_argument("--storage-key")
    ap.add_argument("--lang", default="fr")
    ap.add_argument("--phases", help="fichier JSON des phases (liste ou {\"phases\": [...]}) — sinon phases par défaut")
    ap.add_argument("--strict-details", action="store_true",
                    help="échoue si une tâche n'a pas de détails techniques ou de critères d'acceptation")
    args = ap.parse_args()

    lots = parse_tasks(args.tasks)
    if not lots:
        sys.exit(f"Aucune tâche trouvée dans {args.tasks} (attendu : '## N. Titre' puis '- [ ] N.M texte').")
    missing = missing_details(lots)
    for key, ids in missing.items():
        if ids:
            print(f"⚠ {len(ids)} tâche(s) sans {DETAIL_LABELS[key].lower()} : {', '.join(ids)}", file=sys.stderr)
    if args.strict_details and any(missing.values()):
        sys.exit("--strict-details : compléter tasks.md (sous-puces « Technique : » et « Acceptation : ») avant de générer.")
    state, previous_updated = read_existing_state(args.out)
    total = sum(len(l["tasks"]) for l in lots)
    today = datetime.date.today().isoformat()
    out_dir = os.path.dirname(os.path.abspath(args.out))
    tasks_rel = os.path.relpath(os.path.abspath(args.tasks), os.getcwd())
    docs = sourcedocs.collect(args.source, out_dir)
    sources = " · ".join(
        f'<a href="{html.escape(s.split("=", 1)[1])}"'
        + (f' data-doc="{html.escape(s.split("=", 1)[0])}"' if s.split("=", 1)[0] in docs else "")
        + f'>{html.escape(s.split("=", 1)[0])}</a>' for s in args.source if "=" in s
    )
    storage_key = args.storage_key or re.sub(r"[^a-z0-9-]+", "-", os.path.splitext(os.path.basename(args.out))[0].lower()) + "-v1"
    subtitle = args.subtitle or f"{total} tâches · {len(lots)} lots"
    phase_override = None
    if args.phases:
        raw = json.load(open(args.phases, encoding="utf-8"))
        phase_override = raw.get("phases") if isinstance(raw, dict) else raw
    phases = ph.build_phases(phase_override, read_existing_phases(args.out))
    phases_json = json.dumps({"phases": phases}, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    footer = (f'Fichier de suivi interactif · état de référence <b>dans ce fichier</b> · brouillon local (clé <code>{storage_key}</code>)'
              + (f" · sources : {sources}" if sources else ""))

    values = {
        "LANG": args.lang, "TITLE": html.escape(args.title), "H1": html.escape(args.h1), "EYEBROW": html.escape(args.eyebrow),
        "BADGE_HTML": f'<span class="badge">{html.escape(args.badge)}</span>' if args.badge else "",
        "INFO_HTML": info_html(args, subtitle, sources), "CONTEXT_HTML": context_html(args, subtitle, sources),
        "PROCEDURE_HTML": procedure_html(tasks_rel),
        "FILE_UPDATED": previous_updated if state and previous_updated else today, "TOTAL": str(total),
        "TASKS_FILE": html.escape(tasks_rel),
        "LOTS_HTML": lots_html(lots, state), "FOOTER_HTML": footer, "STORAGE_KEY": storage_key,
        "PHASES_JSON": phases_json,
        "SOURCE_DOCS_JSON": sourcedocs.to_json(docs),
    }
    out = open(TEMPLATE, encoding="utf-8").read()
    for key, val in values.items():
        out = out.replace("{{" + key + "}}", val)
    leftover = re.findall(r"\{\{[A-Z_]+\}\}", out)
    if leftover:
        sys.exit(f"Marqueurs non remplacés : {leftover}")
    os.makedirs(out_dir, exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(out)
    kept = sum(1 for l in lots for t in l["tasks"] if t["id"] in state)
    print(f"{args.out} : {total} tâches, {len(lots)} lots ({kept} états conservés)")


if __name__ == "__main__":
    main()
