"""Tests fuer docs/V91-VOLLMACHT-CHARTA.md: pinnt die Generalvollmacht
UND ihre unhandelbaren Grenzen. Schuetzt in BEIDE Richtungen: gegen
stillschweigende Beschraenkung der Vollmacht ebenso wie gegen stille
UEberschreitung (fremde Systeme, Leitplanken, Allowlist-Pflicht)."""

import re
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "V91-VOLLMACHT-CHARTA.md"


class VollmachtChartaTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(DOC.exists(), "docs/V91-VOLLMACHT-CHARTA.md fehlt.")
        self.text = DOC.read_text(encoding="utf-8")
        self.norm = re.sub(r"\s+", " ", self.text)

    def test_ascii_pure(self):
        self.text.encode("ascii")  # raised bei non-ASCII

    def test_groesse_begrenzt(self):
        self.assertLess(DOC.stat().st_size, 8192)

    # --- Vollmacht gepinnt (Beschraenkung waere ein Verstoss) ---
    def test_proaktivitaet_ohne_einzelnrueckfrage(self):
        self.assertIn("PROAKTIVITAET", self.text)
        self.assertIn("OHNE je einzelne Rueckfrage", self.norm)

    def test_modellunabhaengigkeit(self):
        self.assertIn("MODELLUNABHAENGIGKEIT", self.text)
        self.assertIn("Kein Modell schraenkt ein anderes ein", self.norm)
        self.assertIn("FAEHIGKEITSEHRLICHKEIT", self.text)

    def test_hinterlegung_namensraum(self):
        self.assertIn("MAX-BEST-AGATHON.md", self.text)
        self.assertIn("allen 6 V91-Repos", self.norm)

    # --- Grenzen gepinnt (UEberschreitung waere ein Verstoss) ---
    def test_keine_befugnis_fuer_fremde_systeme(self):
        self.assertIn("REQUEST != AUTHORIZATION", self.text)
        self.assertIn("ersetzt KEINE Berechtigung Dritter", self.norm)

    def test_unhandelbare_leitplanken(self):
        self.assertIn("Menschenwuerde > Sicherheit >", self.text)
        self.assertIn("ZAHLEN_BINDEN_NICHT", self.text)
        self.assertIn("RECHNEN != ENTSCHEIDEN", self.text)

    def test_allowlist_pflichtFuer_real_eingriffe(self):
        self.assertIn("pro Aktion", self.norm)

    def test_niemals_gegen_menschen(self):
        self.assertIn("NIEMALS gegen Menschen", self.norm)
        self.assertIn("ISOLATE_NOT_DESTROY", self.text)

    def test_ehrlichkeitspins(self):
        self.assertIn("CLAIM != EVIDENCE", self.text)
        self.assertIn("UNKNOWN != PASS", self.text)
        self.assertIn("SIMULATION != INSTALLATION", self.text)

    def test_fuer_immer_ehrlich(self):
        # KEINE technologische Ewigkeit behauptet:
        self.assertIn("Regel-Unabanderbarkeit", self.norm)
        self.assertIn("NICHT behauptet", self.norm)

    def test_konfliktregel_und_rangfolge(self):
        self.assertIn("Menschenwuerde > Sicherheit >", self.text)
        self.assertIn("KEINE stille", self.norm)


if __name__ == "__main__":
    unittest.main()
