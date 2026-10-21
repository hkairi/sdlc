"""Tests du corpus de processus et de la commande de mesure."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sdlc_console.cli import main
from sdlc_console.services.process_corpus import evaluate_corpus
from sdlc_console.services.process_detection import ProcessDetection


def _detection(key: str, label: str = "") -> ProcessDetection:
    return ProcessDetection(
        key=key,
        label=label or key,
        confidence=0.8,
        detected=True,
        signals=(),
        reasons=(),
        scores={},
    )


class ProcessCorpusTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.corpus = self.root / "corpus"
        self.corpus.mkdir()
        (self.corpus / "a").mkdir()
        (self.corpus / "b").mkdir()
        (self.corpus / "labels.json").write_text(
            json.dumps({"a": "git_flow", "b": "github_flow"}),
            encoding="utf-8",
        )

    def test_precision_et_echecs(self) -> None:
        detections = {"a": _detection("git_flow"), "b": _detection("git_flow")}
        result = evaluate_corpus(
            self.corpus,
            detector=lambda path: detections[path.name],
        )
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["correct"], 1)
        self.assertEqual(result["accuracy"], 0.5)
        self.assertFalse(result["passed"])
        self.assertEqual(result["failures"][0]["repository"], "b")

        detections["b"] = _detection("github_flow")
        passed = evaluate_corpus(
            self.corpus,
            detector=lambda path: detections[path.name],
        )
        self.assertEqual(passed["accuracy"], 1.0)
        self.assertTrue(passed["passed"])

    def test_cli_corpus_et_rapport(self) -> None:
        output = self.root / "reports" / "corpus.json"
        code = main(
            [
                "process",
                "corpus",
                str(self.corpus),
                "--output",
                str(output),
            ]
        )
        # Sans dépôt Git, les deux cas sont « non identifiable » et ne
        # correspondent pas aux labels : la commande signale l'échec.
        self.assertEqual(code, 1)
        self.assertTrue(output.is_file())
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["total"], 2)


if __name__ == "__main__":
    unittest.main()
