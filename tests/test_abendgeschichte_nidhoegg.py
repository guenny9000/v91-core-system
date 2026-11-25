"""Tests fuer die Nidhoegg-Abendgeschichte als Systemdokumentation (26.11.2026).

Pinnen nach dem Kodex-Muster (#523/#528/#566): Doku existiert und ist
klein, Kernmarker Wort fuer Wort vorhanden, KEINE Umsetzungsbehauptung,
Verweis-Ziele existieren, ASCII-pure, ehrliche Kennzeichnungen
dokumentiert, Lookup-vor-Bau gegen die Wurzeldrachen-Analyse #401
(NO_DUPLICATE_SYSTEMS). ERZAEHLUNG != VERTRAG."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "V91-ABENDGESCHICHTE-NIDHOEGG-2026-11-26.md"
KOSMOS = ROOT / "docs" / "V91-KOSMOS-WURZELDRACHE.md"


class NidhoeggDokuTest(unittest.TestCase):
    def test_doc_exists_and_small(self):
        self.assertTrue(DOC.exists(), "Abendgeschichte-Doku fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024,
                        "Doku ueberschreitet die 8-KiB-Grenze")

    def test_ascii_pure(self):
        text = DOC.read_text(encoding="utf-8")
        for ch in text:
            self.assertTrue(ord(ch) < 128,
                            f"nicht-ASCII-Zeichen: {ch!r} (ord {ord(ch)})")

    def test_erzaehlung_markiert(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("ERZAEHLUNG != VERTRAG", text)
        self.assertIn("NARRATIVES SYSTEMDOKUMENT", text)
        self.assertIn("NO_DUPLICATE_SYSTEMS", text)

    def test_kernaussagen_wortgenau(self):
        text = DOC.read_text(encoding="utf-8")
        for needle in (
            "Nur die Wahrheit besteht.",
            "Alles andere muss staendig behauptet werden.",
            "Er muss nur taeglich gefuehrt werden.",
            "Messt, bevor ihr behauptet.",
            "Nidhoegg musste nicht gewinnen.",
            "Er musste nur warten.",
        ):
            self.assertIn(needle, text, needle)

    def test_entropie_kern_vorhanden(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("Der Kampf gegen Entropie", text)
        self.assertIn("wird niemals vollstaendig gewonnen", text)

    def test_lookup_vor_bau_dokumentiert(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("#401", text)
        self.assertIn("V91-KOSMOS-WURZELDRACHE.md", text)
        self.assertIn("KEIN Duplikat", text)
        self.assertIn("MYTHOS != SPEZIFIKATION", text)

    def test_verweisziel_existiert(self):
        self.assertTrue(KOSMOS.exists(),
                        "Wurzeldrachen-Analyse #401 fehlt als Verweisziel")

    def test_keine_umsetzungsbehauptung(self):
        import re
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        self.assertIn("Keine Verhaltensaenderung", text)
        self.assertIn("keine Wirkungszahl", text)
        self.assertIn("UNKNOWN != PASS", text)


if __name__ == "__main__":
    unittest.main()
