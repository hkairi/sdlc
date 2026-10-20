#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_thresholds.py — calcule la couverture globale et compte les vulnérabilités SARIF.

Appelé par `scripts/ci.sh` à la fin des contrôles. Aucune dépendance externe
(bibliothèque standard Python 3 uniquement).

Entrées
-------
--coverage-dir   Dossier des rapports de couverture. Formats reconnus (par
                 ordre de priorité documenté) :
                   1. Cobertura XML   (élément racine <coverage>, attribut line-rate)
                   2. JaCoCo XML      (élément racine <report>, compteur LINE)
                   3. lcov            (fichiers *.info / *.lcov, lignes LF: et LH:)
                   4. coverage.py JSON (clé totals.percent_covered)
                 Si plusieurs formats coexistent, le premier de cette liste gagne.
--sarif-dir      Dossier des fichiers SARIF 2.1.0 (analyse de code, dépendances,
                 conteneurs, secrets).
--coverage-min   Seuil minimal de couverture, en pourcentage (défaut 0).
--block-on       Sévérités bloquantes, séparées par des virgules.
                 Valeurs : critique, haute, moyenne, faible (synonyme de basse).
                 Les valeurs inconnues sont ignorées.
--json-out       Chemin d'un fichier où écrire le résultat détaillé (optionnel).

Mapping des sévérités (documenté)
---------------------------------
- Si le résultat SARIF (ou sa règle) porte une propriété `security-severity`
  (nombre 0–10), la sévérité en découle :
      >= 9,0  -> critique
      >= 7,0  -> haute
      >= 4,0  -> moyenne
      <  4,0  -> basse
- Sinon, on retombe sur le niveau SARIF `level` (mapping identique à GitHub) :
      error   -> haute
      warning -> moyenne
      note    -> basse
      none / absent -> basse

Rattachement d'un fichier SARIF à un contrôle (pour le blocage par contrôle) :
- nom contenant « semgrep » ou « sast » ......... sast
- nom contenant « gitleaks » ou « secret » ...... secrets
- nom contenant « trivy », « osv », « grype »,
  « dependency », « deps » ou « snyk » ........... deps
- tout autre fichier ............................ sast

Sorties
-------
- stdout : lignes `clé=valeur` (machine), consommées par `scripts/ci.sh`.
- stderr : résumé lisible.
- code de sortie : 0 si rien ne bloque, 1 si un seuil est franchi, 2 sur erreur.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SEVERITIES = ("critique", "haute", "moyenne", "basse")
SECURITY_CONTROLS = ("sast", "deps", "secrets")

# Niveaux SARIF -> sévérité (fallback quand security-severity est absente).
LEVEL_TO_SEVERITY = {
    "error": "haute",
    "warning": "moyenne",
    "note": "basse",
    "none": "basse",
}

# Synonymes acceptés dans `--block-on` (la config utilise « faible »).
SEVERITY_SYNONYMS = {
    "faible": "basse",
    "basse": "basse",
    "low": "basse",
    "critique": "critique",
    "critical": "critique",
    "haute": "haute",
    "high": "haute",
    "moyenne": "moyenne",
    "medium": "moyenne",
}


# --------------------------------------------------------------------------
# Couverture
# --------------------------------------------------------------------------
def _xml_root_tag(path: Path) -> str | None:
    """Renvoie le nom local de l'élément racine d'un fichier XML, ou None."""
    try:
        for _event, elem in ET.iterparse(str(path), events=("start",)):
            return elem.tag.split("}")[-1].lower()
    except Exception:
        return None
    return None


def parse_cobertura(path) -> float | None:
    """Cobertura XML : attribut line-rate (0–1) de l'élément racine."""
    root = ET.parse(str(path)).getroot()
    rate = root.get("line-rate")
    if rate is None:
        return None
    return 100.0 * float(rate)


def parse_jacoco(path) -> float | None:
    """JaCoCo XML : compteur LINE de premier niveau (covered / (covered + missed))."""
    root = ET.parse(str(path)).getroot()
    for child in list(root):
        tag = child.tag.split("}")[-1].lower()
        if tag == "counter" and child.get("type") == "LINE":
            covered = int(child.get("covered", "0"))
            missed = int(child.get("missed", "0"))
            total = covered + missed
            if total == 0:
                return None
            return 100.0 * covered / total
    return None


def parse_lcov(path) -> float | None:
    """lcov : somme des lignes LF: (found) et LH: (hit)."""
    total_found = 0
    total_hit = 0
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith("LF:"):
            total_found += int(line[3:].strip() or 0)
        elif line.startswith("LH:"):
            total_hit += int(line[3:].strip() or 0)
    if total_found == 0:
        return None
    return 100.0 * total_hit / total_found


def _looks_like_coverage_json(path: Path) -> bool:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    if "percent_covered" in data:
        return True
    totals = data.get("totals")
    return isinstance(totals, dict) and "percent_covered" in totals


