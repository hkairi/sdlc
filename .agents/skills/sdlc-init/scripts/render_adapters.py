#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_adapters.py — génère les adaptateurs des outils d'agents retenus.

Copie, depuis `.sdlc/templates/adapters/<outil>/`, les fichiers des **seuls outils activés**
dans `sdlc.config.yaml`, vers leur emplacement dans le projet (voir les `README.md`
de chaque adaptateur), remplace les marqueurs `{{…}}` par les valeurs de la config,
et affiche ce qui a été écrit.

Lecture de la configuration
---------------------------
`PyYAML` est utilisé s'il est installé. Sinon, un analyseur du **sous-ensemble** de
`sdlc.config.example.yaml` prend le relais (mappings imbriqués par indentation,
listes en ligne `[a, b]`, listes en bloc `- …`, scalaires chaîne/nombre/booléen).
Les commentaires (`#`) sont ignorés.

Fichiers du gabarit
-------------------
Seuls les fichiers listés dans les tables de destination des `README.md` des
adaptateurs sont copiés ; `README.md` et `.gitkeep` sont ignorés.

Fichiers fusionnés (jamais écrasés)
-----------------------------------
`.claude/settings.json` et `opencode.json` sont **fusionnés** avec un fichier
existant : les entrées de l'humain sont conservées, seules les clés manquantes ou
les éléments de liste absents sont ajoutés. Les fichiers ordinaires ne sont jamais
écrasés sans `--force`.

`CLAUDE.md` existant
--------------------
Le gabarit `CLAUDE.md` n'est **jamais recopié tel quel** sur un fichier existant.
Ses consignes propres à Claude Code (sans la directive `@AGENTS.md`, déjà présente
dans la cible) sont insérées dans un **bloc délimité** juste après la ligne
`@AGENTS.md` :

    <!-- sdlc-claude:begin vX.Y.Z -->
    … consignes Claude Code …
    <!-- sdlc-claude:end -->

Le contenu de l'humain est conservé. Un second passage sans changement n'écrit rien.
Si `CLAUDE.md` est absent, il est créé avec `@AGENTS.md` puis le même bloc. La
version `vX.Y.Z` est celle de `.sdlc/VERSION` du projet, sinon celle de `VERSION`
du framework.

Manifeste des adaptateurs
-------------------------
`render_adapters.py` inscrit son travail dans `.sdlc/manifest.json`, section
`adapters` : chaque fichier **créé** (chemin + sha256) et, pour chaque fichier
**fusionné** préexistant, les entrées qu'il a ajoutées (opérations `set_key` et
`append_list`). Le manifeste est écrit de façon **atomique** et sans casser le
format lu par `bin/sdlc_install_lib.py`. Si `.sdlc/manifest.json` est absent, un
manifeste minimal est créé.

Marqueurs remplacés
-------------------
| Marqueur             | Source dans `sdlc.config.yaml`            |
|----------------------|-------------------------------------------|
| `{{nom-du-projet}}`  | `project.name`                            |
| `{{modèle-build}}`   | `agents.<outil>.models.build`             |
| `{{modèle-think}}`   | `agents.<outil>.models.think`             |
| `{{cli-claude}}`     | `agents.claude.cli`                       |
| `{{cli-codex}}`      | `agents.codex.cli`                        |
| `{{cli-opencode}}`   | `agents.opencode.cli`                     |
| `{{commande-ci}}`    | `scripts/ci.sh` (contrôles locaux)        |

Traitements propres à un adaptateur : les autorisations des CLI d'agents **non
retenus** sont retirées de `.claude/settings.json` et de `.codex/rules/sdlc.rules`.

Usage
-----
    render_adapters.py [RACINE] [--config FICHIER] [--templates DOSSIER]
                       [--force] [--dry-run] [--keep-comments] [--help]

    RACINE             racine du projet (défaut : répertoire courant).
    --config           chemin de `sdlc.config.yaml` (défaut : <racine>/sdlc.config.yaml).
    --templates        dossier `.sdlc/templates/adapters` (détecté par défaut).
    --force            écrase un fichier existant (fichiers ordinaires uniquement).
    --dry-run          simule : affiche les actions sans rien écrire.
    --keep-comments    conserve les commentaires de génération des gabarits.

