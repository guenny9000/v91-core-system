"""Tests fuer den V91-REPO-AUDIT-REVIEW 2026-11-26
(docs/V91-REPO-AUDIT-REVIEW-2026-11-26.md).
Muster: Der externe Bereinigungsbericht ist nur eine BEHAUPTUNG,
bis jede Aussage gegen Primaerquellen geprueft ist. Diese Tests
pinnen die Pruefergebnisse (BELEGT / KORREKTUR / NICHT_GEPRUEFT),
die Fremd-Markierungen, den eigenen Zusatzfund und die Grenzen.
NEGATIVE Tests verweigern jede Fix-Behauptung (REVIEW != FIX)."""
from __future__ import annotations

import pathlib
import unittest

DOC = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs"
    / "V91-REPO-AUDIT-REVIEW-2026-11-26.md"
)


class V91RepoAuditReviewDokuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_datei_existiert_klein_ascii(self):
        self.assertTrue(DOC.is_file(), "Pruefbericht fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024)
        self.assertEqual([], [c for c in self.text if ord(c) > 127])

    def test_status_review_ohne_fix(self):
        self.assertIn("PRUEFBERICHT", self.text)
        self.assertIn("REVIEW != FIX", self.text)
        self.assertIn("BELEGT != GELOEST", self.text)

    def test_provenienz_fremdbericht_und_kanalnachweis(self):
        self.assertIn("externer Bereinigungsbericht", self.text)
        self.assertIn("V91-SESSION-2026-11-26-REPO-AUDIT-GPT6", self.text)
        self.assertIn("CLAIM != EVIDENCE", self.text)

    def test_fuenf_fremd_markierungen_bestaetigt(self):
        self.assertIn("Alle fuenf vom Bericht behaupteten Aktionen EXISTIEREN", self.text)
        self.assertIn("Aurelia-Prisma Issue #269", self.text)
        self.assertIn("V91_Agathon Issue #24", self.text)
        self.assertIn("#041", self.text)
        self.assertIn("#049", self.text)
        self.assertIn("10:12:13Z", self.text)

    def test_finding1_lux_gate_belegt(self):
        self.assertIn("Finding 1: Aurelia-Prisma LUX-Gate (Issue #269) - BELEGT", self.text)
        self.assertIn("weniger als 3 Zeichen", self.text)
        self.assertIn("Hard-Stop", self.text)
        self.assertIn("VERHALTENSAENDERUNG", self.text)

    def test_finding2_agathon_platzhalter_belegt(self):
        self.assertIn("Finding 2: V91_Agathon Skalierung (Issue #24) - BELEGT", self.text)
        self.assertIn("NotImplementedError", self.text)
        self.assertIn("no scan was executed", self.text)
        self.assertIn("VORGETAEUSCHTE Funktion", self.text)

    def test_finding3_singlefile_belegt(self):
        self.assertIn("Finding 3: Aurelia-Prisma V92 Singlefile - BELEGT", self.text)
        self.assertIn("V92_SUPERVISOR_SINGLEFILE.py", self.text)
        self.assertIn("Legacy Single-File (Referenz)", self.text)
        self.assertIn("KEIN Test importiert es", self.text)

    def test_eigener_zusatzfund_provider_zentralitaet(self):
        self.assertIn("PROVIDER-ZENTRALITAET", self.text)
        self.assertIn("https://api.openai.com", self.text)
        self.assertIn("USE_OLLAMA", self.text)
        self.assertIn("0.0.0.0:8000", self.text)

    def test_finding4_orchester_log_nicht_loeschen(self):
        self.assertIn("KORREKTUR BELEGT", self.text)
        self.assertIn("V91_MAILBOX_LOG.node.js", self.text)
        self.assertIn("NICHT LOESCHEN", self.text)

    def test_finding5_offline_belegt_nicht_geprueft(self):
        self.assertIn("zero network I/O by construction", self.text)
        self.assertIn("gates_local_readiness = FALSE", self.text)
        self.assertIn("CODE-EXISTENZ != BETRIEBSNACHWEIS", self.text)
        self.assertIn("#23", self.text)

    def test_sicherheitsfaelle_bleiben_offen(self):
        self.assertIn("#239", self.text)
        self.assertIn("#264", self.text)
        self.assertIn("bleiben OFFEN", self.text)

    def test_grenzen_pins(self):
        self.assertIn("NICHT_GEPRUEFT", self.text)
        self.assertIn("GitHub-Code-Suche", self.text)

    def test_negativ_kein_fix_anspruch(self):
        # NEGATIVE TESTS: Der Bericht darf KEINE Bewirkung behaupten.
        self.assertNotIn("WURDE GELOESCHT", self.text)
        self.assertNotIn("WURDE ARCHIVIERT", self.text)
        self.assertNotIn("FIX ERLEDIGT", self.text)
        self.assertNotIn("gh repo archive", self.text)


if __name__ == "__main__":
    unittest.main()
