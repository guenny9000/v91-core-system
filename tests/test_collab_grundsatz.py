"""Pins the core boundaries of docs/V91-MAX-BEST-ZUSAMMENARBEIT.md.

Verhindert stilles Aushohlen: die Nummer-uebergreifenden Kerngrenzen
keine neuen Rechte, keine Einschraenkung Freiwilliger, keine
Toetung/Gewalt und Schichten-Trennung fuer Beitraege muessen im
Dokument stehen bleiben.
"""
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "V91-MAX-BEST-ZUSAMMENARBEIT.md"


class CollaborationPrincipleDocTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(DOC.exists(), "docs/V91-MAX-BEST-ZUSAMMENARBEIT.md fehlt.")
        self.text = DOC.read_text(encoding="utf-8")

    def test_six_owner_principles_present_verbatim_headings(self):
        for heading in (
            "1. AUTARKIE FÖRDERN",
            "2. KOOPERATION ERMÖGLICHEN",
            "3. MENSCHENLEBEN SCHÜTZEN",
            "4. WIRKUNG MAXIMIEREN",
            "5. BALLAST REDUZIEREN",
            "6. WAHRHEIT SICHERN",
        ):
            self.assertIn(heading, self.text)

    def test_grants_no_new_rights(self):
        self.assertIn("AUTORISIERUNG != BESCHLUSS != DURCHFÜHRUNG", self.text)
        self.assertIn("Er erteilt\nniemandem neue Rechte", self.text)
        self.assertIn("erzeugt keine Betriebszustände, Rechte oder", self.text)

    def test_voluntary_participants_not_restricted(self):
        self.assertIn("Keine unnötigen Einschränkungen für freiwillige", self.text)
        self.assertIn("FREIWILLIGKEIT != ZUGRIFF", self.text)

    def test_life_protection_boundary(self):
        self.assertIn("Keine Tötung, Gewalt, gezielte Gefährdung", self.text)
        self.assertIn("Notstand/Notwehr nur zum", self.text)

    def test_layer_separation_for_all_contributors(self):
        self.assertIn("für ALLE beteiligten Modelle und Sessions", self.text)
        self.assertIn("CI 2/2 success am exakten Head", self.text)
        self.assertIn("Blob-Gate vor jedem Commit", self.text)
        self.assertIn("werden zurückgewiesen", self.text)
        self.assertIn("nie Evidenz", self.text)

    def test_collision_rule_references_binding_long_versions(self):
        self.assertIn("Kollisionsregel", self.text)
        for ref in ("Gelöbnis", "Audit-Kern", "GBM-001", "Network-Policy"):
            self.assertIn(ref, self.text)

    def test_honest_limits_documented_not_operating(self):
        self.assertIn("RICHTLINIE DOKUMENTIERT - NICHT DEPLOYED", self.text)
        self.assertIn("MODELL != REALITÄT", self.text)


if __name__ == "__main__":
    unittest.main()
