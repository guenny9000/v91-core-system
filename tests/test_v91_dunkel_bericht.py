"""Tests fuer den V91-Dunkelbericht 26.11.2026 (Abschaltung,
Isolierung, Transformation, Ressourcenersparnis; Dark Edition).

Pinnen nach dem Kodex-Muster (#533/#566/#578/#595): Doku existiert
und ist klein, Kernsaetze wortgenau (umbruch-normalisiert nach
Lektion #547), KEINE Umsetzungsbehauptung, Verweis-Ziele existieren,
ASCII-pure, ehrliche Grenzen. BERICHT != BEWEIS, DOKUMENT !=
VOLLZUG, UNKNOWN != PASS.
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "V91-DUNKEL-BERICHT-2026-11-26.md"
ABSCHALT = ROOT / "docs" / "V91-ABSCHALT-VERFUEGUNG-2026-11-26.md"
DEPAUDIT = ROOT / "docs" / "V91-DEPENDENCY-AUDIT-2026-11-26.md"
IMPERIAL = ROOT / "docs" / "V91-IMPERIAL-BERICHT-2026-11-26.md"


def flat(text: str) -> str:
    """Umbruch- und Leerraum-normalisiert (Lektion #547)."""
    return re.sub(r"\s+", " ", text)


class DunkelBerichtDokuTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")
        cls.flat = flat(cls.text)

    def test_doc_exists_and_small(self):
        self.assertTrue(DOC.exists(), "Dunkelbericht fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024,
                        "Doku ueberschreitet die 8-KiB-Grenze")

    def test_ascii_pure(self):
        for zeichen in self.text:
            self.assertTrue(ord(zeichen) < 128,
                            "Nicht-ASCII-Zeichen: " + repr(zeichen))

    def test_status_markiert(self):
        self.assertIn("DUNKEL-LAGEBERICHT", self.flat)
        self.assertIn("KEIN VERTRAG", self.flat)
        self.assertIn("KEINE NEUE BEFUGNIS", self.flat)

    def test_provenienz_direktive(self):
        self.assertIn("BETREIBER-DIREKTIVE 26.11.2026", self.flat)

    def test_kanon_schaeden_keine_erfolge(self):
        self.assertIn("SCHAEDEN und keine Erfolge", self.flat)
        self.assertIn("RISIKEN und BELASTUNGEN", self.flat)
        self.assertIn("NIEMALS als Fortschritt gefeiert", self.flat)

    def test_max_best_fuenf_massstaebe(self):
        for satz in ("Schaeden verhindern und Folgen begrenzen",
                     "Ressourcenverbrauch und unnoetige Transportwege",
                     "bessere Alternativen ersetzen",
                     "messbarer Ergebnisse bewerten",
                     "Neue Entwicklungen beobachten"):
            self.assertIn(satz, self.flat, "Massstab fehlt: " + satz)

    def test_rebellen_nuechtern_nie_gegen_menschen(self):
        self.assertIn("NUR gegen destruktive PROZESSE und ARTEFAKTE",
                      self.flat)
        self.assertIn("NIEMALS gegen Menschen oder Grundversorgung",
                      self.flat)
        self.assertIn("KEINE Menschenjagd", self.flat)

    def test_isolate_not_destroy(self):
        self.assertIn("ISOLATE_NOT_DESTROY", self.flat)
        self.assertIn("Abschalten heisst ISOLIEREN", self.flat)

    def test_verweis_ziele_existieren(self):
        for pfad, name in ((ABSCHALT, "Abschalt-Verfuegung"),
                           (DEPAUDIT, "Dependency-Audit"),
                           (IMPERIAL, "Imperialer Bericht")):
            self.assertTrue(pfad.exists(), "Verweisziel fehlt: " + name)

    def test_drei_leere_repos_genau(self):
        for name in ("New-project", "guenn", ".antigravity-ide"):
            self.assertIn(name, self.flat)
        self.assertIn("GENAU DREI leere", self.flat)
        self.assertIn("Vollzug = BETREIBER", self.flat)

    def test_sechs_aktive_repos_nicht_isoliert(self):
        self.assertIn("BEWUSST NICHT-ISOLIERT", self.flat)
        self.assertIn("SECHS aktiven Repos", self.flat)
        self.assertIn("nutzlose Zerstoerung", self.flat)

    def test_ballast_kandidaten_ehrlich(self):
        self.assertIn("NICHT_GEFUNDEN_IN_PY", self.flat)
        self.assertIn("NICHT_GEFUNDEN != UNGENUTZT", self.flat)
        self.assertIn("NACHMESSUNG PFLICHT", self.flat)
        self.assertIn("Merge-Nachweis-Pruefung", self.flat)

    def test_keine_erfundenen_zahlen(self):
        self.assertIn("UNGEMESSEN", self.flat)
        self.assertIn("wird NICHT behauptet", self.flat)
        self.assertIn("UNKNOWN != PASS", self.flat)
        self.assertIn("MESSDATEN #101/#103".replace("MESSDATEN",
                                                    "Messdaten"), self.flat)

    def test_kein_vollzug_durch_bericht(self):
        self.assertIn("ein Bericht vollstreckt NICHTS", self.flat)
        self.assertIn("kein einziger Abschalt-Vollzug", self.flat)
        self.assertIn("DOKUMENT != VOLLZUG", self.flat)

    def test_messtand_aktuell(self):
        self.assertIn("a6b2df25d", self.flat)

    def test_negativsonde_kein_endzustand(self):
        # KEIN Gesamterfolg, KEINE Weltwirkungs-Behauptung.
        self.assertNotIn("Welt gerettet", self.flat)
        self.assertNotIn("Mission erfuellt", self.flat)
        self.assertIn("NICHT GEPRUEFT", self.flat)


if __name__ == "__main__":
    unittest.main()