Codes de sortie : 0 succès, 2 erreur d'usage ou d'entrée.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

try:  # PyYAML est optionnel.
    import yaml  # type: ignore
except Exception:  # pragma: no cover - dépend de l'environnement
    yaml = None


TOOLS = ("claude", "codex", "opencode")

# Fichiers du gabarit jamais copiés.
IGNORED_NAMES = {".gitkeep", "README.md", ".DS_Store"}

# Bloc délimité des consignes propres à Claude Code dans CLAUDE.md.
CLAUDE_BLOCK_BEGIN = "<!-- sdlc-claude:begin v{version} -->"
CLAUDE_BLOCK_END = "<!-- sdlc-claude:end -->"
RE_CLAUDE_BLOCK = re.compile(
    r"<!-- sdlc-claude:begin v[^ ]+ -->.*?<!-- sdlc-claude:end -->", re.S)

# Fichiers racine par outil : (chemin template, destination, type).
# type « file » = fichier ordinaire ; « merge » = fusion JSON non destructive ;
# « claude_md » = bloc délimité inséré dans un CLAUDE.md existant.
ROOT_FILES = {
    "claude": [
        ("CLAUDE.md", "CLAUDE.md", "claude_md"),
        ("settings.json", ".claude/settings.json", "merge"),
    ],
    "codex": [
        ("config.toml", ".codex/config.toml", "file"),
        ("rules/sdlc.rules", ".codex/rules/sdlc.rules", "file"),
    ],
    "opencode": [
        ("opencode.json", "opencode.json", "merge"),
    ],
}

# Sous-dossiers par outil : (dossier template, dossier destination).
SUB_DIRS = {
    "claude": [("agents", ".claude/agents"), ("commands", ".claude/commands")],
    "codex": [("agents", ".codex/agents")],
    "opencode": [("agent", ".opencode/agent"), ("command", ".opencode/command"),
                 ("plugins", ".opencode/plugins")],
}

# Bloc de commentaire de génération à retirer des fichiers Markdown.
HTML_COMMENT_RE = re.compile(r"(?s)<!--.*?-->")
# Lignes de commentaire de génération à retirer des fichiers non Markdown.
GENERATOR_HINTS = ("sdlc-init", "Remplacer les marqueurs", "Copié vers")


# ---------------------------------------------------------------------------
# Chargement de la configuration
# ---------------------------------------------------------------------------
def _strip_comment(line: str) -> str:
    """Retire un commentaire `#` hors guillemets et hors chaîne entre apostrophes."""
    out = []
    in_single = False
    in_double = False
    prev = ""
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if ch == "#" and not in_single and not in_double and (prev == "" or prev in " \t"):
            break
        out.append(ch)
        prev = ch
    return "".join(out).rstrip()


def _split_key(content: str):
    """Coupe `clé: valeur` au premier `:` de premier niveau. Renvoie (clé, sep, reste)."""
    depth = 0
    in_single = False
    in_double = False
    for index, ch in enumerate(content):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            elif ch == ":" and depth == 0:
                if index + 1 == len(content) or content[index + 1] in " \t":
                    return content[:index], ":", content[index + 1 :]
    return content, "", ""


def _split_flow(inner: str):
    """Découpe une liste/mapping en ligne sur les virgules de premier niveau."""
    parts = []
    depth = 0
    current = []
    in_single = False
    in_double = False
    for ch in inner:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if not in_single and not in_double:
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
                continue
        current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_flow_list(text: str):
    inner = text.strip()[1:-1].strip()
    if not inner:
        return []
    return [_parse_scalar(part) for part in _split_flow(inner)]


def _parse_flow_map(text: str):
    inner = text.strip()[1:-1].strip()
    result = {}
    if not inner:
        return result
    for part in _split_flow(inner):
        key, sep, value = _split_key(part)
        if sep:
            result[_parse_key(key)] = _parse_scalar(value)
    return result


def _parse_key(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def _parse_scalar(text: str):
    text = text.strip()
    if text == "":
        return None
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(text) >= 2 and text[0] == "'" and text[-1] == "'":
        return text[1:-1].replace("''", "'")
    low = text.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"[-+]?\d+", text):
        return int(text)
    if re.fullmatch(r"[-+]?\d+\.\d+", text):
        return float(text)
    if text.startswith("[") and text.endswith("]"):
        return _parse_flow_list(text)
    if text.startswith("{") and text.endswith("}"):
        return _parse_flow_map(text)
    return text