def parse_coverage_json(path) -> float | None:
    """coverage.py JSON : totals.percent_covered (ou percent_covered racine)."""
    data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    totals = data.get("totals", data)
    for key in ("percent_covered", "percent_covered_display"):
        value = totals.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def find_coverage(directory) -> tuple[float | None, Path | None]:
    """Cherche le meilleur rapport de couverture dans un dossier (récursif).

    Priorité : Cobertura > JaCoCo > lcov > coverage.py JSON.
    """
    base = Path(directory)
    if not base.is_dir():
        return None, None

    cobertura: list[Path] = []
    jacoco: list[Path] = []
    lcov: list[Path] = []
    covjson: list[Path] = []

    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        name = path.name.lower()
        suffix = path.suffix.lower()
        if suffix == ".xml":
            tag = _xml_root_tag(path)
            if tag == "coverage":
                cobertura.append(path)
            elif tag == "report":
                jacoco.append(path)
        elif name.endswith(".info") or name.endswith(".lcov"):
            lcov.append(path)
        elif suffix == ".json" and _looks_like_coverage_json(path):
            covjson.append(path)

    groups = (
        (cobertura, parse_cobertura),
        (jacoco, parse_jacoco),
        (lcov, parse_lcov),
        (covjson, parse_coverage_json),
    )
    for group, parser in groups:
        for path in group:
            try:
                pct = parser(path)
            except Exception:
                pct = None
            if pct is not None:
                return pct, path
    return None, None


# --------------------------------------------------------------------------
# SARIF
# --------------------------------------------------------------------------
def _security_severity(result: dict, rule: dict | None) -> float | None:
    for candidate in (result.get("properties"), (rule or {}).get("properties")):
        if isinstance(candidate, dict):
            raw = candidate.get("security-severity")
            if raw is not None:
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    return None
    return None


def _severity_from_score(score: float) -> str:
    if score >= 9.0:
        return "critique"
    if score >= 7.0:
        return "haute"
    if score >= 4.0:
        return "moyenne"
    return "basse"


def _rule_for(result: dict, rules: list[dict]) -> dict | None:
    index = result.get("ruleIndex")
    if isinstance(index, int) and 0 <= index < len(rules):
        return rules[index]
    rule_id = result.get("ruleId")
    if rule_id:
        for rule in rules:
            if rule.get("id") == rule_id:
                return rule
    return None


def classify_result(result: dict, rules: list[dict]) -> str:
    """Renvoie la sévérité normalisée d'un résultat SARIF."""
    rule = _rule_for(result, rules)
    score = _security_severity(result, rule)
    if score is not None:
        return _severity_from_score(score)
    level = result.get("level")
    if not level and rule:
        default = rule.get("defaultConfiguration")
        if isinstance(default, dict):
            level = default.get("level")
    return LEVEL_TO_SEVERITY.get(str(level or "").lower(), "moyenne")


def parse_sarif(path) -> dict[str, int]:
    """Compte les résultats d'un fichier SARIF par sévérité normalisée."""
    counts = {severity: 0 for severity in SEVERITIES}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return counts
    for run in data.get("runs", []) or []:
        driver = (run.get("tool") or {}).get("driver") or {}
        rules = driver.get("rules") or []
        if not isinstance(rules, list):
            rules = []
        for result in run.get("results", []) or []:
            if not isinstance(result, dict):
                continue
            counts[classify_result(result, rules)] += 1
    return counts


def control_for_sarif(name: str) -> str:
    """Rattache un fichier SARIF à un contrôle (sast, deps, secrets)."""
    low = name.lower()
    if "gitleaks" in low or "secret" in low:
        return "secrets"
    if any(token in low for token in ("trivy", "osv", "grype", "dependency", "deps", "snyk")):
        return "deps"
    if "semgrep" in low or "sast" in low:
        return "sast"
    return "sast"


def collect_vulns(directory) -> dict[str, dict[str, int]]:
    """Compte les vulnérabilités par contrôle et par sévérité."""
    result = {control: {severity: 0 for severity in SEVERITIES} for control in SECURITY_CONTROLS}
    base = Path(directory)
    if not base.is_dir():
        return result
    for path in sorted(base.rglob("*.sarif")):
        counts = parse_sarif(path)
        control = control_for_sarif(path.name)
        for severity, number in counts.items():
            result[control][severity] += number
    return result


# --------------------------------------------------------------------------
# Seuils
# --------------------------------------------------------------------------
def normalize_block_on(raw: str) -> set[str]:
    """Normalise une liste de sévérités ; « faible » devient « basse ».

    Les sévérités peuvent être séparées par des virgules, des points-virgules
    ou des espaces (la config YAML et ci.sh produisent les deux formes).
    """
    out: set[str] = set()
    normalized = str(raw).replace(",", " ").replace(";", " ")
    for item in normalized.split():
        mapped = SEVERITY_SYNONYMS.get(item.strip().lower())
        if mapped:
            out.add(mapped)
    return out


