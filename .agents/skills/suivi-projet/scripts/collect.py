#!/usr/bin/env python3
"""collect.py — normalise les sources du tableau de bord « suivi-projet ».

Usage :
    python3 collect.py [RACINE_DU_PROJET]

Lit, depuis la racine du projet (défaut : répertoire courant) :
  - sdlc.config.yaml                          (config, seuils, gates, profils) ;
  - reports/summary.json                      s'il existe, sinon :
      reports/coverage/ (Cobertura, lcov, JaCoCo, coverage.py JSON),
      reports/junit/*.xml, reports/security/*.sarif ;
  - openspec/changes/*/ et openspec/changes/archive/ (tâches cochées / total) ;
  - docs/suivi/state.json                     (features, actions, envs) ;
  - docs/journal/runs.jsonl, deploys.jsonl ;
  - docs/incidents/*.md ;
  - tous les .md de docs/ et openspec/ (lecteur Markdown).

Écrit :
  - docs/suivi/project-data.json
  - docs/suivi/docs-data.json
  - ajoute un instantané à docs/metrics/history.jsonl (sans doublon du même jour).

Python 3.9+, bibliothèque standard uniquement ; PyYAML n'est utilisé que s'il est
installé, sinon un analyseur couvrant le sous-ensemble de sdlc.config.example.yaml.
"""

import argparse
import datetime
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

SEV_ORDER = ["critique", "haute", "moyenne", "basse"]
PALETTE = ["#5c6b7a", "#0f4c81", "#1379b0", "#2b6cb0", "#7d3c98", "#1f9d55",
           "#b7791f", "#0f766e", "#c0392b", "#4a5568", "#6b46c1", "#2f855a"]

# Défauts de la section `paths` (§ 13.3 de la spec), surchargés par sdlc.config.yaml.
DEFAULT_PATHS = {
    "templates": ".sdlc/templates",
    "spec": ".sdlc/workflow-sdlc.md",
    "docs": "docs",
    "cadrage": "docs/00-cadrage",
    "architecture": "docs/architecture",
    "adr": "docs/architecture/adr",
    "ops": "docs/ops",
    "recette": "docs/recette",
    "incidents": "docs/incidents",
    "retro": "docs/retro",
    "client": "docs/client",
    "journal": "docs/journal",
    "suivi": "docs/suivi",
    "metrics": "docs/metrics",
    "reports": "reports",
    "ci_script": "scripts/ci.sh",
}


def resolve_paths(config):
    """Fusionne `paths` de la config avec les défauts (jamais de valeur vide)."""
    out = dict(DEFAULT_PATHS)
    raw = (config or {}).get("paths") or {}
    if isinstance(raw, dict):
        for key in DEFAULT_PATHS:
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                out[key] = value.strip()
    return out


def _p(paths, key):
    return (paths or DEFAULT_PATHS).get(key, DEFAULT_PATHS[key])

# --------------------------------------------------------------------------- #
# Analyseur YAML minimal (sous-ensemble de sdlc.config.example.yaml)
# --------------------------------------------------------------------------- #

def _strip_comment(line):
    out, q = [], None
    for c in line:
        if q:
            out.append(c)
            if c == q:
                q = None
        elif c in "\"'":
            q = c
            out.append(c)
        elif c == "#":
            break
        else:
            out.append(c)
    return "".join(out).rstrip()


def _split_top(s):
    """Découpe sur les virgules de premier niveau (respecte guillemets et crochets)."""
    parts, depth, q, cur = [], 0, None, ""
    for c in s:
        if q:
            cur += c
            if c == q:
                q = None
        elif c in "\"'":
            q = c
            cur += c
        elif c in "[{":
            depth += 1
            cur += c
        elif c in "]}":
            depth -= 1
            cur += c
        elif c == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += c
    if cur.strip() or parts:
        parts.append(cur.strip())
    return parts


def _split_kv(s):
    depth, q = 0, None
    for i, c in enumerate(s):
        if q:
            if c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        elif c == ":" and depth == 0:
            return s[:i].strip(), s[i + 1:].strip()
    return s.strip(), ""


def _parse_scalar(s):
    s = s.strip()
    if s == "":
        return None
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "none", "~"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def _parse_value(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(p) for p in _split_top(inner)]
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1].strip()
        if not inner:
            return {}
        out = {}
        for p in _split_top(inner):
            k, v = _split_kv(p)
            out[_parse_scalar(k)] = _parse_value(v)
        return out
    return _parse_scalar(s)


