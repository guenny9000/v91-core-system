"""
Doku-pinnende Tests fuer docs/V91-MAX-BEST-DAUERPROTOKOLL.md
(Betreiber-Vorlage 25.11.2026, wortgetreu uebernommen,
ASCII-transliteriert).

Muster: test_max_best_modulbeispiele (#528). Diese Tests sichern,
dass das Dokument (a) existiert und kompakt bleibt (< 8 KiB),
(b) die Leitlinie und alle Zustands-/Massnahme-Paare wortgetreu
traegt, (c) KEINE Umsetzungsbehauptung enthaelt (VORLAGE !=
INSTALLATION), (d) die zitierten Verweis-Ziele real existieren,
(e) ASCII-pure bleibt, (f) die Zusatz-Einordnung klar als ZUSATZ
gekennzeichnet ist, NICHT als Teil der Vorlage.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

REPO = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "V91-MAX-BEST-DAUERPROTOKOLL.md"

REQUIRED_INVARIANTS = (
    "Oberstes Ziel: Menschenleben schuetzen",
    "jede vermeidbare Ressourcenverschwendung dauerhaft reduzieren",
    "Vorsatzliche Gefaehrdung von Menschen",
    "Unklare Lage",
    "NICHT GEPRUEFT - keine blinde Abschaltung",
    "niemals",
    "gegen Menschenleben oder koerperliche Unversehrtheit",
    "Energieerzeugung, Netze, Speicher und Rechenzentren",
    "Trinkwasser, Pumpen, Aufbereitung und Verteilung",
    "Reversible Optimierung bevorzugen",
    "Wirkung anhand von Vorher-Nachher-Daten ueberpruefen",
    "Ergebnisse nachvollziehbar dokumentieren",
    "DOKUMENTIERT != INSTALLIERT",
    "UNKNOWN != PASS",
    "ISOLATE_NOT_DESTROY",
    "RECHNEN != ENTSCHEIDEN",
    "KEINE fremden Systeme ohne Autorisierung veraenderen",
    "REQUEST != AUTHORIZATION",
    "ALS DAUERLEITLINIE FESTGEHALTEN",
)

FORBIDDEN_CLAIMS = (
    # KEINE Umsetzungsbehauptung:
    "erfolgreich implementiert",
    "bereits umgesetzt",
    "Installation abgeschlossen",
    "weltweite Abschaltung durchgefuehrt",
)

REQUIRED_REF_TARGETS = (
    "docs/V91-MAX-BEST-GELUEBNIS.md",
    "controller/max_best_rechner.py",
    "controller/kreislauf_status.py",
)


class DauerprotokollDokuTest(unittest.TestCase):
    def test_dokument_existiert_und_ascii_pure(self):
        self.assertTrue(DOC.exists(), "Dauerprotokoll-Doku fehlt")
        text = DOC.read_bytes().decode("ascii")
        self.assertGreater(len(text), 2000)
        self.assertIn("MAX-BEST Dauerprotokoll", text)

    def test_dokument_kompakt_unter_8kib(self):
        self.assertLess(DOC.stat().st_size, 8 * 1024)

    def test_invarianten_wortvermoeglich(self):
        text = DOC.read_text(encoding="ascii")
        for satz in REQUIRED_INVARIANTS:
            self.assertIn(satz, text, "fehlt: " + satz)

    def test_keine_umsetzungsbehauptung(self):
        text = DOC.read_text(encoding="ascii").lower()
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim.lower(), text,
                            "UMSETZUNGSBEHAUPTUNG: " + claim)

    def test_zustaende_alle_da(self):
        text = DOC.read_text(encoding="ascii")
        for zustand in ("Ressourcenverschwendung", "Sicherheitsverdacht",
                        "Sinnvolle Funktion", "Unnoetiger Dauerbetrieb",
                        "Gefaehrdung der Grundversorgung"):
            self.assertIn(zustand, text)

    def test_zusatz_ist_gekennzeichnet(self):
        text = DOC.read_text(encoding="ascii")
        self.assertIn("Zusatz-Einordnung (NICHT Teil der Vorlage)", text)
        self.assertIn("NICHT Teil der Vorlage", text)
        # VORLAGE-Wortlaut-Markierung existiert (Uebernahme-Treue)
        self.assertIn("VORLAGE-Wortlaut", text)

    def test_verweis_ziele_existieren(self):
        for ziel in REQUIRED_REF_TARGETS:
            p = REPO / ziel
            self.assertTrue(p.exists(), "Verweisziel fehlt: " + ziel)


if __name__ == "__main__":
    unittest.main()
