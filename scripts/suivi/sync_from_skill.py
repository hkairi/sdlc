#!/usr/bin/env python3
"""Vendorisation et contrôle de dérive des scripts du suivi.

Pourquoi ce script
------------------
Le plugin `ai-sdlc-tracker` (et la CI) doivent appeler EXACTEMENT les mêmes scripts
que la skill `suivi-taches`, sans dépendre d'un chemin utilisateur
(`~/.claude/skills/...`). Les scripts sont donc copiés dans le dépôt, sous
`scripts/suivi/`, en reproduisant l'arborescence de la skill — c'est nécessaire :
`generate.py` et `generate_multi.py` déduisent `SKILL_DIR = dirname(dirname(__file__))`
puis lisent `<SKILL_DIR>/assets/template*.html`. Aplatir la copie casserait les
gabarits sans modifier les scripts (ce qui créerait une dérive).

Trois copies de la même logique existent (skill, dépôt, manifeste) mais une seule
vérité opérationnelle : le dépôt, que le hook git, la CI et le plugin appellent.

Modes
-----
  --write   copie les scripts et gabarits depuis la skill, puis réécrit le manifeste.
            Idempotent : deux exécutions consécutives ne changent rien.
  --check   compare la copie du dépôt à la source de la skill si elle est disponible
            (poste de travail), sinon vérifie l'intégrité de la copie contre le
            manifeste (CI, où la skill n'existe pas).

Codes de sortie : 0 = conforme ; 1 = dérive ; 2 = aucun moyen de contrôler.

Usage :
  python3 scripts/suivi/sync_from_skill.py --check
  SUIVI_SKILL_DIR=~/.claude/skills/suivi-taches python3 scripts/suivi/sync_from_skill.py --write
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # racine du dépôt
VENDOR = os.path.join(HERE, "scripts")                 # copie des scripts Python
ASSETS = os.path.join(HERE, "assets")                  # copie des gabarits
MANIFEST = os.path.join(HERE, "manifest.json")
DEFAULT_SKILL = os.path.expanduser("~/.claude/skills/suivi-taches")

# Copie : (chemin relatif à la vendorisation, chemin relatif à la skill, en-tête ?)
MAP = [
    ("scripts/track.py", "scripts/track.py", True),
    ("scripts/track_multi.py", "scripts/track_multi.py", True),
    ("scripts/track_phase.py", "scripts/track_phase.py", True),
    ("scripts/generate.py", "scripts/generate.py", True),
    ("scripts/generate_multi.py", "scripts/generate_multi.py", True),
    ("scripts/generate_from_openspec.py", "scripts/generate_from_openspec.py", True),
    ("scripts/phases.py", "scripts/phases.py", True),
    ("scripts/sourcedocs.py", "scripts/sourcedocs.py", True),
    ("assets/template.html", "assets/template.html", False),
    ("assets/template-multi.html", "assets/template-multi.html", False),
    ("assets/manifest-example.json", "assets/manifest-example.json", False),
]

HEADER_OPEN = "# " + "-" * 75 + "\n"
HEADER_RE = re.compile(
    r"\A(#![^\n]*\n)?" + re.escape(HEADER_OPEN) + r"(?:#[^\n]*\n)*" + re.escape(HEADER_OPEN),
    re.M,
)


def header_for(src_rel, src_path, date):
    return HEADER_OPEN + (
        f"# Copie vendorisée — source : skill suivi-taches ({src_path})\n"
        f"# Copiée le {date}. Ne pas éditer ici : éditer la source, puis re-générer la copie\n"
        "# avec `python3 scripts/suivi/sync_from_skill.py --write`.\n"
        "# Contrôle de dérive : `python3 scripts/suivi/sync_from_skill.py --check`.\n"
    ) + HEADER_OPEN


def vendored_bytes(src_path, src_rel, with_header, date):
    """Contenu attendu de la copie (en-tête inclus pour les scripts)."""
    body = open(src_path, "rb").read()
    if not with_header:
        return body
    text = body.decode("utf-8")
    if text.startswith("#!"):
        shebang, rest = text.split("\n", 1)
        text = shebang + "\n" + header_for(src_rel, src_path, date) + rest
    else:
        text = header_for(src_rel, src_path, date) + text
    return text.encode("utf-8")


def normalized_bytes(raw, with_header):
    """Retire l'en-tête pour comparer à la source, octet pour octet."""
    if not with_header:
        return raw
    text = raw.decode("utf-8")
    return HEADER_RE.sub(lambda m: m.group(1) or "", text, count=1).encode("utf-8")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def skill_dir(arg):
    return os.path.abspath(os.path.expanduser(arg or os.environ.get("SUIVI_SKILL_DIR") or DEFAULT_SKILL))


