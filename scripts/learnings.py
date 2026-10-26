#!/usr/bin/env python3
"""Registre des apprentissages — lecture, requête et contrôle.

Chaque apprentissage est un fichier `openspec/learnings/L-NNNN-<slug>.md` avec un
frontmatter TOML (parsable par `tomllib`, aucune dépendance).

Un apprentissage répond à une seule question : **qu'est-ce qu'on a appris ici
qu'on ne veut pas réapprendre ?** Il doit être falsifiable (une commande, un
résultat), localisé (`scope`) et révocable (`status`).

Commandes :

  --check                 valide tous les fichiers (schéma, preuves, cycle de vie)
  --query "mots clés"     apprentissages actifs correspondants
  --paths a/b.go c/d.rb   apprentissages dont le scope couvre ces chemins
  --list                  tout ce qui est actif, sans filtre
  --json                  sortie machine

Sortie : 0 si tout est cohérent, 1 si un contrôle échoue, 2 en cas d'erreur.
Lecture seule.
"""

from __future__ import annotations

import argparse
import fnmatch
import glob
import json
import os
import re
import sys
import tomllib

KINDS = {"pitfall", "practice", "convention", "tooling"}
STATUSES = {"active", "superseded", "retired"}
REQUIRED = ["id", "title", "kind", "created", "status", "scope", "evidence"]
SECTIONS = ["## Règle", "## Pourquoi", "## Comment vérifier"]
ID_RE = re.compile(r"^L-(\d{4})$")
PROOF_RESULT_RE = re.compile(r"\d|✓|\b(valid|passed|ok|vert|green|réussi)\b", re.I)


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse(path: str) -> tuple[dict, str]:
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if not text.startswith("+++"):
        raise ValueError("frontmatter TOML absent (le fichier doit commencer par +++)")
    end = text.find("\n+++", 3)
    if end == -1:
        raise ValueError("frontmatter TOML non fermé")
    return tomllib.loads(text[3:end]), text[end + 4 :]


def rule_of(body: str) -> str:
    match = re.search(r"^##\s+Règle\s*$(.*?)(?=^##\s|\Z)", body, re.M | re.S)
    if not match:
        return ""
    for line in match.group(1).splitlines():
        if line.strip():
            return re.sub(r"[*`]", "", line.strip())
    return ""


def load(root: str) -> list[dict]:
    entries = []
    for path in sorted(glob.glob(os.path.join(root, "openspec", "learnings", "L-*.md"))):
        try:
            meta, body = parse(path)
        except (ValueError, tomllib.TOMLDecodeError) as error:
            entries.append({"id": os.path.basename(path), "path": path, "error": str(error)})
            continue
        meta["path"] = path
        meta["body"] = body
        meta["rule"] = rule_of(body)
        entries.append(meta)
    return entries


def validate(entry: dict) -> list[str]:
    problems: list[str] = []
    label = os.path.basename(entry["path"])
    if "error" in entry:
        return [f"{label} : {entry['error']}"]

    missing = [field for field in REQUIRED if field not in entry]
    if missing:
        return [f"{label} : champs obligatoires absents — {', '.join(missing)}"]

    identifier = str(entry.get("id", ""))
    if not ID_RE.match(identifier):
        problems.append(f"{label} : id « {identifier} » invalide (attendu L-NNNN)")
    elif not label.startswith(identifier + "-"):
        problems.append(f"{label} : le nom de fichier doit commencer par « {identifier}- »")

    if entry.get("kind") not in KINDS:
        problems.append(f"{label} : kind « {entry.get('kind')} » inconnu ({', '.join(sorted(KINDS))})")
    if entry.get("status") not in STATUSES:
        problems.append(f"{label} : status « {entry.get('status')} » inconnu")
    if not str(entry.get("title", "")).strip():
        problems.append(f"{label} : titre vide")

    scope = entry.get("scope")
    if not isinstance(scope, list) or not scope or not all(isinstance(item, str) and item for item in scope):
        problems.append(f"{label} : scope doit être une liste non vide de chemins")
    elif "*" in scope:
        problems.append(f"{label} : scope « * » interdit — un apprentissage global n'est jamais retrievé")
    if not entry.get("tags"):
        problems.append(f"{label} : tags vide (la recherche par mot-clé en dépend)")

    evidence = entry.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        problems.append(f"{label} : aucune preuve (une entrée sans commande reproductible n'entre pas)")
    else:
        for index, item in enumerate(evidence, start=1):
            if not isinstance(item, dict) or not item.get("cmd") or not item.get("result"):
                problems.append(f"{label} : preuve #{index} incomplète (cmd et result obligatoires)")
            elif not PROOF_RESULT_RE.search(str(item["result"])):
                problems.append(f"{label} : preuve #{index} sans résultat observable — « {item['result']} »")

    for section in SECTIONS:
        if section not in entry["body"]:
            problems.append(f"{label} : section « {section} » absente")

    status = entry.get("status")
    if status == "retired" and not str(entry.get("retired_reason", "")).strip():
        problems.append(f"{label} : status « retired » sans retired_reason")
    if status == "superseded" and not str(entry.get("superseded_by", "")).strip():
        problems.append(f"{label} : status « superseded » sans superseded_by")

    return problems


