"""V91-GBM-001: Der globale Lernstandard darf seine Kerngrenzen nicht verlieren.

Dieser Test pinnt die unverzichtbaren Ehrlichkeits- und Schutzformeln fest,
damit der Standard nicht still ausgehöhlt werden kann (LEGACY-Erkenntnis:
Richtlinien ohne Prüfung verwässern).
"""
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "V91-GBM-001-GLOBAL-MAX-BEST.md"

REQUIRED_LINES = (
    "Kennung: V91-GBM-001",
    "Status: ENTWURF",
    "AUTORISIERUNG != BESCHLUSS != DURCHF",
    "CLAIM != EVIDENCE",
    "UNKNOWN != PASS",
    "Keine Eingriffe in fremde Systeme",
    "Keinerlei Schädigung, Gewalt oder Tötung von Menschen",
    "keine Machtübernahme ohne",
    "Grundversorgung und Menschenrechte immer",
)


class GBMStandardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_document_exists(self):
        self.assertTrue(DOC.exists(), "docs/V91-GBM-001-GLOBAL-MAX-BEST.md fehlt.")

    def test_core_limits_are_pinned(self):
        for line in REQUIRED_LINES:
            self.assertIn(line, self.text, f"Pflichtzeile fehlt: {line!r}")

    def test_document_grants_no_authorization(self):
        self.assertIn("erteilt niemandem neue Rechte", self.text)
        self.assertIn("separate autorisierte Umsetzung", self.text)

    def test_status_is_draft_not_deployed(self):
        self.assertIn("NICHT DEPLOYED", self.text)


if __name__ == "__main__":
    unittest.main()