def do_write(skill, date):
    missing = []
    for vend_rel, src_rel, with_header in MAP:
        src_path = os.path.join(skill, src_rel)
        if not os.path.isfile(src_path):
            missing.append(src_rel)
            continue
        dst = os.path.join(HERE, vend_rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(vendored_bytes(src_path, src_rel, with_header, date))
        if with_header:
            os.chmod(dst, 0o755)
    if missing:
        sys.stderr.write(
            "source incomplète dans la skill ("
            + ", ".join(missing)
            + f") : rien n'a été écrit pour ces fichiers.\nSkill attendue : {skill}\n"
        )
        return 2

    entries = []
    for vend_rel, src_rel, with_header in MAP:
        src_path = os.path.join(skill, src_rel)
        dst = os.path.join(HERE, vend_rel)
        raw = open(dst, "rb").read()
        entries.append(
            {
                "vendor": os.path.relpath(dst, ROOT),
                "source": src_rel,
                "header": with_header,
                "sha256_source": sha(open(src_path, "rb").read()),
                "sha256_vendor": sha(raw),
            }
        )
    manifest = {
        "schema": 1,
        "generated": date,
        "source": skill,
        "entries": entries,
    }
    open(MANIFEST, "w", encoding="utf-8").write(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"vendorisation écrite : {len(entries)} fichier(s), manifeste {os.path.relpath(MANIFEST, ROOT)}")
    return 0


def do_check(skill):
    if not os.path.isfile(MANIFEST):
        sys.stderr.write(f"aucun manifeste ({os.path.relpath(MANIFEST, ROOT)}) : impossible de contrôler.\n")
        return 2
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    entries = {e["vendor"]: e for e in manifest["entries"]}

    have_skill = any(os.path.isfile(os.path.join(skill, e["source"])) for e in manifest["entries"])
    problems = []
    mode = "source" if have_skill else "manifeste"

    for vend_rel, entry in entries.items():
        dst = os.path.join(ROOT, vend_rel)
        short = os.path.relpath(dst, ROOT)
        if not os.path.isfile(dst):
            problems.append(f"{short} : absent du dépôt")
            continue
        raw = open(dst, "rb").read()

        src_path = os.path.join(skill, entry["source"])
        if have_skill and os.path.isfile(src_path):
            expected = normalized_bytes(raw, entry["header"])
            actual = open(src_path, "rb").read()
            if expected != actual:
                problems.append(f"{short} : diverge de la skill ({entry['source']})")
            if sha(raw) != entry.get("sha256_vendor"):
                problems.append(f"{short} : la copie a été modifiée à la main depuis la vendorisation")
        else:
            if sha(raw) != entry.get("sha256_vendor"):
                problems.append(f"{short} : ne correspond pas au manifeste")

    if problems:
        sys.stderr.write(f"dérive détectée (contrôle par {mode}) :\n  " + "\n  ".join(problems) + "\n")
        return 1
    print(f"vendorisation conforme : {len(entries)} fichier(s) (contrôle par {mode}).")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true", help="copier depuis la skill et réécrire le manifeste")
    g.add_argument("--check", action="store_true", help="vérifier la copie (source, sinon manifeste)")
    ap.add_argument("--skill", help=f"racine de la skill (défaut {DEFAULT_SKILL}, ou $SUIVI_SKILL_DIR)")
    args = ap.parse_args()
    skill = skill_dir(args.skill)
    date = datetime.date.today().isoformat()
    return do_write(skill, date) if args.write else do_check(skill)


if __name__ == "__main__":
    sys.exit(main())