def check_all(root: str) -> int:
    entries = load(root)
    if not entries:
        print("learnings — aucun apprentissage enregistré")
        return 0
    problems: list[str] = []
    seen: dict[str, str] = {}
    for entry in entries:
        for problem in validate(entry):
            problems.append(problem)
        identifier = str(entry.get("id", ""))
        if identifier in seen:
            problems.append(f"{identifier} : identifiant dupliqué ({seen[identifier]} et {os.path.basename(entry['path'])})")
        seen[identifier] = os.path.basename(entry["path"])

    identifiers = set(seen)
    for entry in entries:
        target = entry.get("superseded_by")
        if target and target not in identifiers:
            problems.append(f"{os.path.basename(entry['path'])} : superseded_by « {target} » introuvable")

    print(f"learnings — {len(entries)} entrée(s)")
    for problem in problems:
        print(f"  ✖ {problem}")
    if not problems:
        active = sum(1 for entry in entries if entry.get("status") == "active")
        print(f"  ✓ schéma, preuves et cycle de vie cohérents ({active} active(s))")
    return 1 if problems else 0


def scope_matches(scope: str, path: str) -> bool:
    normalized = scope.rstrip("/")
    return (
        path == normalized
        or path.startswith(normalized + "/")
        or fnmatch.fnmatch(path, scope)
        or fnmatch.fnmatch(path, normalized + "/**")
    )


def score(entry: dict, tokens: list[str], paths: list[str]) -> int:
    total = 0
    haystack = " ".join(
        [str(entry.get("title", "")), str(entry.get("rule", "")), " ".join(entry.get("tags", []))]
    ).lower()
    for token in tokens:
        if token in haystack:
            total += 2
        elif any(token in tag.lower() for tag in entry.get("tags", [])):
            total += 2
    for path in paths:
        if any(scope_matches(scope, path) for scope in entry.get("scope", [])):
            total += 5
    return total


def select(root: str, tokens: list[str], paths: list[str], limit: int) -> list[dict]:
    entries = [entry for entry in load(root) if entry.get("status") == "active"]
    ranked = [(score(entry, tokens, paths), entry) for entry in entries]
    ranked = [(value, entry) for value, entry in ranked if value > 0]
    ranked.sort(key=lambda item: (-item[0], item[1].get("id", "")))
    return [entry for _, entry in ranked[:limit]]


def render(entries: list[dict]) -> str:
    if not entries:
        return "aucun apprentissage applicable"
    lines = []
    for entry in entries:
        lines.append(f"{entry.get('id')}  [{entry.get('kind')}]  {entry.get('title')}")
        lines.append(f"  règle : {entry.get('rule') or '(vide)'}")
        lines.append(f"  scope : {', '.join(entry.get('scope', []))}")
        lines.append(f"  fichier : {os.path.relpath(entry['path'], repo_root())}")
        if entry.get("evidence"):
            first = entry["evidence"][0]
            lines.append(f"  preuve : {first.get('cmd')} → {first.get('result')}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Registre des apprentissages (lecture seule).")
    parser.add_argument("--check", action="store_true", help="valider tous les fichiers")
    parser.add_argument("--query", default="", help="mots-clés (titre, tags, règle)")
    parser.add_argument("--paths", nargs="*", default=[], help="chemins concernés")
    parser.add_argument("--list", action="store_true", help="tous les apprentissages actifs")
    parser.add_argument("--limit", type=int, default=8, help="nombre maximum de résultats")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    parser.add_argument("--root", default=None, help="racine du dépôt")
    args = parser.parse_args()

    root = os.path.abspath(args.root) if args.root else repo_root()
    if args.check:
        return check_all(root)

    tokens = [token for token in re.split(r"[^a-z0-9àâäéèêëïîôöùûüç]+", args.query.lower()) if len(token) > 2]
    if args.list:
        entries = [entry for entry in load(root) if entry.get("status") == "active"][: args.limit]
    elif tokens or args.paths:
        entries = select(root, tokens, args.paths, args.limit)
    else:
        parser.error("indiquer --check, --query, --paths ou --list")

    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2, default=str))
    else:
        print(render(entries))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileNotFoundError as error:
        print(f"learnings : fichier introuvable — {error}", file=sys.stderr)
        sys.exit(2)
