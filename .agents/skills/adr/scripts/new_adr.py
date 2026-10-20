#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new_adr.py — crée un ADR numéroté et met à jour l'index.

Numérotation : le plus grand `ADR-NNN` présent dans `docs/architecture/adr/` + 1
(démarre à 001). Le fichier est créé depuis `.sdlc/templates/docs/adr.md` ; l'index
`docs/architecture/adr/README.md` est créé depuis `.sdlc/templates/docs/adr-index.md`
s'il n'existe pas, puis complété avec la nouvelle ligne (ou mise à jour si l'ADR
existe déjà).

Usage
-----
    new_adr.py [RACINE] --titre "Titre de la décision" [options]

    RACINE            racine du projet (défaut : répertoire courant).
    --titre, -t       titre concis de la décision (obligatoire).
    --statut, -s      proposé | accepté | rejeté | déprécié | remplacé (défaut : proposé).
    --date, -d        date ISO (AAAA-MM-JJ) ; défaut : aujourd'hui.
    --templates       dossier `.sdlc/templates/docs` (détecté par défaut).
    --dry-run         affiche les actions sans écrire.
    --help            cette aide.

Code de sortie : 0 succès, 2 erreur d'usage ou d'entrée.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

STATUTS = ("proposé", "accepté", "rejeté", "déprécié", "remplacé")
ADR_RE = re.compile(r"ADR-(\d{1,4})", re.IGNORECASE)


def _read_path(root: Path, key: str, default: str) -> str:
    """Lit `paths.<key>` dans `sdlc.config.yaml` (défaut si absent).

    Lecture minimale et tolérante (pas de dépendance à PyYAML) : la clé du bloc
    `paths` est recherchée à n'importe quelle indentation.
    """
    config = root / "sdlc.config.yaml"
    if not config.is_file():
        return default
    text = config.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^\s*" + re.escape(key) + r"\s*:\s*[\"']?([^\"'\n#]+)", text, re.MULTILINE)
    return match.group(1).strip() if match else default


def default_templates(root: Path):
    base = _read_path(root, "templates", ".sdlc/templates")
    candidates = [
        root / base / "docs",
        # Repli pour le dépôt du framework lui-même (utilisé sur lui-même).
        Path(__file__).resolve().parents[4] / "templates" / "docs",
    ]
    for candidate in candidates:
        if (candidate / "adr.md").is_file():
            return candidate
    return None


def _project_name(root: Path) -> str:
    config = root / "sdlc.config.yaml"
    if config.is_file():
        text = config.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^\s*name:\s*[\"']?([^\"'\n#]+)", text, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return root.name


def next_number(adr_dir: Path) -> int:
    highest = 0
    if adr_dir.is_dir():
        for path in adr_dir.iterdir():
            for match in ADR_RE.finditer(path.stem):
                highest = max(highest, int(match.group(1)))
    return highest + 1


def parse_rows(text: str):
    """Récupère les lignes de tableau d'ADR : {numéro: (titre, statut, date)}."""
    rows = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        match = re.fullmatch(r"ADR-(\d{1,4})", cells[0], re.IGNORECASE)
        if not match:
            continue
        if any("{{" in cell for cell in cells):
            continue
        number = match.group(1)
        titre = cells[1] if len(cells) > 1 else ""
        statut = cells[2] if len(cells) > 2 else ""
        date = cells[3] if len(cells) > 3 else ""
        rows[number] = (titre, statut, date)
    return rows


def render_table(rows) -> str:
    lines = [
        "| Numéro | Titre | Statut | Date d'acceptation |",
        "|---|---|---|---|",
    ]
    for number in sorted(rows, key=lambda n: int(n)):
        titre, statut, date = rows[number]
        lines.append(f"| ADR-{number} | {titre} | {statut} | {date} |")
    return "\n".join(lines)


def replace_table(text: str, table: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.lstrip().startswith("|") and "Numéro" in line:
            start = index
            break
    if start is None:
        # Pas de tableau : insérer après le premier titre.
        out = []
        inserted = False
        for line in lines:
            out.append(line)
            if not inserted and line.startswith("#"):
                out.append("")
                out.append(table)
                inserted = True
        if not inserted:
            out = [table] + lines
        return "\n".join(out).rstrip() + "\n"

    end = start
    while end < len(lines) and lines[end].lstrip().startswith("|"):
        end += 1
    new_lines = lines[:start] + table.splitlines() + lines[end:]
    return "\n".join(new_lines).rstrip() + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="new_adr.py",
        description="Crée un ADR numéroté et met à jour l'index des ADR.",
    )
    parser.add_argument("root", nargs="?", default=".", help="racine du projet (défaut : .)")
    parser.add_argument("--titre", "-t", required=True, help="titre de la décision")
    parser.add_argument("--statut", "-s", default="proposé", choices=STATUTS, help="statut de l'ADR")
    parser.add_argument("--date", "-d", default=None, help="date ISO AAAA-MM-JJ (défaut : aujourd'hui)")
    parser.add_argument("--templates", default=None, help="dossier .sdlc/templates/docs")
    parser.add_argument("--dry-run", action="store_true", help="affiche sans écrire")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"erreur : racine introuvable : {root}", file=sys.stderr)
        return 2

    templates = Path(args.templates).expanduser().resolve() if args.templates else default_templates(root)
    if not templates or not (templates / "adr.md").is_file():
        print("erreur : gabarit .sdlc/templates/docs/adr.md introuvable ; utiliser --templates", file=sys.stderr)
        return 2

    date = args.date or _dt.date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        print(f"erreur : date invalide : {date} (attendu AAAA-MM-JJ)", file=sys.stderr)
        return 2

    adr_dir = root / _read_path(root, "adr", "docs/architecture/adr")
    number = next_number(adr_dir)
    number_str = f"{number:03d}"
    adr_path = adr_dir / f"ADR-{number_str}.md"
    index_path = adr_dir / "README.md"

    # --- Rendu de l'ADR -----------------------------------------------------
    template = (templates / "adr.md").read_text(encoding="utf-8")
    content = (
        template.replace("{{numéro}}", number_str)
        .replace("{{titre-de-la-décision}}", args.titre)
        .replace("{{statut}}", args.statut)
        .replace("{{date-proposition}}", date)
        .replace("{{date-acceptation}}", date if args.statut == "accepté" else "")
    )

    # --- Rendu de l'index ---------------------------------------------------
    if index_path.is_file():
        index_text = index_path.read_text(encoding="utf-8")
    else:
        index_text = (templates / "adr-index.md").read_text(encoding="utf-8")
        index_text = index_text.replace("{{nom-du-projet}}", _project_name(root))
    rows = parse_rows(index_text)
    rows[number_str] = (args.titre, args.statut, date)
    index_text = replace_table(index_text, render_table(rows))

    actions = []
    if adr_path.exists():
        actions.append(("ignoré", adr_path, "existe déjà"))
    else:
        if not args.dry_run:
            adr_dir.mkdir(parents=True, exist_ok=True)
            adr_path.write_text(content, encoding="utf-8")
        actions.append(("créé", adr_path, ""))
    if not args.dry_run:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(index_text, encoding="utf-8")
    actions.append(("mis à jour", index_path, ""))

    prefix = "[simulation] " if args.dry_run else ""
    for status, path, note in actions:
        suffix = f" — {note}" if note else ""
        print(f"{prefix}[{status}] {path.relative_to(root)}{suffix}")
    print(f"{prefix}ADR-{number_str} : {args.titre} ({args.statut}, {date})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
