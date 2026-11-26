"""Tests fuer den Imperialen Bericht 26.11.2026 (Lagebericht,
Universum-Frage, Audit Edition Ultra Extended).

Pinnen nach dem Kodex-Muster (#533/#566/#578): Doku existiert und
ist klein, Kernmarker wortgenau, KEINE Umsetzungsbehauptung,
Verweis-Ziele existieren, ASCII-pure, ehrliche Grenzen und
Negativliste dokumentiert. BERICHT != BEWEIS, ERZAEHLUNG != VERTRAG.
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "V91-IMPERIAL-BERICHT-2026-11-26.md"


class ImperialBerichtDokuTest(unittest.TestCase):
    def test_doc_exists_and_small(self):
        self.assertTrue(DOC.exists(), "Imperialer Bericht fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024,
                        "Doku ueberschreitet die 8-KiB-Grenze")

    def test_status_markiert(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("LAGEBERICHT", text)
        self.assertIn("KEIN VERTRAG", text)
        self.assertIn("KEINE NEUE BEFUGNIS", text)
        self.assertIn("NO_DUPLICATE_SYSTEMS", text)
        self.assertIn("BETREIBER-AUFTRAG", text)

    def test_universum_antwort_epistemisch(self):
        text = DOC.read_text(encoding="utf-8")
        for needle in (
            "NICHT GEPRUEFT",
            "NICHT BELEGT BEDEUTET NICHT FALSCH",
            "HALB VERIFIZIERT IST UNVERIFIZIERT",
            "UNKNOWN != PASS",
            "BERICHT != BEWEIS",
        ):
            self.assertIn(needle, text, needle)

    def test_kein_gesamturteil_behauptet(self):
        text = DOC.read_text(encoding="utf-8")
        flat = re.sub(r"\s+", " ", text)
        self.assertIn("waere Fiktion und wird NICHT behauptet", flat)
        self.assertIn("keine Gesamtaussage", flat)

    def test_blockieren_isolieren_ehrlich(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("V91 blockiert KEINE fremden Systeme", text)
        self.assertIn("ISOLATE_NOT_DESTROY", text)
        self.assertIn("NIEMALS gegen Menschenleben", text)
        self.assertIn("FREIGABE != BERECHTIGUNG", text)
        self.assertIn("Abschalt-Verfuegung (#579", text)

    def test_beitrag_gemesessen_mit_grenze(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("WIRKUNG AUSSEN != REGISTRIEREN INNEN", text)
        self.assertIn("3/3 success am exakten Head", text)
        self.assertIn("Issue #101/#103", text)

    def test_keine_umsetzungsbehauptung(self):
        text = DOC.read_text(encoding="utf-8")
        for forbidden in ("erfolgreich implementiert",
                          "finaler Zustand erreicht",
                          "Mission accomplished",
                          "Universum ist in Ordnung"):
            self.assertNotIn(forbidden, text, forbidden)

    def test_negativliste(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("Negativliste", text)
        self.assertIn("keine neuen Befugnisse", text)
        self.assertIn("keine erfundenen Zahlen", text)
        self.assertIn("veraendert KEINEN Systemzustand", text)

    def test_offene_fronten_genannt(self):
        text = DOC.read_text(encoding="utf-8")
        for needle in ("#239", "#262", "#101", "#103", "#23",
                       "#590", "SCRIPTED != INSTALLED",
                       "VERTRAG != LAUFENDER VERBUND"):
            self.assertIn(needle, text, needle)

    def test_verweis_ziele_existieren(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("docs/V91-WELTLAGE-REVIEW-2026-11-25.md", text)
        self.assertTrue((ROOT / "docs" /
                         "V91-WELTLAGE-REVIEW-2026-11-25.md").exists())
        self.assertIn("verbund_arbeitszyklus", text)
        self.assertTrue((ROOT / "controller" /
                         "verbund_arbeitszyklus.py").exists())

    def test_ascii_pure(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertEqual([], [c for c in text if ord(c) > 127],
                         "Doku muss ASCII-pure sein")


if __name__ == "__main__":
    unittest.main()