def parse_yaml(text):
    lines = []
    for raw in text.splitlines():
        s = _strip_comment(raw)
        if not s.strip():
            continue
        lines.append((len(s) - len(s.lstrip(" ")), s.strip()))
    if not lines:
        return {}

    pos = [0]

    def parse_block(indent):
        if pos[0] >= len(lines):
            return None
        content0 = lines[pos[0]][1]
        if content0 == "-" or content0.startswith("- "):
            result = []
            while pos[0] < len(lines):
                ind, content = lines[pos[0]]
                if ind < indent or not (content == "-" or content.startswith("- ")):
                    break
                item = content[1:].strip()
                pos[0] += 1
                if item == "":
                    if pos[0] < len(lines) and lines[pos[0]][0] > ind:
                        result.append(parse_block(lines[pos[0]][0]))
                    else:
                        result.append(None)
                elif item.startswith(("{", "[")):
                    result.append(_parse_value(item))
                elif ":" in item and not item.startswith(("\"", "'")):
                    k, v = _split_kv(item)
                    d = {}
                    if v == "":
                        if pos[0] < len(lines) and lines[pos[0]][0] > ind:
                            d[k] = parse_block(lines[pos[0]][0])
                        else:
                            d[k] = None
                    else:
                        d[k] = _parse_value(v)
                    while pos[0] < len(lines) and lines[pos[0]][0] > ind:
                        sub = parse_block(lines[pos[0]][0])
                        if isinstance(sub, dict):
                            d.update(sub)
                        else:
                            break
                    result.append(d)
                else:
                    result.append(_parse_value(item))
            return result
        result = {}
        while pos[0] < len(lines):
            ind, content = lines[pos[0]]
            if ind < indent or content == "-" or content.startswith("- "):
                break
            k, v = _split_kv(content)
            pos[0] += 1
            if v == "":
                if pos[0] < len(lines) and lines[pos[0]][0] > ind:
                    result[k] = parse_block(lines[pos[0]][0])
                else:
                    result[k] = None
            else:
                result[k] = _parse_value(v)
        return result

    return parse_block(lines[0][0])


def load_yaml_file(path):
    if not os.path.isfile(path):
        return {}
    text = open(path, encoding="utf-8").read()
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except Exception:
        return parse_yaml(text) or {}


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #

def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def read_jsonl(path):
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def pct(hit, total):
    if not total:
        return None
    return round(100.0 * hit / total, 1)


def human_duration(seconds):
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        return None
    seconds = int(round(seconds))
    m, s = divmod(seconds, 60)
    if m:
        return "%d min %02d s" % (m, s)
    return "%d s" % s


def fmt_ts(ts):
    if not isinstance(ts, str) or not ts:
        return None
    return ts.replace("T", " ")[:16]


# --------------------------------------------------------------------------- #
# Couverture
# --------------------------------------------------------------------------- #

def _cobertura(path):
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return None, []
    lr = root.get("line-rate")
    coverage = round(100.0 * float(lr), 1) if lr is not None else None
    modules = []
    for pkg in root.iter("package"):
        name = pkg.get("name")
        pr = pkg.get("line-rate")
        if name and pr is not None:
            modules.append({"name": name, "coverage": round(100.0 * float(pr), 1), "tests": None})
    return coverage, modules


def _jacoco(path):
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return None, []
    coverage = None
    counters = root.findall("counter")
    for c in counters:
        if c.get("type") == "LINE":
            missed = int(c.get("missed", 0))
            covered = int(c.get("covered", 0))
            coverage = pct(covered, missed + covered)
    modules = []
    for pkg in root.findall("package"):
        name = pkg.get("name")
        for c in pkg.findall("counter"):
            if c.get("type") == "LINE":
                missed = int(c.get("missed", 0))
                covered = int(c.get("covered", 0))
                modules.append({"name": name, "coverage": pct(covered, missed + covered), "tests": None})
    return coverage, modules


def _lcov(path):
    lf = lh = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("LF:"):
                lf += int(line[3:].strip() or 0)
            elif line.startswith("LH:"):
                lh += int(line[3:].strip() or 0)
    return pct(lh, lf), []