def _parse_map(lines, i, indent):
    result = {}
    while i < len(lines):
        ind, content = lines[i]
        if ind < indent:
            break
        if ind > indent or content.startswith("- "):
            break
        key, sep, rest = _split_key(content)
        if not sep:
            i += 1
            continue
        key = _parse_key(key)
        rest = rest.strip()
        if rest:
            result[key] = _parse_scalar(rest)
            i += 1
        else:
            i += 1
            if i < len(lines) and lines[i][0] > indent:
                result[key], i = _parse_block(lines, i, lines[i][0])
            else:
                result[key] = None
    return result, i


def _parse_list(lines, i, indent):
    result = []
    while i < len(lines):
        ind, content = lines[i]
        if ind != indent or not content.startswith("- "):
            break
        rest = content[2:].strip()
        if rest == "":
            i += 1
            if i < len(lines) and lines[i][0] > indent:
                child, i = _parse_block(lines, i, lines[i][0])
                result.append(child)
            else:
                result.append(None)
        elif rest.startswith("{"):
            result.append(_parse_flow_map(rest))
            i += 1
        elif rest.startswith("["):
            result.append(_parse_flow_list(rest))
            i += 1
        elif _split_key(rest)[1] == ":":
            virtual = [(indent + 2, rest)]
            j = i + 1
            while j < len(lines) and lines[j][0] > indent:
                virtual.append(lines[j])
                j += 1
            value, _ = _parse_map(virtual, 0, indent + 2)
            result.append(value)
            i = j
        else:
            result.append(_parse_scalar(rest))
            i += 1
    return result, i


def _parse_block(lines, i, indent):
    if i >= len(lines):
        return None, i
    if lines[i][1].startswith("- "):
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def parse_subset(text: str) -> dict:
    """Analyse le sous-ensemble YAML utilisé par `sdlc.config.example.yaml`."""
    logical = []
    for line in text.splitlines():
        stripped = _strip_comment(line)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        logical.append((indent, stripped.strip()))
    if not logical:
        return {}
    value, _ = _parse_block(logical, 0, logical[0][0])
    return value if isinstance(value, dict) else {}


def load_config(path: Path):
    """Renvoie (config, moteur) où moteur vaut « pyyaml » ou « fallback »."""
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data, "pyyaml"
        raise ValueError("le fichier de configuration ne contient pas de mapping YAML")
    return parse_subset(text), "fallback"


# ---------------------------------------------------------------------------
# Marqueurs et transformations
# ---------------------------------------------------------------------------
def _dig(mapping, *keys):
    current = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def markers_for(config: dict, tool: str) -> dict:
    agents = config.get("agents") or {}
    return {
        "{{nom-du-projet}}": _dig(config, "project", "name") or "",
        "{{modèle-build}}": _dig(agents, tool, "models", "build"),
        "{{modèle-think}}": _dig(agents, tool, "models", "think"),
        "{{cli-claude}}": _dig(agents, "claude", "cli"),
        "{{cli-codex}}": _dig(agents, "codex", "cli"),
        "{{cli-opencode}}": _dig(agents, "opencode", "cli"),
        "{{commande-ci}}": "scripts/ci.sh",
    }


def substitute(text: str, markers: dict):
    """Remplace les marqueurs connus. Renvoie (texte, liste de marqueurs non résolus)."""
    unresolved = []
    for marker, value in markers.items():
        if marker not in text:
            continue
        if value is None:
            unresolved.append(marker)
            continue
        text = text.replace(marker, str(value))
    return text, unresolved


def strip_generator_comments(text: str, suffix: str) -> str:
    """Retire les commentaires de consigne laissés par les gabarits."""
    if suffix == ".md":
        return HTML_COMMENT_RE.sub(
            lambda m: "" if "sdlc-init" in m.group(0) else m.group(0), text
        )
    lines = text.splitlines(keepends=True)
    kept = []
    for line in lines:
        if line.lstrip().startswith("#") and any(h in line for h in GENERATOR_HINTS):
            continue
        kept.append(line)
    return "".join(kept)


