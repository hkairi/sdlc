#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bibliothèque de l'installateur du framework SDLC.

Spécification : ``docs/conception/workflow-sdlc.md`` § 13.
Python 3.9+, bibliothèque standard uniquement.

Le module ne présente aucune fonction interactive : il expose ``main``, appelé
par ``bin/sdlc-install``. Aucune commande git n'est jamais exécutée.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone

# --- Constantes -------------------------------------------------------------

MARKER_HTML_BEGIN = "<!-- sdlc:begin v{version} -->"
MARKER_HTML_END = "<!-- sdlc:end -->"
MARKER_HASH_BEGIN = "# sdlc:begin v{version}"
MARKER_HASH_END = "# sdlc:end"

GITIGNORE_BODY = "/reports/\n__pycache__/\n*.py[cod]"

CLAUDE_REF_PREFIX = "@AGENTS.md\n\n"

SKIP_DIRS = {"__pycache__", ".git", ".DS_Store"}
SKIP_FILES = {".DS_Store"}
SKIP_SUFFIXES = (".pyc", ".pyo")

RE_HTML_BEGIN = re.compile(r"<!-- sdlc:begin v([^ ]+) -->")
RE_HTML_BLOCK = re.compile(r"<!-- sdlc:begin v[^ ]+ -->.*?<!-- sdlc:end -->", re.S)
RE_HTML_BLOCK_STRIP = re.compile(r"<!-- sdlc:begin v[^ ]+ -->.*?<!-- sdlc:end -->\n?", re.S)
RE_HASH_BLOCK = re.compile(r"# sdlc:begin v[^ ]+\n.*?# sdlc:end", re.S)
RE_HASH_BLOCK_STRIP = re.compile(r"# sdlc:begin v[^ ]+\n.*?# sdlc:end\n?", re.S)
# Bloc des consignes propres à Claude Code, inséré par ``render_adapters.py``.
RE_CLAUDE_BLOCK_STRIP = re.compile(
    r"\n*<!-- sdlc-claude:begin v[^ ]+ -->.*?<!-- sdlc-claude:end -->", re.S)


# --- Utilitaires ------------------------------------------------------------

def sha256_bytes(data):
    """Empreinte sha256 (hexadécimal) d'un ``bytes``."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    """Empreinte sha256 (hexadécimal) d'un fichier, lue par blocs."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root):
    """Parcourt ``root`` en suivant les liens symboliques.

    Renvoie des couples ``(chemin_relatif_posix, chemin_absolu)``. Les caches
    (``__pycache__``, ``*.pyc``) et ``.DS_Store`` sont ignorés. Un garde-fou
    évite les boucles de liens symboliques.
    """
    root = os.path.abspath(root)
    seen = set()

    def walk(directory):
        real = os.path.realpath(directory)
        if real in seen:
            return
        seen.add(real)
        try:
            entries = sorted(os.listdir(directory))
        except OSError:
            return
        for name in entries:
            full = os.path.join(directory, name)
            if os.path.isdir(full):
                if name in SKIP_DIRS:
                    continue
                yield from walk(full)
            else:
                if name in SKIP_FILES or name.endswith(SKIP_SUFFIXES):
                    continue
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                yield rel, full

    yield from walk(root)


def tree_hashes(root):
    """Dictionnaire ``chemin relatif -> sha256`` des fichiers d'une arborescence."""
    return {rel: sha256_file(full) for rel, full in iter_files(root)}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def strip_block(content, style):
    """Retire le premier bloc délimité du contenu, en restaurant l'original."""
    pattern = RE_HTML_BLOCK_STRIP if style == "html" else RE_HASH_BLOCK_STRIP
    new_content, _ = pattern.subn("", content, count=1)
    return new_content


def remove_claude_ref(content):
    """Retire la ligne ``@AGENTS.md`` ajoutée en tête par l'installateur."""
    if content.startswith("@AGENTS.md\n"):
        content = content[len("@AGENTS.md\n"):]
        if content.startswith("\n"):
            content = content[1:]
    return content


def has_claude_ref(content):
    return any(line.strip() == "@AGENTS.md" for line in content.splitlines())