def fmt_number(value: float | None) -> str:
    if value is None:
        return "null"
    rounded = round(float(value), 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return str(rounded)


def read_reports_dir(config_path: str) -> str:
    """Lit `paths.reports` dans sdlc.config.yaml (défaut « reports »)."""
    try:
        text = Path(config_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "reports"
    match = re.search(r"^\s*reports\s*:\s*[\"']?([^\"'\n#]+)", text, re.MULTILINE)
    return match.group(1).strip() if match else "reports"


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------
def build_report(coverage_dir: str, sarif_dir: str, coverage_min: float, block_on_raw: str) -> dict:
    coverage_pct, coverage_source = find_coverage(coverage_dir) if coverage_dir else (None, None)
    vulns_by_control = (
        collect_vulns(sarif_dir)
        if sarif_dir
        else {control: {severity: 0 for severity in SEVERITIES} for control in SECURITY_CONTROLS}
    )

    aggregate = {
        severity: sum(vulns_by_control[control][severity] for control in SECURITY_CONTROLS)
        for severity in SEVERITIES
    }

    block_on = normalize_block_on(block_on_raw)
    control_blocking = {
        control: any(vulns_by_control[control][severity] > 0 for severity in block_on)
        for control in SECURITY_CONTROLS
    }

    coverage_measured = coverage_pct is not None
    coverage_ok = coverage_measured and coverage_pct >= coverage_min
    coverage_blocking = coverage_measured and not coverage_ok
    thresholds_blocking = coverage_blocking or any(control_blocking.values())

    return {
        "coverage_pct": coverage_pct,
        "coverage_source": str(coverage_source) if coverage_source else None,
        "coverage_measured": coverage_measured,
        "coverage_ok": coverage_ok,
        "coverage_min": coverage_min,
        "block_on": sorted(block_on),
        "vulns": aggregate,
        "vulns_by_control": vulns_by_control,
        "control_blocking": control_blocking,
        "thresholds_blocking": thresholds_blocking,
    }


def render_machine(report: dict) -> str:
    lines = [
        f"coverage_pct={fmt_number(report['coverage_pct'])}",
        f"coverage_source={report['coverage_source'] or 'null'}",
        f"coverage_measured={str(report['coverage_measured']).lower()}",
        f"coverage_ok={str(report['coverage_ok']).lower()}",
    ]
    for severity in SEVERITIES:
        lines.append(f"vulns_{severity}={report['vulns'][severity]}")
    for control in SECURITY_CONTROLS:
        lines.append(f"control_{control}_blocking={str(report['control_blocking'][control]).lower()}")
    lines.append(f"thresholds_blocking={str(report['thresholds_blocking']).lower()}")
    return "\n".join(lines)


def render_human(report: dict) -> str:
    lines = ["=== Seuils de qualité ==="]
    if report["coverage_measured"]:
        verdict = "OK" if report["coverage_ok"] else "SOUS LE SEUIL"
        lines.append(
            f"Couverture : {fmt_number(report['coverage_pct'])} % "
            f"(minimum {fmt_number(report['coverage_min'])} %) -> {verdict}"
        )
        lines.append(f"  Source : {report['coverage_source']}")
    else:
        lines.append("Couverture : non mesurée (aucun rapport trouvé)")
    vulns = report["vulns"]
    lines.append(
        "Vulnérabilités : "
        f"critique={vulns['critique']} haute={vulns['haute']} "
        f"moyenne={vulns['moyenne']} basse={vulns['basse']}"
    )
    block_on = ", ".join(report["block_on"]) or "(aucune)"
    lines.append(f"  Sévérités bloquantes : {block_on}")
    for control in SECURITY_CONTROLS:
        state = "BLOQUANT" if report["control_blocking"][control] else "ok"
        lines.append(f"  Contrôle {control} : {state}")
    lines.append(
        "Verdict seuils : " + ("BLOQUANT" if report["thresholds_blocking"] else "ok")
    )
    return "\n".join(lines)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if any(item in ("-h", "--help") for item in args):
        print(__doc__)
        return 0

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--coverage-dir", default="")
    parser.add_argument("--sarif-dir", default="")
    parser.add_argument("--coverage-min", type=float, default=0.0)
    parser.add_argument("--block-on", default="")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--config", default="", help="sdlc.config.yaml : dossiers par défaut via paths.reports")
    try:
        options, extra = parser.parse_known_args(args)
    except SystemExit:
        return 2

    if extra:
        # Aucun argument positionnel n'est attendu : on le signale sans échouer.
        print(f"avertissement : arguments ignorés : {' '.join(extra)}", file=sys.stderr)
    if options.coverage_min < 0:
        print("erreur : --coverage-min doit être >= 0", file=sys.stderr)
        return 2

    coverage_dir = options.coverage_dir
    sarif_dir = options.sarif_dir
    if options.config and (not coverage_dir or not sarif_dir):
        reports = read_reports_dir(options.config)
        coverage_dir = coverage_dir or str(Path(reports) / "coverage")
        sarif_dir = sarif_dir or str(Path(reports) / "security")

    report = build_report(
        coverage_dir,
        sarif_dir,
        options.coverage_min,
        options.block_on,
    )

    print(render_machine(report))
    print(render_human(report), file=sys.stderr)

    if options.json_out:
        try:
            out = Path(options.json_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:  # pragma: no cover - erreur d'écriture disque
            print(f"avertissement : écriture de {options.json_out} impossible : {exc}", file=sys.stderr)

    return 1 if report["thresholds_blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
