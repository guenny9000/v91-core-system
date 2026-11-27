"""Tests: Bridge-Echtlauf 27.11.2026 (#618-Sonde, Betreiber-Go
"real systemecht"). Der Screening-Teil des ECHTLAUFS ist hier offline
reproduzierbar: gleicher Sonden-Text, gleiches deterministisches
Ergebnis (ECHTLAUF != ZUFALL). Der Netz-Abruf selbst bleibt
Betreiber-Schritt (SCRIPTED != RUNNING)."""

from __future__ import annotations

import pathlib
import unittest

from controller.bridge_screening import screen_text
from controller.kern_bridge import gate_payload

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs/V91-BRIDGE-ECHTLAUF-2026-11-27.md"

SONDE_EMAIL = "sonde.synthetik@example.org"
SONDE_IBAN = "DE02120300000000202051"
SONDE_ADRESSE = "Synthetischstrasse 12, 10115 Synthetika"

SONDE_BODY = (
    "### Echtlauf-Sonde (synthetisch)\n"
    "E-Mail-Form: " + SONDE_EMAIL + "\n"
    "IBAN-Form: " + SONDE_IBAN + "\n"
    "vollstaendige Postadresse: " + SONDE_ADRESSE + "\n"
    "UEBERGABE_KERN_START\n"
    "- Ziel: Echtlauf-Nachweis Bridge-Intake\n"
    "- Status: ANGABE (Sonde, keine Freigabe)\n"
    "UEBERGABE_KERN_ENDE\n"
)


class TestEchtlaufScreeningReproduktion(unittest.TestCase):
    def test_screening_findet_alle_drei_formen(self):
        result = screen_text(SONDE_BODY)
        self.assertEqual(result["status"], "REDACTED")
        kinds = {f["kind"] for f in result["findings"]}
        self.assertEqual(kinds, {"email", "iban_de", "adresse_de"})

    def test_redaktion_entfernt_alle_formen(self):
        redacted = screen_text(SONDE_BODY)["redacted_text"]
        self.assertNotIn(SONDE_EMAIL, redacted)
        self.assertNotIn(SONDE_IBAN, redacted)
        self.assertNotIn(SONDE_ADRESSE, redacted)
        self.assertIn("[REDACTIERT]", redacted)

    def test_marker_ueberleben_die_redaktion(self):
        redacted = screen_text(SONDE_BODY)["redacted_text"]
        self.assertIn("UEBERGABE_KERN_START", redacted)
        self.assertIn("UEBERGABE_KERN_ENDE", redacted)

    def test_gate_akzeptiert_die_sonde_isoliert(self):
        self.assertEqual(gate_payload(SONDE_BODY), "ACCEPTED_ISOLATED")

    def test_determinismus(self):
        a = screen_text(SONDE_BODY)
        b = screen_text(SONDE_BODY)
        self.assertEqual(a["findings"], b["findings"])
        self.assertEqual(a["redacted_text"], b["redacted_text"])


class TestEchtlaufDokuPins(unittest.TestCase):
    def test_doc_ascii_und_werte(self):
        text = DOC.read_text(encoding="utf-8")
        text.encode("ascii")
        self.assertIn("issues_seen 1, records_new 1", text)
        self.assertIn("records_new 0, records_known 1", text)
        self.assertIn("c2f44c7e1819f54a69f3e6052b19b4ba6cec2324e04ad9dd16177dfc2d79dff3",
                      text)
        self.assertIn("#618", text)
        self.assertIn("ABDRUCK != ABLAGE", text)
        self.assertIn("MUSTER != GARANTIE", text)

    def test_ehrliche_grenzen_genannt(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("AUFGENOMMEN !=\nVERIFIZIERT", text)
        self.assertIn("Momentaufnahme", text)
        self.assertIn("KEIN Daemon", text)
        self.assertIn("NICHT ins\n  Repository gepusht", text)


if __name__ == "__main__":
    unittest.main()