def remove_ops(target, ops):
    """Retire d'un objet JSON les entrées ajoutées décrites par ``ops``.

    ``ops`` provient de la section ``adapters.merged`` du manifeste, écrite par
    ``render_adapters.py``. Seules les entrées réellement présentes **et égales**
    à ce qui a été ajouté sont retirées : les modifications de l'humain sont
    conservées.
    """
    if not isinstance(target, dict):
        return
    for op in ops or []:
        if not isinstance(op, dict):
            continue
        path = op.get("path") or []
        if not path:
            continue
        node = target
        for key in path[:-1]:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                node = None
                break
        if not isinstance(node, dict):
            continue
        last = path[-1]
        kind = op.get("op")
        if kind == "set_key":
            if last in node and node[last] == op.get("value"):
                del node[last]
        elif kind == "append_list":
            if last in node and isinstance(node[last], list):
                items = op.get("items") or []
                node[last] = [value for value in node[last] if value not in items]


# --- Installateur -----------------------------------------------------------

class Installer:
    def __init__(self, framework_root, target, version=None,
                 dry_run=False, upgrade=False, uninstall=False, force=False):
        self.framework_root = os.path.abspath(framework_root)
        self.target = os.path.abspath(target)
        self.dry_run = dry_run
        self.upgrade = upgrade
        self.uninstall = uninstall
        self.force = force
        self.version = version or self._read_version()
        self.changed = False
        self.counts = {"créer": 0, "remplacer": 0, "ignorer": 0,
                       "conserver": 0, "conflit": 0, "lier": 0,
                       "bloc inséré": 0, "bloc remplacé": 0, "retirer": 0}
        self.manifest = {}
        self.skill_names = []

    # -- chemins -------------------------------------------------------------

    def _read_version(self):
        with open(os.path.join(self.framework_root, "VERSION"),
                  encoding="utf-8") as fh:
            return fh.read().strip()

    def p(self, *parts):
        return os.path.join(self.target, *parts)

    def rel(self, path):
        return os.path.relpath(path, self.target).replace(os.sep, "/")

    @property
    def manifest_path(self):
        return self.p(".sdlc", "manifest.json")

    # -- journalisation ------------------------------------------------------

    def log(self, action, path, note=None):
        if action in self.counts:
            self.counts[action] += 1
        suffix = " ({})".format(note) if note else ""
        print("{:<12} {}{}".format(action, path, suffix))

    def error(self, message):
        print("erreur : {}".format(message), file=sys.stderr)
        return 2

    # -- lecture/écriture bas niveau ----------------------------------------

    def lexists(self, path):
        return os.path.lexists(path)

    def read_bytes(self, path):
        try:
            with open(path, "rb") as fh:
                return fh.read()
        except (OSError, IsADirectoryError):
            return None

    def read_text(self, path):
        data = self.read_bytes(path)
        if data is None:
            return None
        return data.decode("utf-8")

    def write_bytes(self, dest, data, mode=None):
        self.changed = True
        if self.dry_run:
            return
        directory = os.path.dirname(dest)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(data)
        if mode is not None:
            try:
                os.chmod(dest, mode)
            except OSError:
                pass

    def write_text(self, dest, text):
        self.write_bytes(dest, text.encode("utf-8"))

    def source_mode(self, src):
        try:
            return stat.S_IMODE(os.stat(src).st_mode)
        except OSError:
            return None

    # -- manifeste -----------------------------------------------------------

    def load_manifest(self):
        if os.path.isfile(self.manifest_path):
            try:
                with open(self.manifest_path, encoding="utf-8") as fh:
                    self.manifest = json.load(fh)
            except (OSError, ValueError):
                self.manifest = {}
        for key in ("files", "symlinks", "blocks"):
            self.manifest.setdefault(key, {})

    def manifest_file_sha(self, rel):
        entry = self.manifest.get("files", {}).get(rel)
        if isinstance(entry, dict):
            return entry.get("sha256")
        return None

    def record_file(self, rel, sha):
        self.manifest.setdefault("files", {})[rel] = {"sha256": sha}

    def record_symlink(self, rel, target):
        self.manifest.setdefault("symlinks", {})[rel] = target

    def record_block(self, rel, info):
        self.manifest.setdefault("blocks", {})[rel] = info

    def write_manifest(self):
        self.manifest["framework_version"] = self.version
        self.manifest["installer"] = "bin/sdlc-install"
        self.manifest.setdefault("installed_at", now_iso())
        self.manifest["updated_at"] = now_iso()
        if self.dry_run:
            return
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump(self.manifest, fh, indent=2, ensure_ascii=False,
                      sort_keys=True)
            fh.write("\n")

    # -- installation d'un fichier ------------------------------------------

    def install_one(self, src, dest, kind="file"):
        rel = self.rel(dest)
        data = self.read_bytes(src)
        if data is None:
            self.log("conflit", rel, "source illisible")
            return
        sha = sha256_bytes(data)
        mode = self.source_mode(src)

        if not self.lexists(dest):
            self.write_bytes(dest, data, mode)
            self.record_file(rel, sha)
            self.log("créer", rel)
            return

        if os.path.isdir(dest) and not os.path.islink(dest):
            self.log("conflit", rel, "un dossier de même nom existe")
            return

        current = self.read_bytes(dest)
        if current is None:
            self.log("conflit", rel, "entrée existante illisible")
            return
        current_sha = sha256_bytes(current)

        if current_sha == sha:
            self.log("ignorer", rel, "déjà à jour")
            return

        if self.upgrade and self.manifest_file_sha(rel) == current_sha:
            self.write_bytes(dest, data, mode)
            self.record_file(rel, sha)
            self.log("remplacer", rel, "fichier non modifié, mis à jour")
            return

        if self.force:
            self.write_bytes(dest, data, mode)
            self.record_file(rel, sha)
            self.log("remplacer", rel, "forcé")
            return

        if kind == "skill":
            self.log("conflit", rel, "contenu différent, rien n'a été écrit")
        elif self.upgrade:
            self.log("conserver", rel,
                     "modifié depuis l'installation ; --force pour écraser")
        else:
            self.log("ignorer", rel,
                     "existe déjà, contenu différent (--upgrade pour mettre à jour)")

    # -- espace .sdlc/ -------------------------------------------------------

    def install_sdlc(self):
        self.install_one(os.path.join(self.framework_root, "VERSION"),
                         self.p(".sdlc", "VERSION"))
        self.install_one(
            os.path.join(self.framework_root, "docs", "conception",
                         "workflow-sdlc.md"),
            self.p(".sdlc", "workflow-sdlc.md"))
        templates_root = os.path.join(self.framework_root, "templates")
        for rel, full in iter_files(templates_root):
            self.install_one(full, self.p(".sdlc", "templates", *rel.split("/")))

    # -- skills --------------------------------------------------------------

    def install_skills(self):
        skills_root = os.path.join(self.framework_root, ".agents", "skills")
        if not os.path.isdir(skills_root):
            return
        self.skill_names = [name for name in sorted(os.listdir(skills_root))
                            if os.path.isdir(os.path.join(skills_root, name))]
        for name in self.skill_names:
            src = os.path.join(skills_root, name)
            dest = self.p(".agents", "skills", name)
            self.install_skill(name, src, dest)

    def install_skill(self, name, src, dest):
        rel = self.rel(dest)
        if not self.lexists(dest):
            for file_rel, full in iter_files(src):
                self.install_one(full, os.path.join(dest, *file_rel.split("/")),
                                 kind="skill")
            return

        if not os.path.isdir(dest) or os.path.islink(dest):
            self.log("conflit", rel, "entrée de même nom incompatible, rien n'a été écrit")
            return

        if self.upgrade:
            for file_rel, full in iter_files(src):
                self.install_one(full, os.path.join(dest, *file_rel.split("/")),
                                 kind="skill")
            return

        if tree_hashes(src) == tree_hashes(dest):
            self.log("ignorer", rel, "skill déjà installée")
        else:
            self.log("conflit", rel,
                     "skill existante différente, rien n'a été écrit")

    # -- .claude/skills ------------------------------------------------------

    def install_claude_skills(self):
        dest = self.p(".claude", "skills")
        rel = ".claude/skills"
        agents_skills = self.p(".agents", "skills")

        if not self.lexists(dest):
            if not self.dry_run:
                os.makedirs(self.p(".claude"), exist_ok=True)
                os.symlink("../.agents/skills", dest)
            self.changed = True
            self.record_symlink(rel, "../.agents/skills")
            self.log("lier", rel, "-> ../.agents/skills")
            return

        if os.path.islink(dest):
            if os.path.realpath(dest) == os.path.realpath(agents_skills):
                self.log("ignorer", rel, "lien déjà en place")
            else:
                self.log("conflit", rel,
                         "lien existant vers {}, conservé".format(os.readlink(dest)))
            return

        if os.path.isdir(dest):
            for name in self.skill_names:
                link = os.path.join(dest, name)
                link_rel = ".claude/skills/{}".format(name)
                link_target = "../../.agents/skills/{}".format(name)
                expected = os.path.join(agents_skills, name)
                if not self.lexists(link):
                    if not self.dry_run:
                        os.symlink(link_target, link)
                    self.changed = True
                    self.record_symlink(link_rel, link_target)
                    self.log("lier", link_rel, "-> {}".format(link_target))
                elif os.path.islink(link) and \
                        os.path.realpath(link) == os.path.realpath(expected):
                    self.log("ignorer", link_rel, "lien déjà en place")
                else:
                    self.log("conflit", link_rel,
                             "entrée existante différente, conservée")
            return

        self.log("conflit", rel, "existe et n'est ni dossier ni lien")

    # -- AGENTS.md -----------------------------------------------------------

    def agents_block(self):
        with open(os.path.join(self.framework_root, "AGENTS.md"),
                  encoding="utf-8") as fh:
            body = fh.read().rstrip("\n")
        begin = MARKER_HTML_BEGIN.format(version=self.version)
        return "{}\n{}\n{}".format(begin, body, MARKER_HTML_END)

    def install_agents_md(self):
        dest = self.p("AGENTS.md")
        rel = "AGENTS.md"
        block = self.agents_block()
        block_sha = sha256_bytes(block.encode("utf-8"))

        if not self.lexists(dest):
            self.write_text(dest, block + "\n")
            self.record_block(rel, {"style": "html", "sha256": block_sha,
                                    "created": True})
            self.log("bloc inséré", rel, "fichier créé")
            return

        content = self.read_text(dest)
        if content is None:
            self.log("conflit", rel, "fichier illisible")
            return

        match = RE_HTML_BEGIN.search(content)
        has_end = MARKER_HTML_END in content
        if match and has_end:
            current_version = match.group(1)
            if current_version == self.version:
                self.log("ignorer", rel, "bloc déjà à jour")
                return
            new_content = RE_HTML_BLOCK.sub(lambda _m: block, content, count=1)
            self.write_text(dest, new_content)
            self.record_block(rel, {"style": "html", "sha256": block_sha,
                                    "created": False})
            self.log("bloc remplacé", rel,
                     "v{} -> v{}".format(current_version, self.version))
            return

        if match and not has_end:
            self.log("conflit", rel,
                     "marqueur sdlc:begin sans sdlc:end, non modifié")
            return

        self.write_text(dest, block + "\n" + content)
        self.record_block(rel, {"style": "html", "sha256": block_sha,
                                "created": False})
        self.log("bloc inséré", rel, "en tête, contenu de l'humain conservé")

    # -- CLAUDE.md -----------------------------------------------------------

    def install_claude_md(self):
        dest = self.p("CLAUDE.md")
        rel = "CLAUDE.md"

        if not self.lexists(dest):
            self.write_text(dest, "@AGENTS.md\n")
            self.record_block(rel, {"style": "ref", "created": True,
                                    "added": True})
            self.log("bloc inséré", rel, "@AGENTS.md, fichier créé")
            return

        content = self.read_text(dest)
        if content is None:
            self.log("conflit", rel, "fichier illisible")
            return

        if has_claude_ref(content):
            self.log("ignorer", rel, "@AGENTS.md déjà présent")
            return

        self.write_text(dest, CLAUDE_REF_PREFIX + content)
        self.record_block(rel, {"style": "ref", "created": False, "added": True})
        self.log("bloc inséré", rel, "@AGENTS.md en tête")

    # -- .gitignore ----------------------------------------------------------

    def gitignore_block(self):
        begin = MARKER_HASH_BEGIN.format(version=self.version)
        return "{}\n{}\n{}".format(begin, GITIGNORE_BODY, MARKER_HASH_END)

    def install_gitignore(self):
        dest = self.p(".gitignore")
        rel = ".gitignore"
        block = self.gitignore_block()
        block_sha = sha256_bytes(block.encode("utf-8"))

        if not self.lexists(dest):
            self.write_text(dest, block + "\n")
            self.record_block(rel, {"style": "hash", "sha256": block_sha,
                                    "created": True})
            self.log("bloc inséré", rel, "fichier créé")
            return

        content = self.read_text(dest)
        if content is None:
            self.log("conflit", rel, "fichier illisible")
            return

        if RE_HASH_BLOCK.search(content):
            new_content = RE_HASH_BLOCK.sub(lambda _m: block, content, count=1)
            if new_content == content:
                self.log("ignorer", rel, "bloc déjà à jour")
                return
            self.write_text(dest, new_content)
            self.record_block(rel, {"style": "hash", "sha256": block_sha,
                                    "created": False})
            self.log("bloc remplacé", rel, "v{}".format(self.version))
            return

        self.write_text(dest, block + "\n" + content)
        self.record_block(rel, {"style": "hash", "sha256": block_sha,
                                "created": False})
        self.log("bloc inséré", rel, "en tête, contenu de l'humain conservé")

    # -- orchestration -------------------------------------------------------

    def install(self):
        self.load_manifest()
        self.install_sdlc()
        self.install_skills()
        self.install_claude_skills()
        self.install_agents_md()
        self.install_claude_md()
        self.install_gitignore()
        if not self.dry_run and (self.changed or not os.path.isfile(self.manifest_path)):
            self.write_manifest()
        self.print_summary()

    def print_summary(self):
        print()
        if self.dry_run:
            print("--dry-run : aucune écriture n'a été effectuée.")
        print("Résultat : {créer} créé(s), {remplacer} remplacé(s), "
              "{ignorer} ignoré(s), {conserver} conservé(s) car modifié(s), "
              "{lier} lien(s), {conflit} conflit(s).".format(**self.counts))

    # -- désinstallation -----------------------------------------------------

    def prune_parents(self, path):
        if self.dry_run:
            return
        directory = os.path.dirname(path)
        while os.path.abspath(directory) != self.target:
            try:
                os.rmdir(directory)
            except OSError:
                break
            directory = os.path.dirname(directory)

    def uninstall_run(self):
        if not os.path.isfile(self.manifest_path):
            return self.error(
                "aucune installation trouvée ({} absent)".format(
                    self.rel(self.manifest_path)))
        self.load_manifest()
        adapters = self.manifest.get("adapters")
        adapters = adapters if isinstance(adapters, dict) else {}
        adapter_files = adapters.get("files")
        adapter_files = adapter_files if isinstance(adapter_files, dict) else {}
        adapter_merged = adapters.get("merged")
        adapter_merged = adapter_merged if isinstance(adapter_merged, dict) else {}
        leftovers = []

        # Bloc `sdlc-claude` de CLAUDE.md, retiré avant la directive @AGENTS.md.
        claude_info = self.manifest.get("blocks", {}).get("CLAUDE.md", {})
        if adapters.get("claude_md_block") and not claude_info.get("created"):
            path = self.p("CLAUDE.md")
            if os.path.isfile(path):
                content = self.read_text(path)
                if content and RE_CLAUDE_BLOCK_STRIP.search(content):
                    new_content = RE_CLAUDE_BLOCK_STRIP.sub("", content, count=1)
                    if new_content != content:
                        self.write_text(path, new_content)
                        self.log("retirer", "CLAUDE.md", "bloc sdlc-claude")

        for rel in sorted(self.manifest.get("files", {})):
            path = self.p(*rel.split("/"))
            entry = self.manifest["files"][rel]
            if os.path.islink(path) or not os.path.isfile(path):
                leftovers.append(rel)
                continue
            if sha256_file(path) == entry.get("sha256"):
                if not self.dry_run:
                    os.remove(path)
                self.log("retirer", rel)
                self.prune_parents(path)
            else:
                self.log("conserver", rel,
                         "modifié depuis l'installation, à retirer à la main")
                leftovers.append(rel)

        for rel, target in sorted(self.manifest.get("symlinks", {}).items()):
            path = self.p(*rel.split("/"))
            if os.path.islink(path) and os.readlink(path) == target:
                if not self.dry_run:
                    os.remove(path)
                self.log("retirer", rel)
                self.prune_parents(path)
            elif os.path.lexists(path):
                self.log("conserver", rel, "lien différent, à retirer à la main")
                leftovers.append(rel)

        for rel, info in sorted(self.manifest.get("blocks", {}).items()):
            path = self.p(*rel.split("/"))
            if not os.path.lexists(path):
                continue
            style = info.get("style")
            if info.get("created"):
                if not self.dry_run:
                    os.remove(path)
                self.log("retirer", rel, "fichier créé par l'installateur")
                self.prune_parents(path)
                continue
            if style == "ref":
                if info.get("added"):
                    content = self.read_text(path)
                    new_content = remove_claude_ref(content)
                    if new_content != content:
                        self.write_text(path, new_content)
                        self.log("retirer", rel, "@AGENTS.md")
                continue
            content = self.read_text(path)
            if content is None:
                continue
            new_content = strip_block(content, style)
            if new_content != content:
                self.write_text(path, new_content)
                self.log("retirer", rel, "bloc délimité")

        for rel in sorted(adapter_files):
            path = self.p(*rel.split("/"))
            if not os.path.lexists(path):
                continue
            entry = adapter_files[rel] or {}
            if os.path.islink(path) or not os.path.isfile(path):
                self.log("conserver", rel, "entrée de type inattendu, à retirer à la main")
                leftovers.append(rel)
                continue
            if sha256_file(path) == entry.get("sha256"):
                if not self.dry_run:
                    os.remove(path)
                self.log("retirer", rel, "adaptateur généré")
                self.prune_parents(path)
            else:
                self.log("conserver", rel,
                         "adaptateur modifié par l'humain, à retirer à la main")
                leftovers.append(rel)

        for rel, ops in sorted(adapter_merged.items()):
            path = self.p(*rel.split("/"))
            if not os.path.isfile(path):
                continue
            content = self.read_text(path)
            if content is None:
                continue
            try:
                data = json.loads(content)
            except ValueError:
                self.log("conserver", rel, "JSON illisible, entrées non retirées")
                leftovers.append(rel)
                continue
            if not isinstance(data, dict):
                continue
            remove_ops(data, ops)
            new_content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            if new_content != content:
                self.write_text(path, new_content)
                self.log("retirer", rel, "entrées ajoutées par le framework")

        if os.path.isfile(self.manifest_path):
            if not self.dry_run:
                os.remove(self.manifest_path)
            self.prune_parents(self.manifest_path)

        print()
        if leftovers:
            print("À retirer à la main (modifiés depuis l'installation) :")
            for rel in leftovers:
                print("  - {}".format(rel))
        else:
            print("Rien à retirer à la main : tous les fichiers installés ont été retirés.")
        if self.dry_run:
            print("--dry-run : aucune écriture n'a été effectuée.")
        return 0

    def run(self):
        if self.uninstall:
            return self.uninstall_run()
        self.install()
        return 0