def _coveragepy_json(path):
    data = read_json(path)
    if not isinstance(data, dict):
        return None, []
    totals = data.get("totals") if isinstance(data.get("totals"), dict) else data
    coverage = totals.get("percent_covered")
    coverage = round(float(coverage), 1) if coverage is not None else None
    modules = []
    files = data.get("files")
    if isinstance(files, dict):
        groups = {}
        for fpath, info in files.items():
            top = fpath.split("/")[0] if "/" in fpath else (fpath.split("\\")[0] if "\\" in fpath else fpath)
            summary = info.get("summary") if isinstance(info, dict) else None
            pc = summary.get("percent_covered") if isinstance(summary, dict) else None
            if pc is None:
                continue
            g = groups.setdefault(top, [0.0, 0])
            g[0] += float(pc)
            g[1] += 1
        for name, (s, n) in sorted(groups.items()):
            modules.append({"name": name, "coverage": round(s / n, 1), "tests": None})
    return coverage, modules


def collect_coverage(root, paths=None):
    """Retourne (coverage_pct, modules). Détecte le format par fichier."""
    base = os.path.join(root, _p(paths, "reports"), "coverage")
    if not os.path.isdir(base):
        return None, []
    files = sorted(glob.glob(os.path.join(base, "**", "*"), recursive=True))
    for path in files:
        low = path.lower()
        try:
            if low.endswith(".info"):
                return _lcov(path)
            if low.endswith(".json"):
                cov, mods = _coveragepy_json(path)
                if cov is not None or mods:
                    return cov, mods
            if low.endswith(".xml"):
                head = open(path, encoding="utf-8", errors="replace").read(2000)
                if "jacoco" in head.lower() or 'counter type="LINE"' in head:
                    cov, mods = _jacoco(path)
                else:
                    cov, mods = _cobertura(path)
                if cov is not None or mods:
                    return cov, mods
        except Exception:
            continue
    return None, []


# --------------------------------------------------------------------------- #
# Tests JUnit
# --------------------------------------------------------------------------- #

def collect_junit(root, paths=None):
    base = os.path.join(root, _p(paths, "reports"), "junit")
    total = failed = skipped = 0
    duration = 0.0
    found = False
    for path in sorted(glob.glob(os.path.join(base, "**", "*.xml"), recursive=True)):
        try:
            root_el = ET.parse(path).getroot()
        except Exception:
            continue
        found = True
        suites = [root_el] if root_el.tag == "testsuite" else list(root_el.iter("testsuite"))
        for st in suites:
            total += int(st.get("tests", 0) or 0)
            failed += int(st.get("failures", 0) or 0) + int(st.get("errors", 0) or 0)
            skipped += int(st.get("skipped", 0) or 0)
            try:
                duration += float(st.get("time", 0) or 0)
            except ValueError:
                pass
    if not found:
        return None
    return {"total": total, "failed": failed, "skipped": skipped, "duration": human_duration(duration)}


# --------------------------------------------------------------------------- #
# SARIF
# --------------------------------------------------------------------------- #

