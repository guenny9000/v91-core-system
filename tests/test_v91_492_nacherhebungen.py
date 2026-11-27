"""Tests: V91 #492 Nacherhebungen 27.11.2026 (Stufe-1-Abgleich, Stufe-4
Abruf-Seite). Pins sind gegen die abgelegten Dokumente und den
WIRKLICHEN main-Code gemessen; weicht eine Seite ab, schlagen die
Tests bewusst aus (DOKU == STAND)."""

from __future__ import annotations

import pathlib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs/V91-492-NACHERHEBUNGEN-2026-11-27.md"
BESTAND = REPO_ROOT / "docs/V91-492-BESTANDSAUFNAHME-2026-11-26.md"
KERN_BRIDGE = REPO_ROOT / "controller/kern_bridge.py"


class TestNacherhebungsDoc(unittest.TestCase):
    def setUp(self):
        self.text = DOC.read_text(encoding="utf-8")

    def test_doc_ascii_und_groesse(self):
        self.text.encode("ascii")
        self.assertLess(len(self.text.encode("utf-8")), 8192)

    def test_stufe1_verdikt(self):
        self.assertIn("ABGLEICH_ERFOLGT", self.text)
        self.assertIn("PR #615", self.text)
        self.assertIn("V91-492-STUFE1-COMMS-1-TEXTABGLEICH-2026-11-27.md", self.text)

    def test_stufe4_verdikt_und_grenzen(self):
        self.assertIn("ABRUF-SEITE_GESCHLOSSEN", self.text)
        self.assertIn("LUECKE -> ABRUF-SEITE_GESCHLOSSEN", self.text)
        self.assertIn("MUSTER != GARANTIE", self.text)
        self.assertIn("Sofortregel bleibt", self.text)
        self.assertIn("secret_scan prueft nur repo-eigene Dateien", self.text)
        self.assertIn("NICHT_GELOEST_BEKANNT", self.text)

    def test_uebrige_stufen_unveraendert(self):
        for s in ("Stufe 2 BELEGT", "3 BELEGT", "5 BELEGT",
                  "6 TEILWEISE", "7 TEILWEISE", "8 BEWUSST_GESPERRT"):
            self.assertIn(s, self.text)

    def test_bestandsaufnahme_verweist_und_bleibt_klein(self):
        text = BESTAND.read_text(encoding="utf-8")
        self.assertIn("V91-492-NACHERHEBUNGEN-2026-11-27.md", text)
        self.assertLess(len(text.encode("utf-8")), 8192)
        self.assertIn("NICHT_GELOEST_BEKANNT", text)


class TestStufe4WiringAmCode(unittest.TestCase):
    """Funktionsbeweis am echten Code (nicht Prosa)."""

    def test_kern_bridge_importiert_screen_text(self):
        source = KERN_BRIDGE.read_text(encoding="utf-8")
        self.assertIn("from controller.bridge_screening import", source)
        self.assertIn("screening = screen_text(body)", source)

    def test_ablage_nimmt_redigierten_text_hash_ueber_rohtext(self):
        source = KERN_BRIDGE.read_text(encoding="utf-8")
        self.assertIn('"payload": screening["redacted_text"]', source)
        # Digest VOR dem Screening berechnet: Hash bezeugt den Rohstoff.
        self.assertLess(
            source.index('digest = hashlib.sha256'),
            source.index("screening = screen_text(body)"),
        )

    def test_gate_bleibt_vom_screening_getrennt(self):
        source = KERN_BRIDGE.read_text(encoding="utf-8")
        self.assertIn("status = gate_payload(body)", source)

    def test_screening_musterumfang_am_modul(self):
        from controller import bridge_screening

        text = pathlib.Path(bridge_screening.__file__).read_text(
            encoding="utf-8"
        )
        for pattern in ("email", "iban_de", "tel_international_de",
                        "tel_national_de", "adresse_de"):
            self.assertIn(pattern, text)

    def test_end_to_end_sonde_erreichbar(self):
        from controller.bridge_screening import screen_text

        result = screen_text("Kontakt: max.mustermann@example.org")
        self.assertEqual(result["status"], "REDACTED")
        self.assertNotIn("max.mustermann@example.org",
                         result["redacted_text"])


if __name__ == "__main__":
    unittest.main()
