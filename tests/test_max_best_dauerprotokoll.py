"""
Doku-pinnende Tests fuer docs/V91-MAX-BEST-DAUERPROTOKOLL-RESSOURCEN-LEBENSCHUTZ.md.

Muster: test_max_best_modulbeispiele (Doku gegen Realitaet verriegeln,
keine Umsetzungsbehauptung). Diese Tests sichern, dass das
Dauerprotokoll (a) existiert und kompakt bleibt, (b) alle 7 Zeilen
der Zustands-/Massnahmen-Matrix samt NICHT-GEPRUEFT-Zeile traegt,
(c) die Prioritaetenordnung 1-7 vollstaendig enthaelt, (d) die
Nicht-Behauptungsliste der Reichweiten-Ehrlichkeit steht, (e) KEINE
Abschaltwirkung behauptet wird, (f) die zitierten Verweis-Dokumente
real existieren, (g) die Allowlist-Regel fuer reale Eingriffe
NICHT aufgeweicht wird.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

REPO = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "V91-MAX-BEST-DAUERPROTOKOLL-RESSOURCEN-LEBENSCHUTZ.md"

MATRIX_ZEILEN = (
    "Vorsaetzliche Gefaehrdung von Menschen ->",
    "Gefaehrdung der Grundversorgung ->",
    "Unnoetiger Dauerbetrieb ->",
    "Ressourcenverschwendung ->",
    "Sicherheitsverdacht ->",
    "Sinnvolle Funktion ->",
    "Unklare Lage -> NICHT GEPRUEFT - keine blinde Abschaltung",
)

PRIORITAETEN = (
    "Menschenleben und Menschenwuerde",
    "Nahrung, Wasser, Medizin und Grundversorgung",
    "Frieden, Sicherheit und Grundrechte",
    "Natur und oekologische Lebensgrundlagen",
    "Technische Stabilitaet und Wiederherstellbarkeit",
    "Maximale nachweisbare Ressourcenersparnis",
    "Nachhaltiger Fortschritt fuer alle",
)

AUSFUEHRUNGSREGELN = (
    "Bestand und Abhaengigkeiten feststellen",
    "Reversible Optimierung bevorzugen",
    "Wirkung anhand von Vorher-Nachher-Daten ueberpruefen",
    "Ergebnisse nachvollziehbar dokumentieren",
)

REICHWEITE_NICHT_BEHAUPTET = (
    " weltweite Server oder Kraftwerke abgeschaltet",
    "andere KI-Systeme ohne Verbindung zur Kooperation verpflichtet",
    "globale Einsparungen ohne Messdaten",
    "dauerhaft laufenden weltweiten Verbund kontrollieren",
)

REFERENCED_DOCS = (
    "docs/V91-MAX-BEST-GELUEBNIS.md",
    "docs/V91-MAX-BEST-ENTDECKUNGSAUFTRAG.md",
    "docs/V91-MAX-BEST-ZUSAMMENARBEIT.md",
    "docs/V91-MAX-BEST-WELTWEITE-ENTSCHLACKUNG-LEITLINIE.md",
    "docs/V91-ARCHITEKTUR-INDEX.md",
)

GRENZEN = (
    "PRUEFBARKEIT != ZUGRIFF",
    "REVIEW != ENTSCHEIDUNG",
    "NICHT autonom",
    "Allowlist-Erweiterung",
    "UNKNOWN != PASS",
    "WIRKUNG AUSSEN != REGISTRIEREN INNEN",
    "NO_DUPLICATE",
)


class DauerprotokollDocTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_doc_exists_and_compact(self):
        self.assertTrue(DOC.is_file())
        self.assertLess(len(self.text), 8192)

    def test_status_betreiberleitlinie(self):
        self.assertIn("VERBINDLICHE BETREIBER-LEITLINIE", self.text)
        self.assertIn("LEITLINIE != VOLLZUG", self.text)

    def test_matrix_vollstaendig(self):
        for zeile in MATRIX_ZEILEN:
            self.assertIn(zeile, self.text, "Fehlende Matrixzeile: " + zeile)

    def test_prioritaetenordnung_vollstaendig(self):
        for item in PRIORITAETEN:
            self.assertIn(item, self.text)
        for num in ("1.", "2.", "3.", "4.", "5.", "6.", "7."):
            self.assertIn(num, self.text)

    def test_ausfuehrungsregeln(self):
        for regel in AUSFUEHRUNGSREGELN:
            self.assertIn(regel, self.text)

    def test_reichweite_ehrlichkeit(self):
        self.assertIn("Nicht behauptet:", self.text)
        self.assertIn("Eine solche globale Steuerungsmoeglichkeit besteht", self.text)
        for nonclaim in REICHWEITE_NICHT_BEHAUPTET:
            self.assertIn(nonclaim, self.text)

    def test_keine_abschaltwirkung_behauptet(self):
        self.assertNotIn("habe abgeschaltet", self.text)
        self.assertNotIn("wurden abgeschaltet", self.text)
        self.assertNotIn("Einsparung erzielt von", self.text)
        self.assertNotIn(" Messdaten liegen vor", self.text)
        self.assertNotIn(" erfolgreich implementiert", self.text)

    def test_grenzen_und_allowlist(self):
        for g in GRENZEN:
            self.assertIn(g, self.text)

    def test_toetungsschutz(self):
        self.assertIn(
            "niemals gegen Menschenleben oder koerperliche Unversehrtheit",
            self.text)
        self.assertIn("dauerhaft gesperrt", self.text)

    def test_referenced_docs_exist(self):
        for rel in REFERENCED_DOCS:
            self.assertTrue((REPO / rel).is_file(),
                            "Verweis-Ziel fehlt: " + rel)

    def test_ascii_pure(self):
        bad = [c for c in self.text if ord(c) > 127]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