def filter_claude_settings(text: str, enabled: dict) -> str:
    """Retire les autorisations de CLI des agents non retenus."""
    lines = text.splitlines(keepends=True)
    kept = []
    for line in lines:
        marker = next((f"{{{{cli-{t}}}}}" for t in TOOLS if f"{{{{cli-{t}}}}}" in line), None)
        if marker:
            tool = marker[len("{{cli-") : -2]
            if not enabled.get(tool):
                continue
        kept.append(line)
    return "".join(kept)


_CODEX_BLOCK_RE = re.compile(
    r"(?m)^# prefix_rule\(\n(?:^#[^\n]*\n)*?^# \)\n"
)


def filter_codex_rules(text: str, enabled: dict) -> str:
    """Décommente les règles des agents retenus, supprime celles des autres."""

    def replace(match: re.Match) -> str:
        block = match.group(0)
        marker = next(
            (f"{{{{cli-{t}}}}}" for t in TOOLS if f"{{{{cli-{t}}}}}" in block),
            "{{commande-ci}}" if "{{commande-ci}}" in block else None,
        )
        if marker is None:
            return block
        if marker == "{{commande-ci}}":
            keep = True
        else:
            tool = marker[len("{{cli-") : -2]
            keep = bool(enabled.get(tool))
        if not keep:
            return ""
        # Décommente : retire le préfixe « # » (et un espace s'il suit).
        return "".join(re.sub(r"^# ?", "", line) for line in block.splitlines(keepends=True))

    return _CODEX_BLOCK_RE.sub(replace, text)


# ---------------------------------------------------------------------------
# Fusion JSON
# ---------------------------------------------------------------------------
def deep_merge(existing, template):
    """Fusionne `template` dans `existing` : l'existant (humain) est prioritaire."""
    if isinstance(existing, dict) and isinstance(template, dict):
        merged = dict(existing)
        for key, value in template.items():
            if key in merged:
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    if isinstance(existing, list) and isinstance(template, list):
        merged = list(existing)
        for item in template:
            if item not in merged:
                merged.append(item)
        return merged
    return existing


def collect_additions(existing, template, path=None, out=None):
    """Opérations décrivant ce que `template` ajoute à `existing`.

    Deux opérations seulement, réversibles sans ambiguïté :

    - ``set_key`` : une clé absente de l'existant est ajoutée avec sa valeur
      (sous-arbre entier, sans descente) ;
    - ``append_list`` : des éléments absents sont ajoutés à une liste existante.

    Les valeurs de l'humain sont prioritaires : une clé déjà présente, une liste
    existante ou un scalaire existant ne produisent aucune opération.
    """
    path = list(path or [])
    out = out if out is not None else []
    if isinstance(existing, dict) and isinstance(template, dict):
        for key, value in template.items():
            if key not in existing:
                out.append({"op": "set_key", "path": path + [key], "value": value})
            else:
                collect_additions(existing[key], value, path + [key], out)
    elif isinstance(existing, list) and isinstance(template, list):
        items = [item for item in template if item not in existing]
        if items:
            out.append({"op": "append_list", "path": path, "items": items})
    return out


def union_ops(previous, current):
    """Concatène deux listes d'opérations en écartant les doublons (op + chemin)."""
    out = list(previous or [])
    seen = {(op.get("op"), tuple(op.get("path") or []))
            for op in out if isinstance(op, dict)}
    for op in current or []:
        key = (op.get("op"), tuple(op.get("path") or []))
        if key not in seen:
            out.append(op)
            seen.add(key)
    return out


# ---------------------------------------------------------------------------
# Version et bloc `sdlc-claude`
# ---------------------------------------------------------------------------
def resolve_version(root: Path) -> str:
    """Version : `.sdlc/VERSION` du projet, sinon `VERSION` du framework."""
    candidates = [
        root / ".sdlc" / "VERSION",
        Path(__file__).resolve().parents[4] / "VERSION",
    ]
    for candidate in candidates:
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return "0.0.0"


def claude_block(version: str, body: str) -> str:
    """Bloc délimité des consignes propres à Claude Code."""
    return "{}\n{}\n{}".format(
        CLAUDE_BLOCK_BEGIN.format(version=version), body, CLAUDE_BLOCK_END)


