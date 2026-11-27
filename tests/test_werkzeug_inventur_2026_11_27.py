"""Tests: Werkzeug-Inventur 27.11.2026 (Connector-Lese-Sonden).
Pinnt das Inventur-Dokument und seine Kerndisziplinen:
ASCII-pure, ehrliche Fehler-Spalte (UNKNOWN != PASS), keine
Inhalts-Dumps (ZAEHLWERTE != INHALTE)."""

from __future__ import annotations

import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs/V91-WERKZEUG-INVENTUR-2026-11-27.md"


class TestWerkzeugInventurDokument(unittest.TestCase):
    def test_dokument_existiert(self):
        self.assertTrue(DOC.is_file())

    def test_ascii_pure(self):
        raw = DOC.read_bytes().decode("utf-8")
        self.assertRegex(raw, r"^[\x00-\x7F]*$")
        self.assertEqual(raw, raw.encode("ascii", "ignore").decode("ascii"))

    def test_kernzeilen_gepingt(self):
        text = DOC.read_text(encoding="utf-8")
        for pin in (
            "# V91-WERKZEUG-INVENTUR-2026-11-27",
            "CLAIM != EVIDENCE",
            "UNKNOWN != PASS",
            "Verfuegbarkeit != Nutzung",
            "INVENTUR != PRUEFUNG",
            "| sharepoint_mcp | list_team_sites | FEHLER 401 |",
            "NICHT_GEPRUEFT",
        ):
            self.assertIn(pin, text)

    def test_ehrlichkeit_kein_stilles_ok(self):
        """Jeder NICHT_GEPRUEFT-Connector muss namentlich im Fehlerteil
        oder in der Tabelle mit NICHT_GEPRUEFT stehen (kein Pass durch
        Schweigen)."""
        text = DOC.read_text(encoding="utf-8")
        for name in ("notion", "figma_adc4", "image_generation"):
            self.assertIn(name, text)

    def test_kein_v91_audit_token(self):
        """Fiction-Scan-Policy: Chat-Protokoll-Tokens gehoeren nicht
        in Dokumente (audit_series_marker-Analogon)."""
        text = DOC.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\bV91-AUDIT-V[0-9]", text))

    def test_keine_erfundene_connector_liste(self):
        """Die 8 authentication_required-Connector muessen ehrlich als
        nicht verbunden benannt sein."""
        text = DOC.read_text(encoding="utf-8")
        for name in (
            "apify",
            "asana",
            "atlassian",
            "box",
            "outlook,",
            "sharepoint_online",
            "stripe",
            "teams",
        ):
            self.assertIn(name, text, "fehlender Nicht-Verbundener: " + name)


if __name__ == "__main__":
    unittest.main()
