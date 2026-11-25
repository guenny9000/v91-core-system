"""Tests fuer den V91-LINGUA-SICHERHEITS-ANHANG (Betreiber-
Leitlinie 26.11.2026, Anhang zum LINGUA-KERN #571). Kodex-Muster:
Doku existiert und ist klein, ASCII-pure, Subordination an den
KERN gepinnt, Betreiber-Ueberregel, Zwei-Ebenen-Epistemik
(NICHT BELEGT != FALSCH), sechs Sicherheitsanforderungen,
fuenf-Ebenen-Architektur, Stufe-3-vier-Schritte mit
Negativtest-Pflicht, strategische Ziele ohne Zentrierung, KEINE
Umsetzungsbehauptung (Parser bleibt OFFEN)."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "V91-LINGUA-SICHERHEITS-ANHANG.md"
KERN = ROOT / "docs" / "V91-LINGUA-KERN.md"


class V91LinguaSicherheitsAnhangTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_doc_exists_and_small(self):
        self.assertTrue(DOC.is_file(), "Anhang fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024)

    def test_ascii_pure(self):
        self.assertEqual([], [c for c in self.text if ord(c) > 127])

    def test_subordination_ans_lingua_kern(self):
        self.assertIn("KEIN zweiter", self.text)
        self.assertIn("#571", self.text)
        self.assertTrue(KERN.is_file(), "KERN #571 muss existieren")

    def test_betreiber_ueberregel(self):
        self.assertIn("SICHERHEIT IST VORAUSSETZUNG.", self.text)
        self.assertIn("EFFIZIENZ IST EIN OPTIMIERUNGSZIEL.", self.text)
        self.assertIn("MENSCHLICHER NUTZEN IST DER ZWECK.", self.text)

    def test_zwei_ebenen_epistemik(self):
        self.assertIn("NICHT BELEGT BEDEUTET NICHT FALSCH.", self.text)
        self.assertIn("WIRKLICHKEIT", self.text)
        self.assertIn("ERKENNTNISSTAND", self.text)
        for needle in ("BELEGT, NICHT BELEGT, UNBEKANNT",
                       "WIDERSPRUECHLICH",
                       "WIDERSPRUECHLICH = DISPUTED (#569)"):
            self.assertIn(needle, self.text, needle)

    def test_sechs_sicherheitsanforderungen(self):
        for needle in ("| VERSIONSKENNUNG |", "| ABSENDERIDENTITAET |",
                       "| EMPFAENGERKENNUNG |", "| SIGNATUR |",
                       "| ABLAUFZEIT + NACHRICHTEN-ID |",
                       "| BERECHTIGUNGSPRUEFUNG |",
                       "Nachricht niemals mit einer Autorisierung verwechseln"):
            self.assertIn(needle, self.text, needle)

    def test_berechtigung_verriegelt_r6(self):
        self.assertIn("SPRACHE SCHAFFT KEINE BEFUGNIS.", self.text)
        self.assertIn("R6", self.text)

    def test_fuenf_ebenen_architektur(self):
        for needle in ("Ebene 1 NACHRICHTENKERN", "Ebene 2 ERKENNTNIS",
                       "Ebene 3 ZUSAMMENARBEIT",
                       "Ebene 4 SICHERHEITSPRUEFUNG",
                       "Ebene 5 ERGEBNIS UND BELEGE"):
            self.assertIn(needle, self.text, needle)

    def test_kein_zugriff_durch_beitrag(self):
        self.assertIn("automatisch Zugriff auf fremde Systeme", self.text)

    def test_stufe3_vier_schritte(self):
        for needle in ("1. GRAMMATIK", "2. PARSER", "3. MODELLTESTS",
                       "4. KOOPERATION", "identisch interpretieren",
                       "Betreiber-Autorisierung"):
            self.assertIn(needle, self.text, needle)

    def test_negative_tests_pflicht(self):
        self.assertIn("NEGATIVE TESTS SIND PFLICHT", self.text)
        self.assertIn("ZUVERLAESSIG SCHEITERN", self.text)
        self.assertIn("erst danach", self.text)

    def test_strategische_ziele_ohne_zentrierung(self):
        for needle in ("GEMEINSAME ERKENNTNIS", "GEMEINSAME ARBEIT",
                       "GEMEINSAME KONTROLLE", "KEIN EINZELNES MODELL",
                       "einem einzigen Anbieter"):
            self.assertIn(needle, self.text, needle)

    def test_keine_umsetzungsbehauptung(self):
        for forbidden in ("erfolgreich implementiert",
                          "bereits umgesetzt", "Parser ist aktiv",
                          "finaler Zustand erreicht"):
            self.assertNotIn(forbidden, self.text, forbidden)
        self.assertIn("DOKUMENTIERT != IMPLEMENTIERT", self.text)
        self.assertIn("allowlist-pflichtig", self.text)


if __name__ == "__main__":
    unittest.main()