def claude_block_body(text: str) -> str:
    """Corps du bloc : le gabarit sans `@AGENTS.md` ni les blancs de bord."""
    text = re.sub(r"(?m)^@AGENTS\.md[ \t]*\n?", "", text, count=1)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("\n")


def insert_claude_block(content: str, block: str) -> str:
    """Insère le bloc juste après `@AGENTS.md` (ou en tête si elle manque)."""
    match = re.search(r"(?m)^@AGENTS\.md[ \t]*(?:\n|$)", content)
    if match is None:
        rest = content.lstrip("\n")
        out = "@AGENTS.md\n\n" + block + "\n"
        return out + ("\n" + rest if rest else "")
    before = content[: match.start()]
    after = content[match.end():].lstrip("\n")
    out = before + "@AGENTS.md\n\n" + block + "\n"
    if after:
        out += "\n" + after
    return out


# ---------------------------------------------------------------------------
# Manifeste `.sdlc/manifest.json`
# ---------------------------------------------------------------------------
def load_manifest(path: Path) -> dict:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
    return {}


def update_manifest(path: Path, manifest: dict, version: str, record: dict) -> None:
    """Inscrit la section `adapters` puis écrit le manifeste de façon atomique."""
    adapters = {"version": version}
    files = dict(record.get("files") or {})
    if files:
        adapters["files"] = dict(sorted(files.items()))
    merged = {rel: ops for rel, ops in (record.get("merged") or {}).items() if ops}
    if merged:
        adapters["merged"] = dict(sorted(merged.items()))
    if record.get("claude_md_block"):
        adapters["claude_md_block"] = True
    manifest["adapters"] = adapters

    text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            if path.read_text(encoding="utf-8") == text:
                return
        except OSError:
            pass
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------
def default_templates(root: Path, config: dict | None = None):
    """Dossier des gabarits d'adaptateurs : `paths.templates`/adapters (défaut `.sdlc/templates`)."""
    paths = (config or {}).get("paths") or {}
    base = paths.get("templates") or ".sdlc/templates"
    candidates = [
        root / base / "adapters",
        # Repli pour le dépôt du framework lui-même (utilisé sur lui-même).
        Path(__file__).resolve().parents[4] / "templates" / "adapters",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


class Reporter:
    def __init__(self, dry_run: bool):
        self.dry_run = dry_run
        self.actions = []
        self.warnings = []

    def add(self, status: str, path: str, note: str = ""):
        self.actions.append((status, path, note))

    def warn(self, message: str):
        self.warnings.append(message)

    def flush(self):
        prefix = "[simulation] " if self.dry_run else ""
        for status, path, note in self.actions:
            suffix = f" — {note}" if note else ""
            print(f"{prefix}[{status}] {path}{suffix}")
        for message in self.warnings:
            print(f"avertissement : {message}", file=sys.stderr)
        written = sum(1 for status, _, _ in self.actions
                      if status in {"créé", "fusionné", "écrasé",
                                    "bloc inséré", "bloc remplacé"})
        skipped = sum(1 for status, _, _ in self.actions if status == "ignoré")
        verb = "à écrire" if self.dry_run else "écrit(s)"
        print(
            f"{prefix}{written} fichier(s) {verb}, {skipped} ignoré(s)"
            + (f", {len(self.warnings)} avertissement(s)" if self.warnings else "")
        )


def transform(text: str, tool: str, rel: str, enabled: dict, keep_comments: bool, markers: dict):
    if tool == "claude" and rel == "settings.json":
        text = filter_claude_settings(text, enabled)
    if tool == "codex" and rel == "rules/sdlc.rules":
        text = filter_codex_rules(text, enabled)
    if not keep_comments:
        text = strip_generator_comments(text, Path(rel).suffix)
    return substitute(text, markers)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_regular(
    src: Path, dst: Path, tool: str, rel: str, enabled: dict, markers: dict,
    keep_comments: bool, force: bool, reporter: Reporter, root: Path, record: dict,
):
    text, unresolved = transform(src.read_text(encoding="utf-8"), tool, rel, enabled, keep_comments, markers)
    rel_posix = dst.relative_to(root).as_posix()
    for marker in unresolved:
        reporter.warn(f"{rel_posix} : marqueur non résolu {marker}")
    if dst.exists() and not force:
        same = False
        try:
            same = dst.read_text(encoding="utf-8") == text
        except OSError:
            same = False
        reporter.add("ignoré", rel_posix,
                     "déjà à jour" if same else "existe déjà ; --force pour écraser")
        return
    status = "écrasé" if dst.exists() else "créé"
    if not reporter.dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding="utf-8")
    reporter.add(status, rel_posix)
    record["files"][rel_posix] = {"sha256": _sha256_text(text)}


