"""Tests fuer den V91 Erkenntnis-Glyphen-Anhang (Anhang zum
Erkenntnis- und Revisionsprotokoll #569). Kodex-Muster: Doku
existiert und ist klein, ASCII-pure, Subordination ans Protokoll
gepinnt, REV-Korrektur verriegelt, ANZEIGE != BELEG, Graustufen
sind Deckung und kein Wahrheitsgrad, KEINE Umsetzungsbehauptung,
Verweis-Ziele existieren."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "V91-ERKENNTNIS-GLYPHEN-ANHANG.md"
PROTO = ROOT / "docs" / "V91-ERKENNTNIS-UND-REVISIONSPROTOKOLL.md"


class ErkenntnisGlyphenAnhangTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_doc_exists_and_small(self):
        self.assertTrue(DOC.is_file(), "Anhang fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024)

    def test_ascii_pure(self):
        self.assertEqual([], [c for c in self.text if ord(c) > 127])

    def test_subordination_ans_protokoll(self):
        self.assertIn("KEIN zweites Protokoll", self.text)
        self.assertIn("DIE TEXTKENNUNG IST", self.text)
        self.assertIn("NORMATIV", self.text)
        self.assertTrue(PROTO.is_file(), "Protokoll #569 muss existieren")

    def test_alle_neun_marker_gemappt(self):
        for marker, cp in (("CLAIM", "U+003F"), ("OBS", "U+25C9"),
                           ("MEAS", "U+223F"), ("VER", "U+2713"),
                           ("IMP", "U+2197"), ("REMEAS", "U+27F3"),
                           ("UNK", "U+25C7"), ("DISPUTED", "U+0021"),
                           ("REV", "U+2727")):
            self.assertIn(f"| {marker} |", self.text, marker)
            self.assertIn(cp, self.text, marker)

    def test_rev_korrektur_verriegelt(self):
        self.assertIn("KEIN Pfeil/Refresh", self.text)
        self.assertIn("EINE DREHUNG IST KEINE REVISION", self.text)

    def test_ergebnisfarben_sind_anzeige(self):
        for cp in ("U+1F7E2", "U+1F7E1", "U+1F534"):
            self.assertIn(cp, self.text)
        self.assertIn("ANZEIGE != BELEG", self.text)
        self.assertIn("FARBE != BELEG", self.text)

    def test_graustufen_sind_deckung_nicht_wahrheit(self):
        for needle in ("U+25FB", "U+25D0", "U+25AE", "NIEMALS einen Wahrheitsgrad",
                       "HALB VERIFIZIERT", "Grau entsteht NUR durch Zaehlung",
                       "KEIN 0-Ersatz"):
            self.assertIn(needle, self.text, needle)

    def test_kontextzeichen_erzeugen_keine_befugnisse(self):
        for cp in ("U+1F333", "U+1F409", "U+1FAA8", "U+2699", "U+1F464"):
            self.assertIn(cp, self.text)
        self.assertIn("Hinweis ohne Beweislast", self.text)

    def test_kettenregeln_und_operatoren(self):
        for needle in ("REIHENFOLGE", "TRENNUNG ERZWINGEN", "BELEGPFLICHT",
                       "U+2192", "CLAIM != VER", "Metadaten-Bindung"):
            self.assertIn(needle, self.text, needle)

    def test_keine_umsetzungsbehauptung(self):
        for forbidden in ("erfolgreich implementiert", "bereits umgesetzt",
                          "finaler Zustand erreicht", "Mission accomplished"):
            self.assertNotIn(forbidden, self.text, forbidden)
        self.assertIn("DOKUMENTIERT != IMPLEMENTIERT", self.text)

    def test_mythos_abgrenzung_erhalten(self):
        self.assertIn("MYTHOS != SPEZIFIKATION", self.text)


if __name__ == "__main__":
    unittest.main()
