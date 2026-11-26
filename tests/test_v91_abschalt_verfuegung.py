"""Tests fuer die V91-ABSCHALT-VERFUEGUNG (Betreiber-Direktive
26.11.2026, docs/V91-ABSCHALT-VERFUEGUNG-2026-11-26.md).
Kodex-Muster: Doku existiert, ist klein und ASCII-pure,
Kernaussagen sind gepinnt (LEER-Evidenz, NICHT-Archivierungs-
Begruendungen, ISOLATE_NOT_DESTROY, NICHT_AUSFUEHRBAR,
gh-Befehle), und ein NEGATIVER Test verweigert jede
Vollzugs-Behauptung (DIRECTIVE != VOLLZUG)."""
from __future__ import annotations

import pathlib
import re
import unittest

DOC = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs"
    / "V91-ABSCHALT-VERFUEGUNG-2026-11-26.md"
)

LEERE_REPOS = ("New-project", "guenn", ".antigravity-ide")
AKTIVE_REPOS = (
    "guenny9000",
    "guenny9000-uni-lern-bloc",
    "v91-audit-ledger",
    "V91_Agathon",
    "Aurelia-Prisma",
    "v91-core-system",
)


class V91AbschaltVerfuegungDokuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_datei_existiert_klein_ascii(self):
        self.assertTrue(DOC.is_file(), "Verfuegung fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024)
        self.assertEqual([], [c for c in self.text if ord(c) > 127])

    def test_status_direktive_nicht_vollzug(self):
        self.assertIn("DIRECTIVE != VOLLZUG", self.text)
        self.assertIn("DOKUMENTIERT != AUSGEFUEHRT", self.text)
        self.assertIn("NICHTS ist durch sie ausgefuehrt", self.text)

    def test_leer_evidenz_exakt_drei_kandidaten(self):
        self.assertIn("EXACTLY DREI", self.text)
        for name in LEERE_REPOS:
            self.assertIn(name, self.text, name)
        for name in LEERE_REPOS:
            self.assertNotIn("%s: 1" % name, self.text)

    def test_leere_repos_0_branches_belegt(self):
        # Jeder Kandidat muss mit 0 Branches und 0 offenen
        # Issues/PRs dokumentiert sein (frischer Lookup 26.11.).
        for name in LEERE_REPOS:
            self.assertRegex(
                self.text,
                re.escape(name) + r": 0 Branches, 0 offene Issues, 0 offene PRs",
            )

    def test_aktive_repos_nicht_archiviert(self):
        self.assertIn("NICHT archivierte Repos", self.text)
        for name in AKTIVE_REPOS:
            self.assertIn(name, self.text, name)
        self.assertIn("UNBERUEHRT", self.text)

    def test_begruendung_mit_branch_und_issue_evidenz(self):
        self.assertIn("14 Branches, 1 offener Pull Request", self.text)
        self.assertIn("25 Branches, 1 offenes Issue (#15", self.text)
        self.assertIn("29 Branches, 4 offene Issues", self.text)
        self.assertIn("19 offene Issues", self.text)

    def test_isolate_not_destroy_und_kein_loeschen(self):
        self.assertIn("ISOLATE_NOT_DESTROY", self.text)
        self.assertIn("KEIN LOESCHEN", self.text)
        self.assertIn("NICHT loeschen", self.text)
        self.assertIn("gh repo delete", self.text)
        self.assertIn("NICHT beauftragt", self.text)

    def test_nicht_ausfuehrbar_ueber_vibe_connector(self):
        self.assertIn("NICHT_AUSFUEHRBAR", self.text)
        self.assertIn("49", self.text)
        self.assertIn("KEINEN Archiv-Endpunkt", self.text)
        self.assertIn("VOLLAUTOMATISCHER VOLLZUG: NICHT_MOEGLICH", self.text)

    def test_gh_archiv_befehle_alle_drei_kandidaten(self):
        for name in LEERE_REPOS:
            self.assertIn("gh repo archive guenny9000/%s --yes" % name, self.text)

    def test_unarchive_weg_genannt(self):
        self.assertIn("gh repo unarchive", self.text)

    def test_grenzen_und_veraltungshinweis(self):
        self.assertIn("Stand vom", self.text)
        self.assertIn("Vor jedem Vollzug FRISCH pruefen", self.text)
        self.assertIn("keine fremden Systeme", self.text)

    def test_negativ_kein_vollzugsanspruch(self):
        # NEGATIVER TEST: Die Verfuegung darf NICHT behaupten,
        # der Vollzug sei bereits erledigt.
        self.assertNotIn("VOLLZUG: ERLEDIGT", self.text)
        self.assertNotIn("ARCHIVIERT_AM:", self.text)
        self.assertNotIn("wurde archiviert am", self.text)
        for name in AKTIVE_REPOS:
            self.assertNotIn("gh repo archive guenny9000/%s" % name, self.text)


if __name__ == "__main__":
    unittest.main()
