"""Tests fuer den Nidhoegg-Anhang als Systemdokumentation (26.11.2026).

Pinnen nach dem Kodex-Muster (#523/#528/#566/#567): Ergaenzung existiert
und ist klein, Kernmarker Wort fuer Wort vorhanden, ehrliche
Ergaenzungen des Betreibers VERBINDLICH mitgetestet (BEOBACHTUNG !=
BEHEBUNG, Massnahmenstein-Metafelder, vollstaendiger
Verbesserungszyklus), Verweis-Ziel existiert, ASCII-pure.
ERZAEHLUNG != VERTRAG."""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "V91-ABENDGESCHICHTE-NIDHOEGG-ANHANG-2026-11-26.md"
ORIGINAL = ROOT / "docs" / "V91-ABENDGESCHICHTE-NIDHOEGG-2026-11-26.md"


class NidhoeggAnhangDokuTest(unittest.TestCase):
    def test_anhang_exists_and_small(self):
        self.assertTrue(DOC.exists(), "Anhang-Doku fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024,
                        "Anhang ueberschreitet die 8-KiB-Grenze")

    def test_original_unangetastet_vorhanden(self):
        self.assertTrue(ORIGINAL.exists(), "Original-Geschichte fehlt")
        self.assertLess(ORIGINAL.stat().st_size, 8 * 1024)

    def test_ascii_pure(self):
        text = DOC.read_text(encoding="utf-8")
        for ch in text:
            self.assertTrue(ord(ch) < 128,
                            f"nicht-ASCII-Zeichen: {ch!r} (ord {ord(ch)})")

    def test_sichtbarmacher_kern_wortgenau(self):
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        self.assertIn("NIDHOEGG IST NICHT DAS BOESE", text)
        self.assertIn("DER SICHTBARMACHER UNBEACHTETER SCHWAECHEN", text)
        self.assertIn("Wer Nidhoegg sieht, hat nicht versagt.", text)
        self.assertIn("Wer ihn ignoriert, beginnt zu versagen.", text)

    def test_massnahmenstein_drei_bereiche(self):
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        for needle in ("Bewahren.", "Verbessern.", "Erforschen.",
                        "Der Stein enthielt nur drei Bereiche."):
            self.assertIn(needle, text, needle)

    def test_beobachtung_nicht_behebung_pin(self):
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        self.assertIn("BEOBACHTUNG != BEHEBUNG", text)
        self.assertIn("NACHGEWIESENE Behebung", text)

    def test_massnahmenstein_metafelder_pin(self):
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        self.assertIn("VERANTWORTLICHKEIT", text)
        self.assertIn("PRIORITAET", text)
        self.assertIn("ERFASSUNG != ERLEDIGUNG", text)

    def test_verbesserungszyklus_vollstaendig(self):
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        for schritt in ("Entdecken", "Pruefen", "Bewerten", "Bewahren",
                        "Verbessern", "Wirkung nachweisen",
                        "Erneut pruefen"):
            self.assertIn(schritt, text, schritt)

    def test_gleichgueltigkeit_als_gefahr(self):
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        self.assertIn("Die groesste Gefahr war immer Gleichgueltigkeit.", text)
        self.assertIn("Aber beobachtet.", text)

    def test_ehrliche_kennzeichnungen(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("ERZAEHLUNG != VERTRAG", text)
        self.assertIn("MYTHOS != SPEZIFIKATION", text)
        self.assertIn("UNKNOWN != PASS", text)
        self.assertIn("#567", text)
        self.assertIn("ISOLATE_NOT_DESTROY", text)


if __name__ == "__main__":
    unittest.main()