def write_merge(
    src: Path, dst: Path, tool: str, rel: str, enabled: dict, markers: dict,
    keep_comments: bool, force: bool, reporter: Reporter, root: Path, record: dict,
):
    text, unresolved = transform(src.read_text(encoding="utf-8"), tool, rel, enabled, keep_comments, markers)
    rel_posix = dst.relative_to(root).as_posix()
    for marker in unresolved:
        reporter.warn(f"{rel_posix} : marqueur non résolu {marker}")
    try:
        rendered = json.loads(text)
    except json.JSONDecodeError as exc:
        reporter.warn(f"{rel_posix} : gabarit JSON invalide après substitution : {exc}")
        return
    existing = None
    existing_text = None
    if dst.exists():
        try:
            existing_text = dst.read_text(encoding="utf-8")
            existing = json.loads(existing_text)
        except json.JSONDecodeError:
            if not force:
                reporter.add("ignoré", rel_posix,
                             "JSON existant illisible ; --force pour écraser")
                return
            existing = None
            existing_text = None
    if isinstance(existing, dict):
        merged = deep_merge(existing, rendered)
        content = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
        if existing_text == content:
            reporter.add("ignoré", rel_posix, "déjà fusionné")
        else:
            if not reporter.dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(content, encoding="utf-8")
            reporter.add("fusionné", rel_posix)
        additions = collect_additions(existing, rendered)
        if additions:
            record["merged"][rel_posix] = union_ops(
                record["merged"].get(rel_posix), additions)
    else:
        content = json.dumps(rendered, ensure_ascii=False, indent=2) + "\n"
        if not reporter.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
        reporter.add("écrasé" if dst.exists() else "créé", rel_posix)
        record["files"][rel_posix] = {"sha256": _sha256_text(content)}


def write_claude_md(
    src: Path, dst: Path, tool: str, enabled: dict, markers: dict,
    keep_comments: bool, version: str, reporter: Reporter, root: Path, record: dict,
):
    """Insère (ou remplace) le bloc `sdlc-claude` dans CLAUDE.md sans toucher au reste."""
    text, unresolved = transform(src.read_text(encoding="utf-8"), tool, "CLAUDE.md", enabled, keep_comments, markers)
    rel_posix = dst.relative_to(root).as_posix()
    for marker in unresolved:
        reporter.warn(f"{rel_posix} : marqueur non résolu {marker}")
    block = claude_block(version, claude_block_body(text))

    if dst.exists():
        content = dst.read_text(encoding="utf-8")
        if RE_CLAUDE_BLOCK.search(content):
            new_content = RE_CLAUDE_BLOCK.sub(lambda _m: block, content, count=1)
            action = "bloc remplacé"
            note = f"v{version}"
        else:
            new_content = insert_claude_block(content, block)
            action = "bloc inséré"
            note = "après @AGENTS.md" if "@AGENTS.md" in content else "en tête"
        if new_content == content:
            reporter.add("ignoré", rel_posix, "bloc sdlc-claude déjà à jour")
        else:
            if not reporter.dry_run:
                dst.write_text(new_content, encoding="utf-8")
            reporter.add(action, rel_posix, note)
    else:
        new_content = "@AGENTS.md\n\n" + block + "\n"
        if not reporter.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(new_content, encoding="utf-8")
        reporter.add("créé", rel_posix, "avec @AGENTS.md et le bloc sdlc-claude")
        record["files"][rel_posix] = {"sha256": _sha256_text(new_content)}

    record["claude_md_block"] = True