# --- Interface en ligne de commande ----------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="sdlc-install",
        description="Installe le framework SDLC dans un projet (nouveau ou "
                    "existant), sans rien détruire. L'installateur est lancé "
                    "depuis le dépôt du framework.")
    parser.add_argument("--target", metavar="PROJET", required=True,
                        help="répertoire du projet cible (doit exister)")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche les actions sans rien écrire")
    parser.add_argument("--upgrade", action="store_true",
                        help="met à jour les fichiers non modifiés et les blocs délimités")
    parser.add_argument("--uninstall", action="store_true",
                        help="retire les fichiers installés non modifiés et les blocs")
    parser.add_argument("--force", action="store_true",
                        help="écrase les fichiers modifiés par l'humain")
    return parser


def framework_root_from_here():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def is_framework_root(path):
    path = os.path.abspath(path)
    if os.path.realpath(path) == os.path.realpath(framework_root_from_here()):
        return True
    return os.path.isfile(os.path.join(path, "bin", "sdlc-install"))


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.upgrade and args.uninstall:
        print("erreur : --upgrade et --uninstall sont incompatibles",
              file=sys.stderr)
        return 2

    target = args.target
    if not os.path.exists(target):
        print("erreur : chemin inexistant : {}".format(target), file=sys.stderr)
        return 2
    if not os.path.isdir(target):
        print("erreur : le chemin cible n'est pas un répertoire : {}".format(target),
              file=sys.stderr)
        return 2
    if is_framework_root(target):
        print("erreur : refus d'installer le framework dans son propre dépôt "
              "({})".format(target), file=sys.stderr)
        return 2

    installer = Installer(
        framework_root=framework_root_from_here(),
        target=target,
        dry_run=args.dry_run,
        upgrade=args.upgrade,
        uninstall=args.uninstall,
        force=args.force,
    )
    return installer.run()
