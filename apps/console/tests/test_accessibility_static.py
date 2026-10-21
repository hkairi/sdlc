"""Contrôle statique d'accessibilité des 12 vues React."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WEB = REPO_ROOT / "apps" / "console" / "web"

VIEWS = (
    "Overview.tsx",
    "Features.tsx",
    "Gates.tsx",
    "Review.tsx",
    "Deployments.tsx",
    "Team.tsx",
    "Process.tsx",
    "Security.tsx",
    "PerformanceData.tsx",
    "Agents.tsx",
    "Documents.tsx",
    "Configuration.tsx",
)


class AccessibilityStaticTest(unittest.TestCase):
    def test_langue_lien_evitement_et_landmark(self) -> None:
        index = (WEB / "index.html").read_text(encoding="utf-8")
        app = (WEB / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn('lang="fr"', index)
        self.assertIn("Aller au contenu principal", app)
        self.assertIn('id="main-content"', app)

    def test_focus_visible_et_mouvement_reduit(self) -> None:
        css = (WEB / "src" / "styles.css").read_text(encoding="utf-8")
        for selector in ("a:focus-visible", "button:focus-visible", "input:focus-visible"):
            self.assertIn(selector, css)
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn("animation-duration", css)
        self.assertIn("transition-duration", css)

    def test_les_douze_vues_ont_un_titre_et_une_region(self) -> None:
        for name in VIEWS:
            source = (WEB / "src" / name).read_text(encoding="utf-8")
            self.assertIn("aria-labelledby", source, name)
            self.assertIn("<section", source, name)
            self.assertIn("<h2", source, name)

    def test_tableaux_avec_caption(self) -> None:
        for name in (
            "Features.tsx",
            "Gates.tsx",
            "Review.tsx",
            "Deployments.tsx",
            "Team.tsx",
            "Security.tsx",
            "PerformanceData.tsx",
            "Agents.tsx",
            "Documents.tsx",
            "Configuration.tsx",
        ):
            source = (WEB / "src" / name).read_text(encoding="utf-8")
            self.assertIn("<caption>", source, name)
            self.assertIn('scope="col"', source, name)

    def test_mises_a_jour_dynamiques_annoncees(self) -> None:
        for name in VIEWS:
            source = (WEB / "src" / name).read_text(encoding="utf-8")
            self.assertIn("aria-live", source, name)
        log = (WEB / "src" / "RunLog.tsx").read_text(encoding="utf-8")
        self.assertIn('aria-live="polite"', log)
        self.assertNotIn("dangerouslySetInnerHTML", log)


if __name__ == "__main__":
    unittest.main()
