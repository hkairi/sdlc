"""Détection du profil de processus Git par dépôt."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SEMVER = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+].*)?$")
PROFILE_LABELS = {
    "git_flow": "Git Flow",
    "github_flow": "GitHub Flow",
    "trunk_based": "trunk-based",
    "gitlab_flow": "GitLab Flow",
    "unknown": "non identifiable",
}


@dataclass(frozen=True)
class ProcessSignals:
    """Signaux observés pour un dépôt."""

    branches: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    merge_strategy: Mapping[str, int] = field(default_factory=dict)
    protected_branches: tuple[str, ...] = ()
    ci_files: tuple[str, ...] = ()
    merge_commits: int | None = None
    total_commits: int | None = None


@dataclass(frozen=True)
class ProcessDetection:
    """Profil détecté, signaux et confiance heuristique."""

    key: str
    label: str
    confidence: float
    detected: bool
    signals: tuple[dict[str, Any], ...]
    reasons: tuple[str, ...]
    scores: Mapping[str, float]


def collect_git_signals(repository_path: str | Path) -> ProcessSignals:
    """Lit branches et tags en lecture seule ; les protections restent inconnues."""
    path = Path(repository_path)
    if not path.is_dir():
        return ProcessSignals()
    branch_names: list[str] = []
    tag_names: list[str] = []
    try:
        branches = subprocess.run(
            ["git", "-C", str(path), "for-each-ref", "--format=%(refname:short)", "refs/heads"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        tags = subprocess.run(
            ["git", "-C", str(path), "for-each-ref", "--format=%(refname:short)", "refs/tags"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        branch_names = [line.strip() for line in branches.stdout.splitlines() if line.strip()]
        tag_names = [line.strip() for line in tags.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        pass
    ci_files: list[str] = []
    for candidate in (
        ".github/workflows",
        ".gitlab-ci.yml",
        "Jenkinsfile",
        ".circleci/config.yml",
        "azure-pipelines.yml",
    ):
        if (path / candidate).exists():
            ci_files.append(candidate)
    merge_commits = None
    total_commits = None
    try:
        merges = subprocess.run(
            ["git", "-C", str(path), "rev-list", "--count", "--merges", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        total = subprocess.run(
            ["git", "-C", str(path), "rev-list", "--count", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        merge_commits = int(merges.stdout.strip() or 0)
        total_commits = int(total.stdout.strip() or 0)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return ProcessSignals(
        branches=tuple(branch_names),
        tags=tuple(tag_names),
        ci_files=tuple(ci_files),
        merge_commits=merge_commits,
        total_commits=total_commits,
    )


def _has_branch(branches: set[str], *names: str) -> bool:
    return any(name in branches for name in names)


def detect_process(signals: ProcessSignals) -> ProcessDetection:
    """Calcule un profil parmi les quatre heuristiques documentées."""
    branches = {branch.casefold() for branch in signals.branches}
    tags = tuple(signals.tags)
    semver_tags = [tag for tag in tags if SEMVER.match(tag)]
    develop = _has_branch(branches, "develop", "development")
    release_branches = {
        branch for branch in branches if branch.startswith(("release/", "hotfix/"))
    }
    env_branches = {
        branch
        for branch in branches
        if branch in {"staging", "stage", "preprod", "production", "prod"}
        or any(token in branch for token in ("staging", "preprod", "production"))
    }
    ci = bool(signals.ci_files)
    merge_strategy = {key.casefold(): int(value) for key, value in signals.merge_strategy.items()}
    merge_total = sum(merge_strategy.values())
    squash_ratio = merge_strategy.get("squash", 0) / merge_total if merge_total else None
    merge_ratio = (
        (signals.merge_commits / signals.total_commits)
        if signals.merge_commits is not None and signals.total_commits
        else None
    )
    protected_main = _has_branch({item.casefold() for item in signals.protected_branches}, "main", "master")

    scores: dict[str, float] = {
        "git_flow": 0.0,
        "github_flow": 0.0,
        "trunk_based": 0.0,
        "gitlab_flow": 0.0,
    }
    observed: list[dict[str, Any]] = []

    def signal(kind: str, value: Any, interpretation: str) -> None:
        observed.append(
            {"kind": kind, "value": value, "interpretation": interpretation}
        )

    if develop:
        scores["git_flow"] += 0.55
        signal("branche_develop", "présente", "branche develop observée")
    if release_branches:
        scores["git_flow"] += 0.25
        signal("branches_release", sorted(release_branches), "branches release/hotfix observées")
    if merge_ratio is not None and merge_ratio >= 0.15:
        scores["git_flow"] += 0.1
        signal("taux_merges", round(merge_ratio, 2), "merges réguliers dans l'historique")
    if branches and not develop:
        scores["github_flow"] += 0.15
        signal("absence_develop", "oui", "pas de branche develop")
    if semver_tags:
        scores["github_flow"] += 0.3
        signal("tags_semver", semver_tags[-5:], "tags de version observés")
    if squash_ratio is not None and squash_ratio >= 0.5:
        scores["github_flow"] += 0.35
        signal("squash", round(squash_ratio, 2), "majorité de merges squash")
    if ci:
        scores["github_flow"] += 0.1
        signal("ci", list(signals.ci_files), "fichiers CI présents")
    if branches and len(branches) <= 3:
        scores["trunk_based"] += 0.25
        signal("branches_courtes", len(branches), "peu de branches actives")
    if branches and not develop and not release_branches:
        scores["trunk_based"] += 0.2
        signal("pas_de_flux_long", "oui", "aucune branche de flux long")
    if protected_main:
        scores["trunk_based"] += 0.2
        signal("protection_main", "oui", "branche principale protégée")
    if ci:
        scores["trunk_based"] += 0.1
        signal("ci_trunk", list(signals.ci_files), "CI observée")
    if env_branches:
        scores["gitlab_flow"] += 0.55
        signal("branches_environnement", sorted(env_branches), "branches d'environnement observées")
    if any("gitlab" in item.casefold() for item in signals.ci_files):
        scores["gitlab_flow"] += 0.25
        signal("ci_gitlab", list(signals.ci_files), "configuration GitLab CI observée")

    best_key = max(scores, key=lambda key: scores[key])
    best_score = round(min(scores[best_key], 0.95), 2)
    if best_score < 0.4:
        reasons = []
        if not branches:
            reasons.append("aucune branche exploitable")
        if not tags:
            reasons.append("aucun tag")
        if not ci:
            reasons.append("aucun fichier CI")
        if merge_strategy == {} and merge_ratio is None:
            reasons.append("aucun historique de merge exploitable")
        return ProcessDetection(
            key="unknown",
            label=PROFILE_LABELS["unknown"],
            confidence=best_score,
            detected=False,
            signals=tuple(observed),
            reasons=tuple(reasons or ["signaux insuffisants pour distinguer un profil"]),
            scores=scores,
        )

    label = PROFILE_LABELS[best_key]
    if best_key == "github_flow" and semver_tags:
        label = "GitHub Flow + releases"
    return ProcessDetection(
        key=best_key,
        label=label,
        confidence=best_score,
        detected=True,
        signals=tuple(observed),
        reasons=(),
        scores=scores,
    )


def detect_repository_process(repository_path: str | Path) -> ProcessDetection:
    return detect_process(collect_git_signals(repository_path))
