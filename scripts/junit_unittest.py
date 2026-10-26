#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JUnit XML pour `unittest` (bibliothèque standard uniquement).

Exécute `unittest discover` et écrit un rapport JUnit XML conforme au contrat
`reports/junit/*.xml` du § 10 de la spécification (lisible par les outils de CI
et le tableau de bord), sans dépendance externe.

Usage :
    scripts/junit_unittest.py [chemin-xml] [start-dir]

Exemple :
    scripts/junit_unittest.py reports/junit/unittest.xml tests

Sortie : le fichier XML demandé (défaut `reports/junit/unittest.xml`).
Code de sortie : 0 si tous les tests passent, 1 sinon (reste bloquant dans
`scripts/ci.sh`).
"""

from __future__ import annotations

import sys
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


class _JUnitResult(unittest.TextTestResult):
    """Enregistre chaque cas (nom, classe, statut, durée, message) pour le XML."""

    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.cases: list[tuple[unittest.TestCase, str, str | None, float]] = []

    def startTest(self, test):
        self._started = time.perf_counter()
        super().startTest(test)

    def _record(self, test, status, message):
        self.cases.append((test, status, message, time.perf_counter() - self._started))

    def addSuccess(self, test):
        self._record(test, "success", None)
        super().addSuccess(test)

    def addFailure(self, test, err):
        self._record(test, "failure", self._exc_info_to_string(err, test))
        super().addFailure(test, err)

    def addError(self, test, err):
        self._record(test, "error", self._exc_info_to_string(err, test))
        super().addError(test, err)

    def addSkip(self, test, reason):
        self._record(test, "skipped", reason)
        super().addSkip(test, reason)


def _first_line(text: str | None) -> str:
    if not text:
        return ""
    return text.splitlines()[0]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    xml_path = argv[1] if len(argv) > 1 else "reports/junit/unittest.xml"
    start_dir = argv[2] if len(argv) > 2 else "tests"

    suite = unittest.defaultTestLoader.discover(start_dir=start_dir)
    result = _JUnitResult(sys.stderr, True, 1)
    result.startTestRun()
    suite.run(result)
    result.stopTestRun()

    suite_el = ET.Element(
        "testsuite",
        {
            "name": "unittest",
            "tests": str(result.testsRun),
            "failures": str(len(result.failures)),
            "errors": str(len(result.errors)),
            "skipped": str(len(result.skipped)),
            "time": f"{sum(case[3] for case in result.cases):.3f}",
        },
    )
    for test, status, message, elapsed in result.cases:
        case = ET.SubElement(
            suite_el,
            "testcase",
            {
                "name": test._testMethodName,
                "classname": f"{test.__class__.__module__}.{test.__class__.__name__}",
                "time": f"{elapsed:.3f}",
            },
        )
        if status == "failure":
            ET.SubElement(case, "failure", message=_first_line(message)).text = message
        elif status == "error":
            ET.SubElement(case, "error", message=_first_line(message)).text = message
        elif status == "skipped":
            ET.SubElement(case, "skipped", message=message or "")

    Path(xml_path).parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite_el).write(xml_path, encoding="utf-8", xml_declaration=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
