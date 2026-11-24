"""
Doku-pinnende Tests fuer docs/V91-MAX-BEST-MODULBEISPIELE.md.

Muster: test_max_best_math_kern (Doku gegen Realitaet verriegeln,
keine Umsetzungsbehauptung). Die Modulbeispiele fuellen die Kern-Form
M_i mit BEISPIEL-Tupeln: diese Tests sichern, dass das Dokument
(a) existiert und kompakt bleibt, (b) die Kern-Form und die
Beispiel-Modul-Tupel traegt, (c) KEIN Modul als umgesetzt behauptet
(BEISPIEL != MESSUNG), (d) die zitierten Verweis-Dokumente real
existieren, (e) KEINE Kern-Formeln dupliziert (Formeln bleiben im
Kern, NO_DUPLICATE_SYSTEMS), (f) die Nachweisblock-Schnittstelle
NICHT als Zweit-Vertrag neben den UAS-Kanon tritt.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

REPO = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "V91-MAX-BEST-MODULBEISPIELE.md"

REQUIRED_INVARIANTS = (
    "M_i = (Z_i, R_i, E_i, A_i, W_i)",
    "M_Energie = (Z, R, E, A, W)",
    "M_Digital = (Z, R, E, A, W)",
    "M_Ressourcen = (Z, R, E, A, W)",
    "BEISPIEL != MESSUNG",
    "DOKUMENTIERT != INSTALLIERT",
    "TUPEL != BETRIEB",
    "ISOLATE_NOT_DESTROY",
    "RECOVERY > OPTIMIZATION",
    "ERHALTEN > ERSETZEN",
    "Grundversorgung vor Komfort",
    "REQUEST != AUTHORIZATION",
    "CLAIM != EVIDENCE",
    "NICHT GEPRUEFT",
    "KANON == ABLEITUNG != ZWEITE_WAHRHEIT",
    "Summe(R_i) <= R_verfuegbar",
)

# Kern-Formeln duerfen hier NICHT wiederholt werden (bleiben im Kern):
KERN_FORMELN = (
    "max U = Nutzen - Schaden - Aufwand",
    "Risiko | Eintrittswahrscheinlichkeit x Schadenshoehe",
    "Restrisiko | Risiko",
)

REFERENCED_DOCS = (
    "docs/V91-MAX-BEST-MATHEMATISCHER-KERN.md",
    "docs/V91-MAX-BEST-RECHENBEISPIELE.md",
    "docs/V91-UAS-VERTRAG-KANON.md",
    "docs/V91-AUDIT-KERN.md",
    "docs/V91-ARCHITEKTUR-INDEX.md",
)

NACHWEISBLOCK_FELDER = (
    "Ziel:",
    "Messgroesse:",
    "Belegquelle:",
    "Status:",
    "Wiederherstellungspfad:",
)


class ModulbeispieleDocTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_doc_exists_and_compact(self):
        self.assertTrue(DOC.is_file())
        self.assertLess(len(self.text), 8192,
                        "Modulbeispiele sollen verdichtet bleiben (< 8 KiB)")

    def test_core_invariants_present(self):
        for inv in REQUIRED_INVARIANTS:
            self.assertIn(inv, self.text, "Fehlende Invariante: " + inv)

    def test_no_implementation_claim(self):
        self.assertIn("UMSETZUNG NICHT BEHAUPTET", self.text)
        self.assertIn("BEISPIEL != MESSUNG", self.text)
        self.assertNotIn(" erfolgreich implementiert", self.text)
        self.assertNotIn(" bereits umgesetzt in", self.text)
        self.assertNotIn(" Messwerte liegen vor", self.text)

    def test_no_kernel_formula_duplication(self):
        for formel in KERN_FORMELN:
            self.assertNotIn(formel, self.text,
                             "Kern-Formel dupliziert: " + formel)

    def test_referenced_docs_exist(self):
        for rel in REFERENCED_DOCS:
            self.assertTrue((REPO / rel).is_file(),
                            "Verweis-Ziel fehlt: " + rel)

    def test_nachweisblock_felder_defined(self):
        for feld in NACHWEISBLOCK_FELDER:
            self.assertIn(feld, self.text, "Fehlendes Feld: " + feld)
        self.assertIn("NICHT VERFUEGBAR", self.text)

    def test_status_values_documented(self):
        for status in ("BELEGT", "IN ARBEIT", "VORSCHLAG", "NICHT GEPRUEFT",
                       "NICHT VERFUEGBAR", "FEHLGESCHLAGEN", "VERBESSERT"):
            self.assertIn(status, self.text)

    def test_ascii_pure(self):
        bad = [c for c in self.text if ord(c) > 127]
        self.assertEqual(bad, [], "Beispiel-Doku soll ASCII-pure sein")


if __name__ == "__main__":
    unittest.main()