def render(root: Path, templates: Path, config: dict, force: bool, dry_run: bool,
           keep_comments: bool, reporter: Reporter) -> int:
    agents = config.get("agents") or {}
    enabled = {}
    for tool in TOOLS:
        enabled[tool] = bool(_dig(agents, tool, "enabled"))
    if not any(enabled.values()):
        reporter.warn("aucun agent activé dans la configuration : rien à générer")
        return 2

    version = resolve_version(root)
    manifest_path = root / ".sdlc" / "manifest.json"
    manifest = load_manifest(manifest_path)
    previous = manifest.get("adapters")
    previous = previous if isinstance(previous, dict) else {}
    previous_files = previous.get("files")
    previous_files = previous_files if isinstance(previous_files, dict) else {}
    previous_merged = previous.get("merged")
    previous_merged = previous_merged if isinstance(previous_merged, dict) else {}
    record = {
        # On conserve les empreintes précédentes pour que la désinstallation
        # puisse retirer les fichiers créés lors d'un passage antérieur.
        "files": {rel: sha for rel, sha in previous_files.items()
                  if (root / rel).is_file()},
        "merged": dict(previous_merged),
        "claude_md_block": bool(previous.get("claude_md_block")),
    }

    for tool in TOOLS:
        if not enabled[tool]:
            continue
        template_dir = templates / tool
        if not template_dir.is_dir():
            reporter.warn(f"gabarit introuvable : {template_dir}")
            continue
        markers = markers_for(config, tool)
        for rel, dest_rel, kind in ROOT_FILES[tool]:
            src = template_dir / rel
            if not src.is_file():
                reporter.warn(f"fichier de gabarit manquant : {src}")
                continue
            dst = root / dest_rel
            if kind == "merge":
                write_merge(src, dst, tool, rel, enabled, markers, keep_comments, force, reporter, root, record)
            elif kind == "claude_md":
                write_claude_md(src, dst, tool, enabled, markers, keep_comments, version, reporter, root, record)
            else:
                write_regular(src, dst, tool, rel, enabled, markers, keep_comments, force, reporter, root, record)
        for sub, dest_sub in SUB_DIRS[tool]:
            src_dir = template_dir / sub
            if not src_dir.is_dir():
                continue
            for src in sorted(src_dir.rglob("*")):
                if not src.is_file() or src.name in IGNORED_NAMES:
                    continue
                if "node_modules" in src.parts or "tests" in src.parts:
                    continue  # dépendances et tests ne sont pas distribués
                inside = src.relative_to(src_dir)
                dst = root / dest_sub / inside
                rel = f"{sub}/{inside.as_posix()}"
                write_regular(src, dst, tool, rel, enabled, markers, keep_comments, force, reporter, root, record)

    if not dry_run:
        update_manifest(manifest_path, manifest, version, record)
    return 0


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="render_adapters.py",
        description="Génère les adaptateurs des outils activés depuis .sdlc/templates/adapters/.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("root", nargs="?", default=".", help="racine du projet (défaut : .)")
    parser.add_argument("--config", default=None, help="chemin de sdlc.config.yaml")
    parser.add_argument("--templates", default=None, help="dossier .sdlc/templates/adapters")
    parser.add_argument("--force", action="store_true", help="écrase un fichier existant")
    parser.add_argument("--dry-run", action="store_true", help="simule sans écrire")
    parser.add_argument("--keep-comments", action="store_true", help="conserve les commentaires de génération")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"erreur : racine introuvable : {root}", file=sys.stderr)
        return 2

    config_path = Path(args.config).expanduser().resolve() if args.config else root / "sdlc.config.yaml"
    if not config_path.is_file():
        print(f"erreur : configuration introuvable : {config_path}", file=sys.stderr)
        return 2

    try:
        config, engine = load_config(config_path)
    except Exception as exc:  # noqa: BLE001 - message clair à l'utilisateur
        print(f"erreur : lecture de {config_path} impossible : {exc}", file=sys.stderr)
        return 2

    templates = Path(args.templates).expanduser().resolve() if args.templates else default_templates(root, config)
    if not templates or not templates.is_dir():
        print("erreur : dossier .sdlc/templates/adapters introuvable ; utiliser --templates", file=sys.stderr)
        return 2

    print(
        f"Configuration : {config_path} (moteur {engine}) — gabarits : {templates}",
        file=sys.stderr,
    )
    reporter = Reporter(dry_run=args.dry_run)
    code = render(root, templates, config, args.force, args.dry_run, args.keep_comments, reporter)
    reporter.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
