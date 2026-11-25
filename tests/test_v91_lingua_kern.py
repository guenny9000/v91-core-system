"""Tests fuer den V91-LINGUA-KERN (Stufe 2: gemeinsame
Protokollsprache, ENTWURF). Kodex-Muster: Doku existiert und ist
klein, ASCII-pure, Subordination ans Erkenntnis- und
Revisionsprotokoll #569 gepinnt, fuenf Betreiber-Eigenschaften,
hartes Regelwerk (binaere Wahrheit, UNK explizit, kein
Informationsverlust, Deckung nur Zaehlung), Nachrichtenformat-
ENTWURF mit fail-closed Fehlerregeln, Stufenplan, KEINE
Umsetzungsbehauptung, Sprache schafft keine Befugnis."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "V91-LINGUA-KERN.md"
PROTO = ROOT / "docs" / "V91-ERKENNTNIS-UND-REVISIONSPROTOKOLL.md"
GLYPHEN = ROOT / "docs" / "V91-ERKENNTNIS-GLYPHEN-ANHANG.md"


class V91LinguaKernTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_doc_exists_and_small(self):
        self.assertTrue(DOC.is_file(), "Kern fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024)

    def test_ascii_pure(self):
        self.assertEqual([], [c for c in self.text if ord(c) > 127])

    def test_subordination_ans_protokoll(self):
        self.assertIn("KEIN zweites Marker-System", self.text)
        self.assertIn("SUBORDINIERT", self.text)
        self.assertIn("#569", self.text)
        self.assertTrue(PROTO.is_file(), "Protokoll #569 muss existieren")
        self.assertTrue(GLYPHEN.is_file(), "Anhang #570 muss existieren")

    def test_fuenf_eigenschaften_verbindlich(self):
        for needle in ("SICHERHEIT", "EFFIZIENZ",
                      "VOLLSTAENDIGKEIT", "KOMPATIBILITAET",
                      "ERWEITERBARKEIT"):
            self.assertIn(needle, self.text, needle)
        self.assertIn("SICHERHEIT HAT VORRANG VOR EFFIZIENZ", self.text)
        self.assertIn("append-only", self.text)

    def test_wahrheit_binaer_unk_explicit(self):
        self.assertIn("WAHRHEIT IST BINAER PRO AUSSAGE", self.text)
        self.assertIn("HALB VERIFIZIERT IST UNVERIFIZIERT", self.text)
        self.assertIn("UNBEKANNT MUSS EXPLIZIT SEIN", self.text)
        self.assertIn("KEINE Ersetzung durch Interpretation", self.text)

    def test_kein_informationsverlust(self):
        self.assertIn("KEIN INFORMATIONSVERLUST FUR KUERZE", self.text)
        self.assertIn("nur Redundanz", self.text)
        self.assertIn("Pflichtfelder", self.text)

    def test_deckung_ist_nur_zaehlung(self):
        self.assertIn("ANZEIGE != BELEG", self.text)
        self.assertIn("DECKUNG IST NUR ZAEHLUNG", self.text)
        self.assertIn("NIEMALS Wahrheitsgrad", self.text)

    def test_wortkern_bindet_569_marker(self):
        for needle in ("| VER |", "| UNV |", "| DET |", "| MEAS |",
                       "| OBS |", "| REV |", "| REMEAS |", "| EFF |",
                       "| ACT |", "| SAFE |", "| HOLD |", "| REC |",
                       "| COOP |", "| UNK |", "| DISPUTED |"):
            self.assertIn(needle, self.text, needle)
        self.assertIn("= Marker VER (#569)", self.text)

    def test_nachrichtenformat_entwurf(self):
        for needle in ("SCHLUESSEL:WERT", "GENAU EIN Schluessel",
                       "TASK", "STATE", "EVID", "NEXT",
                       "TASK:042", "STATE:UNV", "EVID:0/4",
                       "GATE:HOLD", "Illustration, KEINE Norm"):
            self.assertIn(needle, self.text, needle)

    def test_fehlerregeln_fail_closed(self):
        for needle in ("FAIL-CLOSED", "UNGUELTIG",
                       "Pflichtfeld => UNGUELTIG",
                       "Unbekannter Schluessel",
                       "Doppelter Schluessel",
                       "Behauptung != Beleg"):
            self.assertIn(needle, self.text, needle)

    def test_stufenplan_pinnt(self):
        for needle in ("Stufe 1", "Stufe 2", "Stufe 3", "OFFEN",
                       "ERLEDIGT", "Betreiber-Autorisierung"):
            self.assertIn(needle, self.text, needle)

    def test_keine_umsetzungsbehauptung(self):
        for forbidden in ("erfolgreich implementiert",
                          "bereits umgesetzt", "Parser ist aktiv",
                          "finaler Zustand erreicht"):
            self.assertNotIn(forbidden, self.text, forbidden)
        self.assertIn("DOKUMENTIERT != IMPLEMENTIERT", self.text)

    def test_sprache_ist_keine_befugnis(self):
        self.assertIn("SPRACHE SCHAFFT KEINE BEFUGNIS", self.text)
        self.assertIn("allowlist-pflichtig", self.text)
        self.assertIn("Governance-Gate #96", self.text)


if __name__ == "__main__":
    unittest.main()
