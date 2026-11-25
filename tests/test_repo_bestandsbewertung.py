"""Tests fuer docs/V91-REPO-BESTANDSBEWERTUNG.md (Prioritaet 5 der
Gegenpruefung 25.11.2026). Pinnen: die drei leeren Repos sind als LEER
BEWERTET (nicht geloescht, ISOLATE_NOT_DESTROY), Behandlung bleibt
Betreiber-Entscheidung (FREIGABE != BERECHTIGUNG), UNKNOWN bleibt UNKNOWN,
ASCII-pure, Groesse begrenzt."""

import re
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "V91-REPO-BESTANDSBEWERTUNG.md"


class RepoBestandsbewertungTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(DOC.exists(), "docs/V91-REPO-BESTANDSBEWERTUNG.md fehlt.")
        self.text = DOC.read_text(encoding="utf-8")
        self.norm = re.sub(r"\s+", " ", self.text)

    def test_ascii_pure(self):
        self.assertEqual(self.text.encode("utf-8").decode("ascii"), self.text,
                         "Doku muss ASCII-pure sein.")

    def test_groesse_begrenzt(self):
        self.assertLess(DOC.stat().st_size, 8192,
                        "Bewertung muss kompakt bleiben (< 8192 B).")

    def test_drei_leere_repos_bewertet(self):
        for name in ("New-project", "guenn", ".antigravity-ide"):
            self.assertIn(name, self.text, f"Reporname fehlt: {name}")

    def test_leer_bewertung_mit_evidenzkriterien(self):
        self.assertIn("| keine | 404 | LEER", self.text)
        self.assertIn("API-size 0 kB", self.text)

    def test_nur_bewertet_nicht_geloescht(self):
        self.assertIn("ISOLATE_NOT_DESTROY", self.text)
        self.assertIn("BEWERTUNG != EINGRIFF", self.text)
        self.assertIn("kein Repository wird geloescht", self.norm)

    def test_betreiber_entscheidet_behandlung(self):
        self.assertIn("FREIGABE != BERECHTIGUNG", self.text)
        self.assertIn("Betreiber-Entscheidung", self.text)

    def test_unknown_bleibt_unknown(self):
        self.assertIn("UNKNOWN bleibt UNKNOWN", self.text)
        self.assertIn("Vermutung bleibt Vermutung", self.text)

    def test_sechs_befuellte_repos_gelistet(self):
        for name in ("v91-core-system", "V91_Agathon", "v91-audit-ledger",
                     "Aurelia-Prisma", "guenny9000-uni-lern-bloc",
                     "guenny9000"):
            self.assertIn(name, self.text)

    def test_kein_fiktiver_ci_status_behauptet(self):
        self.assertIn("UNKNOWN != ROT", self.text)
        # KEIN "CI green" fuer Repos ohne Workflows behauptet:
        for name in ("New-project", "guenn", ".antigravity-ide"):
            idx = self.text.find(name)
            snippet = self.norm[max(0, idx - 150): idx + 250]
            self.assertNotIn("CI", snippet.replace("KEINE CI-Faehigkeit", "")
                             .replace("keine Workflows", ""),
                             f"CI-Anspruch ohne Evidenz fuer {name}")

    def test_kein_loesch_vollzug_behauptet(self):
        self.assertNotIn("geloescht am", self.norm)
        self.assertNotIn("wurde geloescht", self.norm)


if __name__ == "__main__":
    unittest.main()
