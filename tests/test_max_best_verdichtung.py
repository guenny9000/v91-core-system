"""
Doku-pinnende Tests fuer docs/V91-MAX-BEST-VERDICHTUNG.md
(Betreiber-Vorlage 28.11.2026, wortgetreu uebernommen,
ASCII-transliteriert).

Muster: test_max_best_dauerprotokoll (#544). Diese Tests sichern,
dass das Dokument (a) existiert und kompakt bleibt (< 8 KiB),
(b) die Vorlage wortgetreu traegt (alle Abschnitte, beide
Prioritaeten-Listen, alle sechs Endlosschleifen-Stationen in
Reihenfolge), (c) KEINE Umsetzungsbehauptung enthaelt
(DOKUMENTIERT != INSTALLIERT), (d) die zitierten Verweis-Ziele
real existieren, (e) ASCII-pure bleibt, (f) die Zusatz-Abschnitte
klar als ZUSATZ gekennzeichnet sind, NICHT als Teil der Vorlage.

Dauerlehre #547: Phrasen-Asserts muessen Zeilenumbruch-normalisiert
pruefen (re.sub \\s+), sonst schlaegt ein Zeilenumbruch INNERHALB
der Phrase fehl (Rot-Ursache des ersten Laufs dieses PR: 2 statt 3
ZUSATZ-Vorkommen, weil der Header-Umbruch die Phrase zerriss).
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

REPO = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "V91-MAX-BEST-VERDICHTUNG.md"


def _normalisiert(text: str) -> str:
    """Zeilenumbrueche/Mehrfach-Leerzeichen -> Einzel-Leerzeichen."""
    return re.sub(r"\s+", " ", text)


REQUIRED_INVARIANTS = (
    "Alles, was nachweisbar",
    "Menschen, Natur und Zukunft",
    "hilft, soll verbessert werden.",
    "soll erkannt und reduziert werden.",
    "Gute Ideen verbreiten.",
    "Nuetzliches Wissen teilen.",
    "Erfolgreiche Loesungen dokumentieren.",
    "Bewaehrte Ablaeufe wiederholen.",
    "wenn sie dort ebenfalls",
    "Dann erneut beginnen.",
    "Nicht maximale Behauptungen.",
    "Sondern maximale",
    "nachweisbare Ergebnisse.",
    "Was wurde konkret verbessert",
    "wie kann es weiter verbessert",
    "DOKUMENTIERT != INSTALLIERT",
    "UNKNOWN != PASS",
    "REQUEST != AUTHORIZATION",
)

MEHR_PRIORITAETEN = (
    "Frieden",
    "Gesundheit",
    "Bildung",
    "Wissenschaft",
    "Naturschutz",
    "Versorgungssicherheit",
    "Barrierefreiheit",
    "Zusammenarbeit",
    "Transparenz",
)

WENIGER_PRIORITAETEN = (
    "Verschwendung",
    "unnoetige Buerokratie",
    "Fehler",
    "Umweltbelastung",
    "vermeidbare Konflikte",
)

SCHLEIFEN_STATIONEN = (
    "ERKENNEN",
    "PRUEFEN",
    "VERBESSERN",
    "NACHWEISEN",
    "TEILEN",
    "WIEDERHOLEN",
)

FORBIDDEN_CLAIMS = (
    # KEINE Umsetzungsbehauptung. Achtung: Der Satz "Alles ist
    # geloest." steht als zitiertes NEGATIV-Beispiel in der
    # Vorlage und ist daher hier bewusst NICHT verboten.
    "erfolgreich implementiert",
    "bereits umgesetzt",
    "Installation abgeschlossen",
)

REQUIRED_REF_TARGETS = (
    "docs/V91-MAX-BEST-GELUEBNIS.md",
    "docs/V91-MAX-BEST-GLOBAL-DOCTRINE.md",
    "docs/V91-MAX-BEST-ENTDECKUNGSAUFTRAG.md",
    "docs/V91-MAX-BEST-KREISLAUF-ENTSCHEIDUNGSFILTER.md",
    "docs/V91-MAX-BEST-PROTOCOL.md",
    "docs/V91-MAX-BEST-REALRUN-ZYKLUSCHECK.md",
    "docs/V91-MAX-BEST-WELTWEITE-ENTSCHLACKUNG-LEITLINIE.md",
)


class MaxBestVerdichtungDokuTest(unittest.TestCase):
    def test_dokument_existiert_und_ascii_pure(self):
        self.assertTrue(DOC.exists(), "Verdichtungs-Doku fehlt")
        text = DOC.read_bytes().decode("ascii")
        self.assertGreater(len(text), 2000)
        self.assertIn("MAX-BEST Verdichtung", text)

    def test_dokument_kompakt_unter_8kib(self):
        self.assertLess(DOC.stat().st_size, 8 * 1024)

    def test_invarianten_wortvermoeglich(self):
        text = _normalisiert(DOC.read_text(encoding="ascii"))
        for satz in REQUIRED_INVARIANTS:
            self.assertIn(satz, text, "fehlt: " + satz)

    def test_mehr_prioritaeten_alle_da(self):
        text = _normalisiert(DOC.read_text(encoding="ascii"))
        for p in MEHR_PRIORITAETEN:
            self.assertIn(p, text, "Mehr-Prioritaet fehlt: " + p)

    def test_weniger_prioritaeten_alle_da(self):
        text = _normalisiert(DOC.read_text(encoding="ascii"))
        for p in WENIGER_PRIORITAETEN:
            self.assertIn(p, text, "Weniger-Prioritaet fehlt: " + p)

    def test_endlosschleife_stationen_in_reihenfolge(self):
        text = _normalisiert(DOC.read_text(encoding="ascii"))
        pos = -1
        for station in SCHLEIFEN_STATIONEN:
            p = text.find(station, pos + 1)
            self.assertGreater(p, pos, "Station fehlt/unsortiert: " + station)
            pos = p

    def test_keine_umsetzungsbehauptung(self):
        text = _normalisiert(DOC.read_text(encoding="ascii")).lower()
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim.lower(), text,
                            "UMSETZUNGSBEHAUPTUNG: " + claim)

    def test_zusatz_ist_gekennzeichnet(self):
        text = _normalisiert(DOC.read_text(encoding="ascii"))
        self.assertIn("ZUSATZ, NICHT Teil der Vorlage", text)
        self.assertIn("wortgetreu", text)
        self.assertGreaterEqual(
            text.count("ZUSATZ, NICHT Teil der Vorlage"), 3)

    def test_transliteration_dokumentiert(self):
        text = _normalisiert(DOC.read_text(encoding="ascii"))
        self.assertIn("Umlaute transliteriert", text)
        self.assertIn("UNENDLICH", text)

    def test_verweis_ziele_existieren(self):
        for ziel in REQUIRED_REF_TARGETS:
            p = REPO / ziel
            self.assertTrue(p.exists(), "Verweisziel fehlt: " + ziel)


if __name__ == "__main__":
    unittest.main()
