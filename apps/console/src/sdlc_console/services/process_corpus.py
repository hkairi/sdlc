"""Corpus étiqueté et mesure de précision de la détection de processus."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process_detection import ProcessDetection, detect_repository_process

Detector = Callable[[str | Path], ProcessDetection]


@dataclass(frozen=True)
class CorpusCase:
    repository: str
    expected: str
    detected: str
    label: str
    confidence: float
    correct: bool


def _load_labels(root: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    manifest = root / "labels.json"
    if manifest.is_file():
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, Mapping):
            labels.update(
                {
                    str(key): str(value)
                    for key, value in payload.items()
                    if isinstance(value, str)
                }
            )
    return labels


def _case_label(path: Path) -> str | None:
    for candidate in (path / "label.json", path / ".process-label"):
        if not candidate.is_file():
            continue
        try:
            if candidate.suffix == ".json":
                payload = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(payload, Mapping):
                    value = payload.get("profile") or payload.get("label")
                    return str(value) if value else None
            else:
                value = candidate.read_text(encoding="utf-8").strip()
                return value or None
        except (OSError, json.JSONDecodeError):
            return None
    return None


def evaluate_corpus(
    root: str | Path,
    *,
    detector: Detector = detect_repository_process,
    threshold: float = 0.8,
) -> dict[str, Any]:
    """Évalue chaque dépôt étiqueté et calcule le taux de classification."""
    corpus = Path(root)
    if not corpus.is_dir():
        raise ValueError(f"corpus introuvable : {corpus}")
    labels = _load_labels(corpus)
    cases: list[CorpusCase] = []
    for path in sorted(item for item in corpus.iterdir() if item.is_dir()):
        expected = labels.get(path.name) or _case_label(path)
        if not expected:
            continue
        detection = detector(path)
        cases.append(
            CorpusCase(
                repository=path.name,
                expected=expected,
                detected=detection.key,
                label=detection.label,
                confidence=detection.confidence,
                correct=expected == detection.key,
            )
        )
    total = len(cases)
    correct = sum(1 for case in cases if case.correct)
    accuracy = round(correct / total, 4) if total else 0.0
    return {
        "corpus": str(corpus),
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "threshold": threshold,
        "passed": bool(total and accuracy >= threshold),
        "cases": [
            {
                "repository": case.repository,
                "expected": case.expected,
                "detected": case.detected,
                "label": case.label,
                "confidence": case.confidence,
                "correct": case.correct,
            }
            for case in cases
        ],
        "failures": [
            {
                "repository": case.repository,
                "expected": case.expected,
                "detected": case.detected,
            }
            for case in cases
            if not case.correct
        ],
    }
