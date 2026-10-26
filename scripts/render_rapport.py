#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_rapport.py — génère `docs/rapport-qualite-workflow.html` depuis la source Markdown.

Convention du framework : « Markdown est la source, HTML est un rendu ». Le HTML produit
porte la mention « fichier généré, ne pas modifier ». Aucune dépendance externe (bibliothèque
standard uniquement).

Usage :
    python3 scripts/render_rapport.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "rapport-qualite-workflow.md"
DST = ROOT / "docs" / "rapport-qualite-workflow.html"

SEV_CLASS = {
    "Critique": "critique",
    "Important": "important",
    "Mineur": "mineur",
    "Amélioration": "amelioration",
}


# ---------------------------------------------------------------------------
# Parsing inline
# ---------------------------------------------------------------------------
def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text: str) -> str:
    text = escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9à-ÿ]+", "-", text.lower()).strip("-")


# ---------------------------------------------------------------------------
# Parsing de blocs
# ---------------------------------------------------------------------------
def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|?[\s:|-]+\|?\s*$", line)) and "-" in line


def render_table(header: list[str], rows: list[list[str]]) -> str:
    th = "".join("<th>" + inline(c) + "</th>" for c in header)
    trs = "".join(
        "<tr>" + "".join("<td>" + inline(c) + "</td>" for c in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def render_item(item: dict) -> str:
    sev = None
    effort = None
    parts: list[str] = []
    lines = item["lines"]
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = re.match(r"\*\*Sévérité\*\*\s*:\s*(.*)", line)
        if m:
            sev = m.group(1).strip()
            i += 1
            continue
        m = re.match(r"\*\*Effort\*\*\s*:\s*(.*)", line)
        if m:
            effort = m.group(1).strip()
            i += 1
            continue
        if re.match(r"\s*[-*]\s+", line):
            items: list[str] = []
            while i < n and re.match(r"\s*[-*]\s+", lines[i]):
                items.append(inline(re.sub(r"^\s*[-*]\s+", "", lines[i])))
                i += 1
            parts.append("<ul>" + "".join("<li>" + t + "</li>" for t in items) + "</ul>")
            continue
        m = re.match(r"\*\*([^*]+)\*\*\s*:\s*(.*)", line)
        if m:
            parts.append(
                '<p class="kv"><span class="lbl">%s</span> %s</p>'
                % (escape(m.group(1)), inline(m.group(2)))
            )
            i += 1
            continue
        parts.append("<p>" + inline(line.strip()) + "</p>")
        i += 1

    cls = SEV_CLASS.get(sev, "amelioration")
    sev_tag = ('<span class="tag %s">%s</span>' % (cls, escape(sev))) if sev else ""
    effort_tag = (
        '<span class="effort" title="Effort estimé (taille de t-shirt)">Effort %s</span>'
        % escape(effort)
    ) if effort else ""
    head = (
        '<div class="head"><span class="id %s">%s</span>'
        '<div><h3 class="title">%s %s %s</h3></div></div>'
        % (cls, escape(item["id"]), inline(item["title"]), sev_tag, effort_tag)
    )
    return '<div class="item">%s<div class="body">%s</div></div>' % (head, "".join(parts))


def render_blocks(lines: list[str], start: int) -> str:
    out: list[str] = []
    cur_item: dict | None = None
    i, n = start, len(lines)

    def flush() -> None:
        nonlocal cur_item
        if cur_item is not None:
            out.append(render_item(cur_item))
            cur_item = None

    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            level = len(h.group(1))
            txt = h.group(2)
            if level == 3 and re.match(r"^(C\d+|A\d+)\b", txt):
                flush()
                m = re.match(r"^(C\d+|A\d+)\s*[—-]\s*(.*)$", txt)
                cur_item = {"id": m.group(1), "title": m.group(2) or "", "lines": []}
                i += 1
                continue
            flush()
            out.append(f'<h{level} id="{slug(txt)}">{inline(txt)}</h{level}>')
            i += 1
            continue
        if cur_item is not None:
            cur_item["lines"].append(line)
            i += 1
            continue
        if line.startswith("```"):
            buf: list[str] = []
            i += 1
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + escape("\n".join(buf)) + "</code></pre>")
            continue
        if line.startswith("|") and i + 1 < n and is_separator(lines[i + 1]):
            header = split_row(line)
            i += 2
            rows: list[list[str]] = []
            while i < n and lines[i].startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            out.append(render_table(header, rows))
            continue
        if line.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i][1:].lstrip())
                i += 1
            out.append("<blockquote>" + inline(" ".join(buf)) + "</blockquote>")
            continue
        if re.match(r"\s*[-*]\s+", line):
            items = []
            while i < n and re.match(r"\s*[-*]\s+", lines[i]):
                items.append(inline(re.sub(r"^\s*[-*]\s+", "", lines[i])))
                i += 1
            out.append("<ul>" + "".join("<li>" + t + "</li>" for t in items) + "</ul>")
            continue
        if re.match(r"\s*\d+\.\s+", line):
            items = []
            while i < n and re.match(r"\s*\d+\.\s+", lines[i]):
                items.append(inline(re.sub(r"^\s*\d+\.\s+", "", lines[i])))
                i += 1
            out.append('<ol class="roadmap">' + "".join("<li>" + t + "</li>" for t in items) + "</ol>")
            continue
        out.append("<p>" + inline(line.strip()) + "</p>")
        i += 1

    flush()
    return "\n".join(out)


