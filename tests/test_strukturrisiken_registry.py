"""Pins the core boundaries of docs/V91-MAX-BEST-STRUKTURRISIKEN-REGISTRY.md.

Die Registry benennt strukturelle Belastungen einzeln und vollstaendig.
Dieser Test verhindert stilles Aushoehlen: die vier Grenzregeln, alle
vierzehn Eintraege mit Primaerquellen und die Betriebsklasse (kein Handeln
gegen Personen oder Fremdsysteme, KI toetet nicht) muessen im Dokument
stehen bleiben.
"""
import re
import unittest
from pathlib import Path

DOC = (Path(__file__).resolve().parents[1] / "docs"
       / "V91-MAX-BEST-STRUKTURRISIKEN-REGISTRY.md")


class StrukturRisikenRegistryTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(DOC.exists(),
                        "docs/V91-MAX-BEST-STRUKTURRISIKEN-REGISTRY.md fehlt.")
        self.text = DOC.read_text(encoding="utf-8")

    def test_all_fourteen_entries_present_numbered(self):
        found = re.findall(r"^### (\d{2}) ", self.text, re.M)
        self.assertEqual(found, [f"{i:02d}" for i in range(1, 15)])
        for name in (
            "Lobbyismus",
            "Drehtuer",
            "Korruption",
            "Diktatur",
            "Erodierende Demokratien",
            "Zensur",
            "Desinformation",
            "Wahlmanipulation",
            "Ueberwachungsueberhang",
            "Buerokratie-Ballast",
            "Justizbeugung",
            "Informationsmonokulturen",
            "Privatjets",
            "Ruestungsspirale",
        ):
            self.assertIn(name, self.text)

    def test_every_entry_has_primary_source_https(self):
        sources = re.findall(r"Primaerquelle: (https://\S+)", self.text)
        self.assertEqual(len(sources), 14,
                         "jeder Eintrag braucht genau eine Primaerquelle")
        for src in sources:
            self.assertTrue(src.startswith("https://"))

    def test_boundary_rules_verbatim(self):
        for anchor in (
            "SYSTEMEBENE != PERSONENEBENE",
            "POSITION != RECHTSLAGE",
            "REVIEW != ENTSCHEIDUNG",
            "BEHAUPTUNG != BELEGT",
        ):
            self.assertIn(anchor, self.text)

    def test_no_namings_of_individuals(self):
        # Strukturen ja, Personen nie: kein Abschnitt darf
        # Kampagnen-Sprache enthalten.
        for banned in ("Schwarze Liste", "Ausschalten von",
                       "Anklage gegen"):
            self.assertNotIn(banned, self.text)
        self.assertIn("niemals Einzelpersonen", self.text)
        self.assertIn("keine Kampagne gegen Menschen", self.text)

    def test_operating_boundary_no_destruction(self):
        self.assertIn("keine Zerstoerung", self.text)
        self.assertIn("kein Cyberangriff", self.text)
        self.assertIn("KI toetet nicht", self.text)
        self.assertIn("Der digitale Raum vergroessert", self.text)

    def test_not_a_decision_document(self):
        self.assertIn("KEINE ENTSCHEIDUNGEN", self.text)
        self.assertIn("zieht keine Sanktion", self.text)
        self.assertIn("KEIN_INDIKATOR", self.text)

    def test_collision_rule_refs_binding_long_versions(self):
        self.assertIn("Kollisionsregel", self.text)
        for ref in ("Geluebnis", "GBM-001", "Network-Policy",
                    "Zusammenarbeit"):
            self.assertIn(ref, self.text)

    def test_document_is_ascii_pure(self):
        for char in self.text:
            self.assertTrue(ord(char) < 128,
                            f"non-ASCII character {char!r} im Dokument")


if __name__ == "__main__":
    unittest.main()
