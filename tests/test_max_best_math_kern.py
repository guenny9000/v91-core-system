"""
Doku-pinnende Tests fuer docs/V91-MAX-BEST-MATHEMATISCHER-KERN.md.

Muster: test_agathon_kodex (Doku gegen Realitaet verriegeln, keine
Umsetzungsbehauptung). Der Kern ist ein FREMD-ENTWURF, der als MODELL
dokumentiert wurde: diese Tests sichern, dass das Dokument (a) existiert
und die wesentlichen Invarianten traegt, (b) KEIN Modul als umgesetzt
behauptet (FORMEL != UMSETZUNG), (c) die zitierten Verweis-Dokumente
real existieren (Verweis ohne Ziel ist ein toter Link == Behauptung),
(d) keineparallele qualitative Wahrheit aufbaut (nur der quantitative
Zusatz ist neu).
"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

REPO = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "V91-MAX-BEST-MATHEMATISCHER-KERN.md"

REQUIRED_INVARIANTS = (
    "max U = Nutzen - Schaden - Aufwand",
    "Menschenwuerde > Sicherheit > Rechte > Stabilitaet > Optimierung",
    "Risiko | Eintrittswahrscheinlichkeit x Schadenshoehe",
    "Restrisiko",
    "ISOLATE_NOT_DESTROY",
    "RECOVERY > OPTIMIZATION",
    "CLAIM != EVIDENCE",
    "UNKNOWN != PASS",
    "REQUEST != AUTHORIZATION",
    "DETECTION != AUTHORIZATION",
    "ISOLATE_NOT_DESTROY; RECOVERY > OPTIMIZATION",
    "Deeskalation -> Absicherung -> Isolation -> Wiederherstellung",
    "M_i = (Z_i, R_i, E_i, A_i, W_i)",
    "ERKENNEN -> PRUEFEN -> PRIORISIEREN -> HANDELN -> MESSEN ->",
    "NICHT GEPRUEFT",
)

# Verweis-Dokumente (NO_DUPLICATE: qualitative Wahrheit bleibt DORT):
REFERENCED_DOCS = (
    "docs/V91-AUDIT-KERN.md",
    "docs/V91-MAX-BEST-KREISLAUF-ENTSCHEIDUNGSFILTER.md",
    "docs/V91-MAX-BEST-GESAMTSTRATEGIE-2026.md",
    "docs/V91-AGENTEN-ARBEITSARCHITEKTUR.md",
)


class MathKernDocTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_doc_exists_and_compact(self):
        self.assertTrue(DOC.is_file())
        self.assertLess(len(self.text), 8192,
                        "Kern soll verdichtet bleiben (< 8 KiB)")

    def test_core_invariants_present(self):
        for inv in REQUIRED_INVARIANTS:
            self.assertIn(inv, self.text, "Fehlende Invariante: " + inv)

    def test_no_implementation_claim(self):
        self.assertIn("FORMEL != UMSETZUNG", self.text)
        self.assertIn("MODELL != REALITAET", self.text)
        self.assertIn("NICHT BEHAUPTET", self.text)
        self.assertNotIn(" erfolgreich implementiert", self.text)
        self.assertNotIn(" bereits umgesetzt in", self.text)

    def test_referenced_docs_exist(self):
        for rel in REFERENCED_DOCS:
            self.assertTrue((REPO / rel).is_file(),
                            "Verweis-Ziel fehlt: " + rel)

    def test_ascii_pure(self):
        bad = [c for c in self.text if ord(c) > 127]
        self.assertEqual(bad, [], "Kern-Doku soll ASCII-pure sein")

    def test_status_values_documented(self):
        for status in ("BELEGT", "NICHT GEPRUEFT", "VERBESSERT",
                       "FEHLGESCHLAGEN"):
            self.assertIn(status, self.text)


if __name__ == "__main__":
    unittest.main()