def build_html(title: str, lead: str, body: str, toc: list[str]) -> str:
    toc_html = "".join(
        '<li><a href="#%s">%s</a></li>' % (slug(t), inline(t)) for t in toc
    )
    return TEMPLATE.format(
        title=title,
        lead=lead,
        toc=toc_html,
        body=body,
        src_rel=SRC.relative_to(ROOT).as_posix(),
    )


def render(md_text: str) -> str:
    lines = md_text.split("\n")
    n = len(lines)
    i = 0

    title = "Rapport"
    lead = ""
    # Titre (H1) puis citation d'introduction.
    while i < n:
        line = lines[i]
        if title == "Rapport" and line.startswith("# "):
            title = inline(line[2:].strip())
            i += 1
            continue
        if line.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i][1:].lstrip())
                i += 1
            lead = inline(" ".join(buf))
            continue
        if not line.strip():
            i += 1
            continue
        break

    # Sommaire depuis les titres de section `##`.
    toc = [re.sub(r"^##\s+", "", ln).strip() for ln in lines if re.match(r"^##\s+", ln)]

    body = render_blocks(lines, i)
    return build_html(title, lead, body, toc)


TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --bg:#f6f7f9; --surface:#fff; --ink:#1c2430; --muted:#5b6572; --line:#e3e7ec;
    --brand:#16407a; --brand-soft:#eaf1fb; --accent:#0e7a5f;
    --critique:#b3261e; --critique-bg:#fdecea;
    --important:#b26a00; --important-bg:#fff4e0;
    --mineur:#8a6d00; --mineur-bg:#fdf6dc;
    --amelioration:#16407a; --amelioration-bg:#eaf1fb;
    --radius:12px; --shadow:0 1px 2px rgba(16,24,40,.05),0 8px 24px rgba(16,24,40,.06);
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;
  }}
  a {{ color:var(--brand); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
  .wrap {{ max-width:960px; margin:0 auto; padding:0 24px 80px; }}
  header.hero {{
    background:linear-gradient(135deg,#0d2f5c 0%,#16407a 55%,#1b5a8f 100%);
    color:#fff; padding:44px 0 40px; border-bottom:4px solid #0e7a5f;
  }}
  header.hero .wrap {{ padding-bottom:0; }}
  header.hero h1 {{ font-size:30px; line-height:1.2; margin:0 0 12px; font-weight:800; }}
  header.hero p.lead {{ margin:0; max-width:760px; opacity:.93; font-size:15px; }}
  header.hero code {{ background:rgba(255,255,255,.14); padding:1px 6px; border-radius:5px; }}
  section {{ margin-top:40px; }}
  h2 {{ font-size:21px; margin:0 0 12px; font-weight:800; padding-top:12px; }}
  h3.title {{ font-size:16.5px; font-weight:700; margin:0; }}
  .sub {{ color:var(--muted); margin:0 0 20px; font-size:14px; }}
  nav.toc {{
    background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
    padding:16px 20px; box-shadow:var(--shadow);
  }}
  nav.toc ol {{ margin:0; padding-left:20px; columns:2; column-gap:32px; }}
  nav.toc li {{ margin:3px 0; font-size:14px; }}
  p, li {{ color:var(--ink); }}
  blockquote {{
    margin:16px 0; padding:12px 16px; border-left:3px solid var(--brand);
    background:var(--brand-soft); border-radius:0 8px 8px 0; color:#25415f;
  }}
  code {{
    font-family:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;
    font-size:12.8px; background:#eef1f5; border-radius:5px; padding:1px 6px; color:#234;
  }}
  pre {{ background:#101826; color:#e6edf3; padding:16px; border-radius:10px; overflow:auto; }}
  pre code {{ background:none; color:inherit; padding:0; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; background:var(--surface); box-shadow:var(--shadow); border-radius:10px; overflow:hidden; }}
  th, td {{ text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ background:var(--brand-soft); color:var(--brand); font-weight:700; font-size:12px; text-transform:uppercase; letter-spacing:.05em; }}
  tr:last-child td {{ border-bottom:none; }}
  ul, ol {{ padding-left:22px; }}
  ol.roadmap {{ list-style:none; padding-left:0; counter-reset:step; }}
  ol.roadmap li {{
    counter-increment:step; position:relative; padding:12px 0 12px 46px;
    border-bottom:1px dashed var(--line);
  }}
  ol.roadmap li::before {{
    content:counter(step); position:absolute; left:0; top:12px; width:30px; height:30px;
    border-radius:50%; background:var(--brand); color:#fff; font-weight:800;
    display:flex; align-items:center; justify-content:center; font-size:14px;
  }}
  .item {{
    background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
    margin-bottom:16px; box-shadow:var(--shadow); overflow:hidden;
  }}
  .item .head {{ display:flex; align-items:flex-start; gap:14px; padding:16px 20px; border-bottom:1px solid var(--line); }}
  .item .id {{
    flex:none; font-weight:800; font-size:13px; color:#fff; border-radius:8px;
    padding:4px 9px; margin-top:2px;
  }}
  .id.critique {{ background:var(--critique); }} .id.important {{ background:var(--important); }}
  .id.mineur {{ background:var(--mineur); }} .id.amelioration {{ background:var(--amelioration); }}
  .item .body {{ padding:16px 20px 18px; }}
  .tag {{
    display:inline-block; font-size:11px; font-weight:700; letter-spacing:.04em;
    text-transform:uppercase; border-radius:6px; padding:2px 8px; margin-left:8px; vertical-align:1px;
  }}
  .tag.critique {{ background:var(--critique-bg); color:var(--critique); }}
  .tag.important {{ background:var(--important-bg); color:var(--important); }}
  .tag.mineur {{ background:var(--mineur-bg); color:var(--mineur); }}
  .tag.amelioration {{ background:var(--amelioration-bg); color:var(--amelioration); }}
  .effort {{
    display:inline-block; font-size:11px; font-weight:800; letter-spacing:.04em;
    background:#eef1f5; color:#31435c; border-radius:999px; padding:2px 10px; margin-left:6px;
  }}
  .kv {{ margin:0 0 8px; }}
  .kv .lbl {{
    font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.08em; color:var(--muted);
  }}
  footer {{ margin-top:48px; padding-top:20px; border-top:1px solid var(--line); color:var(--muted); font-size:12.5px; }}
  .gen {{
    display:inline-block; background:var(--mineur-bg); color:var(--mineur); font-size:12px;
    border-radius:6px; padding:3px 10px; font-weight:700; margin-top:12px;
  }}
  @media (max-width:640px) {{ nav.toc ol {{ columns:1; }} header.hero h1 {{ font-size:24px; }} }}
  @media print {{ body {{ background:#fff; }} .item, nav.toc, table {{ box-shadow:none; }} .item {{ break-inside:avoid; }} }}
</style>
</head>
<body>
<header class="hero">
  <div class="wrap">
    <h1>{title}</h1>
    <p class="lead">{lead}</p>
  </div>
</header>
<div class="wrap">
  <nav class="toc" aria-label="Sommaire"><ol>{toc}</ol></nav>
  {body}
  <footer>
    <p>Rapport d'audit du workflow SDLC — constats fondés sur la lecture de la spécification
    de référence, de la configuration, des gabarits, des skills et des scripts du dépôt.</p>
    <span class="gen">Fichier généré — ne pas modifier. Source : {src_rel} (script scripts/render_rapport.py).</span>
  </footer>
</div>
</body>
</html>
"""


def main() -> int:
    if not SRC.is_file():
        print(f"erreur : source absente : {SRC}", file=sys.stderr)
        return 2
    html = render(SRC.read_text(encoding="utf-8"))
    DST.write_text(html, encoding="utf-8")
    print(f"généré : {DST.relative_to(ROOT)} ({len(html)} octets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