def _sev_from_security_severity(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v >= 9.0:
        return "critique"
    if v >= 7.0:
        return "haute"
    if v >= 4.0:
        return "moyenne"
    return "basse"


def _sev_from_level(level):
    return {"error": "haute", "warning": "moyenne", "note": "basse", "none": "basse"}.get(level, "basse")


def collect_sarif(root, paths=None):
    base = os.path.join(root, _p(paths, "reports"), "security")
    paths = sorted(glob.glob(os.path.join(base, "**", "*.sarif"), recursive=True))
    if not paths:
        return None
    findings = []
    counts = {k: 0 for k in SEV_ORDER}
    by_source = {}
    for path in paths:
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        for run in data.get("runs", []) or []:
            driver = ((run.get("tool") or {}).get("driver") or {})
            tool = driver.get("name") or "outil inconnu"
            rules = {r.get("id"): r for r in (driver.get("rules") or []) if isinstance(r, dict)}
            for res in run.get("results", []) or []:
                if not isinstance(res, dict):
                    continue
                props = res.get("properties") or {}
                rule_id = res.get("ruleId") or ((res.get("rule") or {}).get("id"))
                rule = rules.get(rule_id) or {}
                sev = None
                for src in (props.get("security-severity"),
                            ((rule.get("properties") or {}).get("security-severity"))):
                    if src is not None:
                        sev = _sev_from_security_severity(src)
                        if sev:
                            break
                if sev is None:
                    sev = _sev_from_level(res.get("level") or rule.get("defaultConfiguration", {}).get("level"))
                counts[sev] += 1
                loc = {}
                locations = res.get("locations") or []
                if locations and isinstance(locations[0], dict):
                    loc = locations[0].get("physicalLocation") or {}
                uri = ((loc.get("artifactLocation") or {}).get("uri")) or ""
                line = (loc.get("region") or {}).get("startLine")
                where = uri + ((":%s" % line) if line else "")
                since = datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
                findings.append({
                    "sev": sev,
                    "id": rule_id or "(sans identifiant)",
                    "source": tool,
                    "where": where or "(emplacement non fourni)",
                    "status": "ouvert",
                    "since": since,
                })
                row = by_source.setdefault(tool, {k: 0 for k in SEV_ORDER})
                row[sev] += 1
    findings.sort(key=lambda f: (SEV_ORDER.index(f["sev"]), f["id"]))
    by_source_list = [{"source": name, "c": c["critique"], "h": c["haute"],
                       "m": c["moyenne"], "l": c["basse"]}
                      for name, c in sorted(by_source.items())]
    return {"counts": counts, "bySource": by_source_list, "findings": findings}


# --------------------------------------------------------------------------- #
# OpenSpec
# --------------------------------------------------------------------------- #

CHECK_RE = re.compile(r"^\s*-\s+\[([ xX])\]")
HEAD_RE = re.compile(r"^#\s+(.*\S)\s*$", re.M)
STATUS_RE = re.compile(r"^\s*[-*]?\s*[Ss]tatut\s*:\s*(.+?)\s*$", re.M)
DATE_RE = re.compile(r"^\s*[-*]?\s*[Dd]ate\s*:\s*(.+?)\s*$", re.M)


def count_tasks(path):
    total = checked = 0
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = CHECK_RE.match(line)
            if m:
                total += 1
                if m.group(1).lower() == "x":
                    checked += 1
    return [checked, total] if total else None


def scan_changes(root):
    base = os.path.join(root, "openspec", "changes")
    active, archived = [], []
    if not os.path.isdir(base):
        return active, archived
    for name in sorted(os.listdir(base)):
        d = os.path.join(base, name)
        if not os.path.isdir(d):
            continue
        if name == "archive":
            for name2 in sorted(os.listdir(d)):
                d2 = os.path.join(d, name2)
                if os.path.isdir(d2):
                    archived.append({"id": name2, "path": d2, "tasks": count_tasks(os.path.join(d2, "tasks.md"))})
            continue
        active.append({"id": name, "path": d, "tasks": count_tasks(os.path.join(d, "tasks.md"))})
    return active, archived


# --------------------------------------------------------------------------- #
# Markdown : catégories, embarquement
# --------------------------------------------------------------------------- #

CATEGORIES = [
    ("🎯", "Cadrage", lambda p: p.startswith("docs/00-cadrage/")),
    ("📐", "Décisions d'architecture (ADR)", lambda p: p.startswith("docs/architecture/adr/")),
    ("📐", "Architecture", lambda p: p.startswith("docs/architecture/")),
    ("📋", "Specs (OpenSpec)", lambda p: p.startswith("openspec/")),
    ("🚀", "Exploitation", lambda p: p.startswith("docs/ops/")),
    ("✅", "Recette & qualité", lambda p: p.startswith("docs/recette/")),
    ("🛡", "Incidents", lambda p: p.startswith("docs/incidents/")),
    ("🗂", "Pilotage", lambda p: p.startswith("docs/retro/") or p.startswith("docs/client/")),
    ("📄", "Documentation diverse", lambda p: True),
]


def scan_md(root, paths=None):
    """Retourne {chemin_relatif: (contenu, mtime)} pour les .md de docs/ et openspec/."""
    out = {}
    for base in (_p(paths, "docs"), "openspec"):
        d = os.path.join(root, base)
        if not os.path.isdir(d):
            continue
        for path in glob.glob(os.path.join(d, "**", "*.md"), recursive=True):
            try:
                content = open(path, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            out[rel(root, path)] = (content, os.path.getmtime(path))
    return out


def md_title(content, path):
    m = HEAD_RE.search(content)
    if m:
        return m.group(1).strip()
    return os.path.basename(path)


def category_of(path):
    for icon, title, test in CATEGORIES:
        if test(path):
            return icon, title
    return "📄", "Documentation diverse"


def build_docs(root, dashboard_file, md_files, embed_max_kb, embed_markdown, paths=None):
    md_dir = os.path.dirname(os.path.abspath(os.path.join(root, dashboard_file)))
    cats = {}
    for path, (content, mtime) in md_files.items():
        icon, title = category_of(path)
        cats.setdefault((icon, title), []).append({
            "t": md_title(content, path),
            "p": path,
            "m": "maj " + datetime.date.fromtimestamp(mtime).isoformat(),
            "_mtime": mtime,
        })
    categories = []
    for (icon, title), items in cats.items():
        items.sort(key=lambda i: i["t"].lower())
        for i in items:
            i.pop("_mtime", None)
        categories.append({"icon": icon, "title": title, "items": items})
    order = [c[1] for c in CATEGORIES]
    categories.sort(key=lambda c: order.index(c["title"]) if c["title"] in order else 99)

    warnings = []
    files = {}
    if not embed_markdown:
        warnings.append("embarquement Markdown désactivé (dashboard.embed_markdown = false) : "
                        "le lecteur nécessite le mode http.")
    else:
        limit = max(0, int(embed_max_kb)) * 1024
        ordered = sorted(md_files.items(), key=lambda kv: kv[1][1], reverse=True)
        used = 0
        for path, (content, mtime) in ordered:
            size = len(content.encode("utf-8"))
            if used + size > limit:
                warnings.append("limite d'embarquement atteinte (%d Kio) : %s et les documents plus "
                                "anciens ne sont pas embarqués — servir le tableau de bord en http "
                                "pour les lire." % (embed_max_kb, path))
                break
            files[path] = {"content": content}
            used += size
        if len(files) < len(md_files) and not warnings:
            warnings.append("embarquement partiel limité à %d Kio." % embed_max_kb)

    # Schémas d'architecture : uniquement docs/architecture/ (fichiers .html),
    # avec en vignette le .png de même nom s'il existe. Aucun schéma ⇒ liste vide
    # (le tableau de bord affiche alors « Aucun schéma trouvé »).
    diagrams = []
    arch_dir = os.path.join(root, _p(paths, "architecture"))
    for path in sorted(glob.glob(os.path.join(arch_dir, "**", "*.html"), recursive=True)):
        p = rel(root, path)
        png = os.path.splitext(path)[0] + ".png"
        item = {"title": os.path.splitext(os.path.basename(path))[0],
                "sub": p,
                "href": os.path.relpath(path, md_dir).replace(os.sep, "/")}
        if os.path.isfile(png):
            item["img"] = os.path.relpath(png, md_dir).replace(os.sep, "/")
        diagrams.append(item)

    return {"diagrams": diagrams, "categories": categories}, {"files": files, "warnings": warnings}


# --------------------------------------------------------------------------- #
# Journaux, incidents
# --------------------------------------------------------------------------- #

def collect_runs(root, max_review, paths=None):
    runs = read_jsonl(os.path.join(root, _p(paths, "journal"), "runs.jsonl"))
    by_agent = {}
    by_feature = {}
    for i, r in enumerate(runs):
        if not isinstance(r, dict):
            continue
        agent = r.get("agent") or "inconnu"
        a = by_agent.setdefault(agent, {"name": agent, "role": None, "tasks": 0, "first": 0,
                                        "done": 0, "escal": 0, "dur": []})
        if r.get("role"):
            a["role"] = r["role"]
        if r.get("status") == "done":
            a["tasks"] += 1
            a["done"] += 1
            if r.get("review_iteration") in (None, 1):
                a["first"] += 1
        ri = r.get("review_iteration")
        if isinstance(ri, int) and isinstance(max_review, int) and ri >= max_review:
            a["escal"] += 1
        if isinstance(r.get("duration_s"), (int, float)):
            a["dur"].append(r["duration_s"])
        feat = r.get("feature") or "(sans feature)"
        f = by_feature.setdefault(feat, {"feature": feat, "runs": 0, "cost": 0.0, "cost_known": True,
                                         "done": 0, "first": 0})
        f["runs"] += 1
        if r.get("status") == "done":
            f["done"] += 1
            if r.get("review_iteration") in (None, 1):
                f["first"] += 1
        if isinstance(r.get("cost_eur"), (int, float)):
            f["cost"] += r["cost_eur"]
        else:
            f["cost_known"] = False
    agents = []
    for i, (name, a) in enumerate(sorted(by_agent.items())):
        tasks = a["tasks"] or (a["done"] or 0)
        if tasks == 0:
            tasks = sum(1 for r in runs if isinstance(r, dict) and r.get("agent") == name)
        avg = human_duration(sum(a["dur"]) / len(a["dur"])) if a["dur"] else None
        agents.append({
            "name": name,
            "role": a["role"] or "exécutant",
            "tasks": tasks,
            "firstPass": round(100.0 * a["first"] / a["done"]) if a["done"] else None,
            "escalations": a["escal"],
            "avg": avg,
            "color": PALETTE[i % len(PALETTE)],
        })
    costs = []
    for feat, f in sorted(by_feature.items()):
        costs.append({
            "feature": feat,
            "runs": f["runs"],
            "cost": ("%.0f €" % f["cost"]) if (f["cost_known"] and f["cost"]) else None,
            "review": ("%d %%" % round(100.0 * f["first"] / f["done"])) if f["done"] else None,
        })
    return agents, costs


def collect_deploys(root, md_dir, paths=None):
    rows = read_jsonl(os.path.join(root, _p(paths, "journal"), "deploys.jsonl"))
    deploys = []
    latest_by_env = {}
    result_label = {"success": "succès", "rollback": "rollback", "failed": "échec"}
    for r in rows:
        if not isinstance(r, dict):
            continue
        label = result_label.get(r.get("result"), r.get("result"))
        deploys.append({
            "date": fmt_ts(r.get("ts")),
            "env": r.get("env"),
            "version": r.get("version"),
            "result": label,
            "duration": human_duration(r.get("duration_s")),
            "note": r.get("note"),
        })
        env = r.get("env")
        if env:
            latest_by_env[env] = r
    deploys.reverse()  # le plus récent d'abord
    envs = []
    for env, r in latest_by_env.items():
        envs.append({
            "name": env,
            "version": r.get("version"),
            "health": "sain" if r.get("result") == "success" else "dégradé",
            "date": fmt_ts(r.get("ts")),
            "by": r.get("by"),
        })
    return deploys, envs


def collect_incidents(root, md_dir, md_files, paths=None):
    out = []
    base = os.path.join(root, _p(paths, "incidents"))
    if not os.path.isdir(base):
        return out
    for path in sorted(glob.glob(os.path.join(base, "*.md"))):
        content = md_files.get(rel(root, path), (None, 0))[0]
        if content is None:
            content = open(path, encoding="utf-8", errors="replace").read()
        title = md_title(content, path)
        m = re.match(r"\s*(INC-\d+)\b[—:-]?\s*(.*)", title)
        if m:
            inc_id, inc_title = m.group(1), m.group(2).strip() or title
        else:
            inc_id, inc_title = os.path.splitext(os.path.basename(path))[0], title
        st = STATUS_RE.search(content)
        dt = DATE_RE.search(content)
        status = (st.group(1).strip().lower() if st else "ouvert")
        out.append({
            "id": inc_id,
            "title": inc_title,
            "status": "clos" if status in ("clos", "résolu", "resolu", "closed") else "ouvert",
            "date": (dt.group(1).strip() if dt else None),
            "pm": os.path.relpath(path, md_dir).replace(os.sep, "/"),
        })
    return out


# --------------------------------------------------------------------------- #
# state.json
# --------------------------------------------------------------------------- #

def normalize_phases(raw):
    """Six statuts de phase tolérant les deux formes du format commun.

    - forme historique : `["done", "done", "doing", "todo", "todo", "todo"]` (six chaînes) ;
    - forme courante (écrite par suivi-taches) : `[{"id": "cadrage", "status": "done", ...}, …]`.
    """
    valid = ("todo", "doing", "blocked", "done")
    if not isinstance(raw, list) or len(raw) != 6:
        return ["todo"] * 6
    out = []
    for phase in raw:
        if isinstance(phase, str) and phase in valid:
            out.append(phase)
        elif isinstance(phase, dict) and phase.get("status") in valid:
            out.append(phase["status"])
        else:
            out.append("todo")
    return out


def build_features(root, state, active_changes, archived_changes):
    task_by_id = {}
    for c in active_changes:
        task_by_id[c["id"]] = c["tasks"]
    for c in archived_changes:
        if c["tasks"]:
            task_by_id.setdefault(c["id"], [c["tasks"][1], c["tasks"][1]])
        else:
            task_by_id.setdefault(c["id"], None)

    features = []
    seen = set()
    for i, f in enumerate(state.get("features") or []):
        if not isinstance(f, dict) or not f.get("id"):
            continue
        fid = f["id"]
        seen.add(fid)
        phases = normalize_phases(f.get("phases"))
        recette = f.get("recette")
        if not (isinstance(recette, list) and len(recette) == 2):
            recette = None
        tasks = f.get("tasks")
        if not (isinstance(tasks, list) and len(tasks) == 2):
            tasks = task_by_id.get(fid)
        features.append({
            "id": fid,
            "name": f.get("name") or fid,
            "color": f.get("color") or PALETTE[i % len(PALETTE)],
            "phases": phases,
            "tasks": tasks,
            "recette": recette,
            "version": f.get("version"),
            "delivered": f.get("delivered"),
            "blocked": f.get("blocked") or 0,
        })
    # Changes en cours non déclarés dans state.json : features dérivées (phases = impl. en cours).
    for c in active_changes:
        if c["id"] in seen:
            continue
        features.append({
            "id": c["id"],
            "name": c["id"],
            "color": PALETTE[len(features) % len(PALETTE)],
            "phases": ["todo", "todo", "doing", "todo", "todo", "todo"],
            "tasks": c["tasks"],
            "recette": None,
            "version": None,
            "delivered": None,
            "blocked": 0,
        })
    return features


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #

def build(root):
    config = load_yaml_file(os.path.join(root, "sdlc.config.yaml"))
    paths = resolve_paths(config)
    project = ((config.get("project") or {}).get("name")) or os.path.basename(os.path.abspath(root))
    dash = config.get("dashboard") or {}
    dashboard_file = dash.get("file") or "docs/suivi-projet.html"
    embed_max_kb = dash.get("embed_max_kb", 2048)
    embed_markdown = dash.get("embed_markdown", True)
    ci_cfg = config.get("ci") or {}
    coverage_min = ci_cfg.get("coverage_min")
    block_on = ci_cfg.get("block_on") or []
    max_review = (config.get("organisation") or {}).get("max_review_iterations", 3)
    deploy_targets = []
    for t in ((config.get("deploy") or {}).get("targets") or []):
        if isinstance(t, dict):
            deploy_targets.append({"component": t.get("component"), "profile": t.get("profile")})

    summary = read_json(os.path.join(root, _p(paths, "reports"), "summary.json"))

    sarif = collect_sarif(root, paths)
    junit = collect_junit(root, paths)

    if summary and isinstance(summary, dict):
        coverage = summary.get("coverage_pct")
        vulns = summary.get("vulns") or {}
        controls = summary.get("controls") or {}
        ci_status = None
        if isinstance(controls, dict) and controls:
            ci_status = "verte" if all(v == "pass" for v in controls.values()) else "rouge"
        ci_when = fmt_ts(summary.get("ts"))
        modules = []
    else:
        coverage, modules = collect_coverage(root, paths)
        if sarif:
            vulns = sarif["counts"]
        else:
            vulns = None
        ci_status, ci_when = None, None

    if sarif:
        security = {"bySource": sarif["bySource"], "findings": sarif["findings"]}
    elif vulns:
        security = {"bySource": [], "findings": []}
    else:
        security = None

    tests = junit
    lint_files = sorted(glob.glob(os.path.join(root, _p(paths, "reports"), "lint", "*.txt")))
    lint = None
    if lint_files:
        offenses = 0
        for p in lint_files:
            offenses += sum(1 for line in open(p, encoding="utf-8", errors="replace") if line.strip())
        lint = {"offenses": offenses, "tool": "linters de la stack"}

    active_changes, archived_changes = scan_changes(root)
    state = read_json(os.path.join(root, _p(paths, "suivi"), "state.json")) or {}
    features = build_features(root, state, active_changes, archived_changes)

    md_files = scan_md(root, paths)
    docs, docs_data = build_docs(root, dashboard_file, md_files, embed_max_kb, embed_markdown, paths)
    md_dir = os.path.dirname(os.path.abspath(os.path.join(root, dashboard_file)))

    deploys, derived_envs = collect_deploys(root, md_dir, paths)
    envs = state.get("envs") if isinstance(state.get("envs"), list) and state.get("envs") else derived_envs
    actions = state.get("actions") if isinstance(state.get("actions"), list) else []
    incidents = collect_incidents(root, md_dir, md_files, paths)
    agents, costs = collect_runs(root, max_review, paths)

    # Instantané du jour. Il est calculé puis ajouté à l'historique (sans doublon
    # le même jour) AVANT de construire la série, afin que les tuiles, l'onglet
    # Sécurité et l'onglet Qualité disposent de la valeur courante dès le premier
    # lancement, même si l'historique ne contient encore aucun point.
    snap = {
        "date": datetime.date.today().isoformat(),
        "coverage_pct": coverage if coverage is not None else None,
        "vulns": vulns if isinstance(vulns, dict) else None,
        "tests": tests["total"] if tests else None,
    }
    history = read_history(root, paths)
    if snapshot_has_data(snap) and not snapshot_is_duplicate(history, snap):
        history = history + [snap]

    # Série d'historique : instantanés de docs/metrics/history.jsonl (12 derniers).
    hist_labels, hist_cov, hist_vulns = [], [], []
    for entry in history[-12:]:
        hist_labels.append(_label_of(entry.get("date")))
        hist_cov.append(entry.get("coverage_pct"))
        if isinstance(entry.get("vulns"), dict):
            v = entry["vulns"]
            hist_vulns.append([v.get("critique"), v.get("haute"), v.get("moyenne"), v.get("basse")])
        else:
            hist_vulns.append(None)
    if not hist_vulns:
        hist_vulns = []

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    ci = None
    if ci_status:
        ci = {"status": ci_status, "pipeline": None, "branch": None, "when": ci_when}

    project_data = {
        "project": project,
        "updated": now,
        "config": {
            "orchestrator": config.get("orchestrator"),
            "executors": config.get("executors") or [],
            "ci": ci_cfg.get("tool"),
            "deploy": deploy_targets,
            "confidentiality": config.get("confidentiality"),
            "coverage_min": coverage_min,
            "block_on": block_on,
        },
        "features": features,
        "actions": actions,
        "envs": envs or [],
        "ci": ci,
        # Valeurs courantes, exposées explicitement : les tuiles, l'onglet
        # Sécurité et l'onglet Qualité les lisent directement, sans dépendre de
        # la longueur de la série d'historique.
        "current": {
            "coverage_pct": snap["coverage_pct"],
            "vulns": snap["vulns"],
            "tests": snap["tests"],
        },
        "history": {"labels": hist_labels, "coverage": hist_cov, "vulns": hist_vulns},
        "modules": modules,
        "quality": {
            "tests": tests,
            "lint": lint,
            "a11y": None,
            "perf": [],
        },
        "security": security,
        "docs": docs,
        "deploys": deploys,
        "incidents": incidents,
        "agents": agents,
        "costs": costs,
    }
    docs_data["embedded_at"] = now
    return project_data, docs_data, snap


def _label_of(date):
    if isinstance(date, str) and len(date) >= 10:
        return date[8:10] + "/" + date[5:7]
    return date or ""


def read_history(root, paths=None):
    return read_jsonl(os.path.join(root, _p(paths, "metrics"), "history.jsonl"))


def snapshot_is_duplicate(history, snap):
    for entry in history:
        if entry.get("date") == snap["date"] \
                and entry.get("coverage_pct") == snap["coverage_pct"] \
                and entry.get("tests") == snap["tests"] \
                and entry.get("vulns") == snap["vulns"]:
            return True
    return False


def snapshot_has_data(snap):
    """Un instantané sans aucune mesure n'est ni ajouté à la série ni écrit."""
    return (snap.get("coverage_pct") is not None
            or isinstance(snap.get("vulns"), dict)
            or snap.get("tests") is not None)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".", help="racine du projet (défaut : répertoire courant)")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)

    project_data, docs_data, snap = build(root)

    paths = resolve_paths(load_yaml_file(os.path.join(root, "sdlc.config.yaml")))
    out_dir = os.path.join(root, _p(paths, "suivi"))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "project-data.json"), "w", encoding="utf-8") as fh:
        json.dump(project_data, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "docs-data.json"), "w", encoding="utf-8") as fh:
        json.dump(docs_data, fh, ensure_ascii=False, indent=2)

    metrics_dir = os.path.join(root, _p(paths, "metrics"))
    os.makedirs(metrics_dir, exist_ok=True)
    history_path = os.path.join(metrics_dir, "history.jsonl")
    history = read_history(root, paths)
    if snapshot_has_data(snap) and not snapshot_is_duplicate(history, snap):
        with open(history_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(snap, ensure_ascii=False) + "\n")
    for w in docs_data.get("warnings", []):
        print("avertissement : " + w, file=sys.stderr)
    print("docs/suivi/project-data.json et docs/suivi/docs-data.json écrits (%d features, %d documents)"
          % (len(project_data["features"]), len(docs_data.get("files", {}))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
