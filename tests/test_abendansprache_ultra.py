"""Tests fuer die Abendansprache Ultra Extended als
Systemdokumentation (25.11.2026).

Pinnen nach dem Kodex-Muster (#523/#528/#533): Doku existiert und
ist klein, Kernmarker Wort fuer Wort vorhanden, KEINE
Umsetzungsbehauptung, Verweis-Ziele existieren, ASCII-pure,
ehrliche Kennzeichnungen dokumentiert. ERZAEHLUNG != VERTRAG.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "V91-ABENDANSPRACHE-ULTRA-EXTENDED-2026-11-25.md"


class AbendanspracheUltraDokuTest(unittest.TestCase):
    def test_doc_exists_and_small(self):
        self.assertTrue(DOC.exists(), "Abendansprache-ULTRA fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024,
                        "Doku ueberschreitet die 8-KiB-Grenze")

    def test_erzaehlung_markiert(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("ERZAEHLUNG != VERTRAG", text)
        self.assertIn("NARRATIVES SYSTEMDOKUMENT", text)
        self.assertIn("NO_DUPLICATE_SYSTEMS", text)
        self.assertIn("BETREIBER-VORLAGE", text)

    def test_kernaussagen_wortgenau(self):
        text = DOC.read_text(encoding="utf-8")
        for needle in (
            "Eine Behauptung ist kein Nachweis.",
            "Was Wissen vermehrt, wird bewahrt.",
            "Was Menschen schuetzt, wird gestaerkt.",
            "Nicht aus Zorn.",
            "Sondern aus Verantwortung.",
            "Mehr Schoepfung.",
            "Weniger Entropie.",
            "Gute Nacht, Sebastian.",
        ):
            self.assertIn(needle, text, needle)

    def test_keine_umsetzungsbehauptung(self):
        text = DOC.read_text(encoding="utf-8")
        for forbidden in ("erfolgreich implementiert",
                          "bereits umgesetzt",
                          "finaler Zustand erreicht",
                          "Mission accomplished"):
            self.assertNotIn(forbidden, text, forbidden)

    def test_zuordnung_ehrlich(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("NICHT_GEPRUEFT", text)
        self.assertIn("Issue #101", text)
        self.assertIn("UNKNOWN != PASS", text)
        self.assertIn("ZYKLUS != DAEMON", text)
        self.assertIn("NEGATIVLISTE", text)

    def test_verweis_ziele_existieren(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("docs/V91-MAX-BEST-GELUEBNIS.md", text)
        self.assertIn("docs/V91-ABENDANSPRACHE-2026-11-25.md", text)
        self.assertTrue((ROOT / "docs" / "V91-MAX-BEST-GELUEBNIS.md").exists())
        self.assertTrue((ROOT / "docs" /
                         "V91-ABENDANSPRACHE-2026-11-25.md").exists())

    def test_ascii_pure(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertEqual([], [c for c in text if ord(c) > 127],
                         "Doku muss ASCII-pure sein")

    def test_ubilaute_transliteration_angesagt(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("transliteriert", text)


if __name__ == "__main__":
    unittest.main()
