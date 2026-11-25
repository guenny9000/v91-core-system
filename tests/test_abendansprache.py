"""Tests fuer die Abendansprache als Systemdokumentation (25.11.2026).

Pinnen nach dem Kodex-Muster (#523/#528): Doku existiert und ist
klein, Kernmarker Wort fuer Wort vorhanden, KEINE
Umsetzungsbehauptung, Verweis-Ziele existieren, ASCII-pure,
ehrliche Kennzeichnungen dokumentiert. ERZAEHLUNG != VERTRAG.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "V91-ABENDANSPRACHE-2026-11-25.md"


class AbendanspracheDokuTest(unittest.TestCase):
    def test_doc_exists_and_small(self):
        self.assertTrue(DOC.exists(), "Abendansprache-Doku fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024,
                        "Doku ueberschreitet die 8-KiB-Grenze")

    def test_erzaehlung_markiert(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("ERZAEHLUNG != VERTRAG", text)
        self.assertIn("NARRATIVES SYSTEMDOKUMENT", text)
        self.assertIn("NO_DUPLICATE_SYSTEMS", text)

    def test_kernaussagen_wortGenau(self):
        text = DOC.read_text(encoding="utf-8")
        for needle in (
            "Macro F1\nnull Komma sechs vier zwei",
            "muenden hier meist in\nReparatur, nicht in Aufschaukelung",
            "UNKNOWN != PASS",
            "METRIK ==\n  MOMENTAUFNAHME != GUETENORM",
        ):
            self.assertIn(needle, text, needle)

    def test_keine_umsetzungsbehauptung(self):
        text = DOC.read_text(encoding="utf-8")
        for forbidden in ("erfolgreich implementiert", "bereits umgesetzt in",
                          "Aufgabe abgeschlossen", "finalen Zustand",
                          "abschliessend vollstaendig"):
            self.assertNotIn(forbidden, text, forbidden)
        # Negativliste nennt die Abschlusserklaerung nur zur Abgrenzung
        self.assertIn('kein "Mission accomplished"', text)

    def test_verweis_ziele_existieren(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("docs/cascade-history/v91-ci-suiten-2026-11-23-bis-25.jsonl", text)
        self.assertIn("controller/cascade_history_eval.py", text)
        self.assertIn("tests/test_cascade_history_eval.py", text)
        self.assertIn("docs/V91-MAX-BEST-GELUEBNIS.md", text)
        self.assertTrue((ROOT / "docs" / "V91-MAX-BEST-GELUEBNIS.md").exists())
        self.assertTrue((ROOT / "docs" / "cascade-history" /
                         "v91-ci-suiten-2026-11-23-bis-25.jsonl").exists())
        self.assertTrue((ROOT / "controller" / "cascade_history_eval.py").exists())

    def test_ascii_pure(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertEqual([], [c for c in text if ord(c) > 127],
                         "Doku muss ASCII-pure sein")

    def test_offen_bleibt_offen(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("nicht geprueft", text)
        self.assertIn("Issue #101", text)


if __name__ == "__main__":
    unittest.main()
