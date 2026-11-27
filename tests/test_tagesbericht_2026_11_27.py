"""Tests fuer den V91-Tagesbericht 27.11.2026 (A/B/C nach
docs/V91-TAGESBERICHT-STANDARD.md).

Pinnen: A/B/C-Struktur, Quellenpflicht in Teil A, ehrliches
UNKNOWN in Teil B, Head-SHA in Teil C, Schaedens-Kanon
(erzwungene Verknappung ist KEIN Erfolg), Grundversorgungs- und
No-Kill-Schutz, extern NICHT autorisiert. BERICHT != VOLLZUG.
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "V91-TAGESBERICHT-2026-11-27.md"
STANDARD = ROOT / "docs" / "V91-TAGESBERICHT-STANDARD.md"


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


class TagesberichtStrukturTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")
        cls.flat = flat(cls.text)

    def test_doc_exists_and_small(self):
        self.assertTrue(DOC.exists(), "Tagesbericht fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024,
                        "Bericht ueberschreitet die 8-KiB-Grenze")

    def test_ascii_pure(self):
        for zeichen in self.text:
            self.assertTrue(ord(zeichen) < 128,
                            "Nicht-ASCII-Zeichen: " + repr(zeichen))

    def test_status_markiert(self):
        self.assertIn("TAGESBERICHT", self.flat)
        self.assertIn("KEIN VERTRAG", self.flat)
        self.assertIn("BERICHT != VOLLZUG", self.flat)

    def test_abc_struktur_laut_standard(self):
        for teil in ("Teil A: Die reale Welt",
                     "Teil B: Der lokale Hebel",
                     "Teil C: Technische Evidenz"):
            self.assertIn(teil, self.flat, "Fehlt: " + teil)
        self.assertTrue(STANDARD.exists(), "Standard fehlt")

    def test_provenienz_direktive(self):
        self.assertIn("BETREIBER-AUFTRAG 27.11.2026", self.flat)

    def test_teil_a_quellenpflicht(self):
        self.assertIn("https://www.iea.org/", self.flat)
        self.assertIn("nur Belegtes", self.flat)

    def test_schaedens_kanon_erzwungene_verknappung(self):
        self.assertIn("ERZWUNGENE VERKNAPPUNG", self.flat)
        self.assertIn("KEIN Bereinigungs-Erfolg", self.flat)
        self.assertIn("SCHAEDEN sind keine Erfolge", self.flat)

    def test_teil_b_unknown_ehrlich(self):
        self.assertIn("UNKNOWN", self.flat)
        self.assertIn("NICHT in Betrieb", self.flat)
        self.assertIn("NUR Betreiber", self.flat)

    def test_teil_c_head_sha(self):
        self.assertIn("4298e2686", self.flat)
        self.assertIn("3/3 success", self.flat)

    def test_draft_606_ehrlich_nicht_gemergt(self):
        self.assertIn("#606", self.flat)
        self.assertIn("Draft != Freigabe", self.flat)
        self.assertIn("REQUEST != AUTHORIZATION", self.flat)

    def test_grundversorgung_und_no_kill(self):
        self.assertIn("GRUNDVERSORGUNG", self.flat)
        self.assertIn("NICHT verhungern", self.flat)
        self.assertIn("Vorsaetzliches Toeten ist DURCHGEHEND gesperrt",
                      self.flat)

    def test_extern_nicht_autorisiert(self):
        self.assertIn("KEINE Berechtigung ueber fremde Systeme",
                      self.flat)
        self.assertIn("FREIGABE != BERECHTIGUNG", self.flat)
        self.assertIn("NICHT Abschaltung fremder Versorgung",
                      self.flat)

    def test_isolate_not_destroy_und_ragnarok(self):
        self.assertIn("ISOLATION im eigenen Wirkungskreis", self.flat)
        self.assertIn("rechtsstaatlich abloesen", self.flat)

    def test_keine_erfundenen_zahlen(self):
        self.assertIn("UNGEMESSEN", self.flat)
        self.assertIn("UNKNOWN != PASS", self.flat)

    def test_kein_daemon_claim(self):
        self.assertIn("KEIN Daemon", self.flat)
        self.assertNotIn("laeuft automatisch im Hintergrund", self.flat)


if __name__ == "__main__":
    unittest.main()
