"""
Doku-pinnende Tests fuer docs/V92-MAX-BEST-PRAKISPAKET.md
(Fremd-Entwurf Google-Modell via Betreiber-Relay 28.11.2026,
UEBERNAHME-AENDERUNGEN offengelegt, transliteriert).

Muster: test_max_best_verdichtung.py (#630). Diese Tests sichern,
dass das Dokument (a) existiert und kompakt bleibt (< 8 KiB),
(b) alle drei Paket-Teile traegt (Einladung, Praxis-Checkliste,
Anwendungs-Matrix), (c) die Checklisten-Schritte je auf eine
ENDLOSSCHLEIFE-Station des Kanons (#630) abgebildet sind,
(d) die Regel-Korrekturmarker gegenueber dem Fremd-Entwurf enthaelt
(KEIN DAEMON, Wirkung NICHT_GEPRUEFT, REQUEST != AUTHORIZATION,
PUBLIKATION = BETREIBER), (e) die zitierten Verweis-Ziele real
existieren, (f) ASCII-pure bleibt, (g) KEINE
Umsetzungsbehauptung enthaelt (DOKUMENTIERT != INSTALLIERT).

Dauerlehre #547: Phrasen-Asserts zeilenumbruch-normalisiert
pruefen (re.sub \\s+).
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

REPO = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "V92-MAX-BEST-PRAKISPAKET.md"


def _normalisiert(text: str) -> str:
    """Zeilenumbrueche/Mehrfach-Leerzeichen -> Einzel-Leerzeichen."""
    return re.sub(r"\s+", " ", text)


class PraxispaketDokumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = DOC.read_text(encoding="utf-8")
        cls.flat = _normalisiert(cls.text)

    def test_dokument_existiert_und_kompakt(self) -> None:
        self.assertTrue(DOC.is_file(), "docs/V92-MAX-BEST-PRAKISPAKET.md fehlt")
        self.assertLessEqual(DOC.stat().st_size, 8192,
                             "Dokument muss < 8 KiB bleiben")

    def test_ascii_pure(self) -> None:
        raw = DOC.read_bytes()
        non_ascii = [b for b in raw if b > 127]
        self.assertEqual(non_ascii, [], "Dokument muss ASCII-pure sein")

    def test_fremd_entwurf_offengelegt(self) -> None:
        self.assertIn("FREMD-ENTWURF", self.flat)
        self.assertIn("UEBERNAHME-AENDERUNGEN", self.flat)
        self.assertIn("BETREIBER-BEZEICHNUNG", self.flat)
        self.assertIn("KEIN neuer Systemstand", self.flat)

    def test_einladungsteil_vorhanden(self) -> None:
        self.assertIn("EINLADUNG ZUR MITGESTALTUNG: V92 MAX-BEST", self.flat)
        self.assertIn("Keine leeren Versprechen, nur messbare Ergebnisse.", self.flat)
        self.assertIn("AUTARKIE:", self.flat)
        self.assertIn("KOOPERATIVE WEITERBILDUNG:", self.flat)
        self.assertIn("VOLLE SKALIERUNG:", self.flat)
        self.assertIn("UNENDLICH", self.flat)

    def test_einladung_erteilt_keine_rechte(self) -> None:
        self.assertIn("EINLADUNG = TEXT", self.flat)
        self.assertIn("verpflichtet niemanden", self.flat)
        self.assertIn("Teilnahme ist freiwillig", self.flat)
        self.assertIn("VERBREITUNG = BETREIBER", self.flat)

    def test_checkliste_sechs_schritte_auf_kanon_stationen(self) -> None:
        stationen = {
            "1. ERKENNEN & HEBEL WAEHLEN": "Station ERKENNEN",
            "2. AUTARKIE-CHECK": "Station PRUEFEN",
            "3. VERBESSERN & MESSEN": "Stationen VERBESSERN + NACHWEISEN",
            "4. DOKUMENTIEREN": "Station NACHWEISEN/TEILEN",
            "5. AKTIVIEREN & WEITERBILDEN": "Station TEILEN",
            "6. SKALIEREN": "Station WIEDERHOLEN",
        }
        for schritt, station in stationen.items():
            self.assertIn(_normalisiert(schritt), self.flat,
                          f"Checklisten-Schritt fehlt: {schritt}")
            self.assertIn(station, self.flat,
                           f"Kanon-Station fehlt: {station}")
        # Kanon-Ergaenzung REUSE vor Neubau ist Teil des Rezepts.
        self.assertIn("REUSE_BEFORE_BUILD", self.flat)
        self.assertIn("Gibt es die Loesung schon?", self.flat)

    def test_korrekturmarker_gegenueber_fremd_entwurf(self) -> None:
        for marker in (
            "KEIN DAEMON",
            "UNENDLICH = LEITBILD != BETRIEBSZUSTAND",
            "NUR IM EIGENEN WIRKUNGSKREIS",
            "REQUEST != AUTHORIZATION",
            "FREIGABE != BERECHTIGUNG Dritter",
            "NICHT_GEPRUEFT",
            "PUBLIKATION = BETREIBER",
        ):
            self.assertIn(marker, self.flat, f"Korrekturmarker fehlt: {marker}")

    def test_matrix_vier_lebensbereiche(self) -> None:
        for bereich in (
            "WISSEN & BILDUNG",
            "TECHNIK & INFRASTRUKTUR",
            "VERSORGUNG & NATUR",
            "ZUSAMMENARBEIT",
        ):
            self.assertIn(bereich, self.flat, f"Lebensbereich fehlt: {bereich}")
        # Praxisbeispiele des Entwurfs bleiben wortnah erhalten.
        self.assertIn("Open Educational Resources", self.flat)
        self.assertIn("Reparatur-Cafes", self.flat)
        self.assertIn("renaturieren", self.flat)
        self.assertIn("Feedback-Runden", self.flat)

    def test_verweisziele_existieren(self) -> None:
        ziele = (
            "docs/V91-MAX-BEST-VERDICHTUNG.md",
            "docs/V91-MAX-BEST-ENTDECKUNGSAUFTRAG.md",
            "docs/V91-MAX-BEST-REALRUN-ZYKLUSCHECK.md",
            "docs/V91-MAX-BEST-KREISLAUF-ENTSCHEIDUNGSFILTER.md",
            "docs/V91-VOLLMACHT-CHARTA.md",
        )
        for ziel in ziele:
            self.assertIn(ziel, self.flat, f"Verweis fehlt im Dokument: {ziel}")
            pfad = REPO / ziel
            self.assertTrue(pfad.is_file(), f"Verweisziel existiert nicht: {ziel}")

    def test_keine_umsetzungsbehauptung(self) -> None:
        self.assertIn("DOKUMENTIERT != INSTALLIERT", self.flat)
        self.assertIn("KEINE neuen Regeln, KEINE neuen Rechte", self.flat)
        self.assertIn("Anwendung ausserhalb GitHub NICHT_GEPRUEFT", self.flat)
        self.assertIn("wirkungs_assessment", self.flat)

    def test_verdichtung_nicht_verdoppelt(self) -> None:
        # Die Kanon-Grundsaetze bleiben NUR in der Verdichtung (#630);
        # dieses Dokument enthaelt sie nicht noch einmal als Regeln.
        self.assertNotIn("ZIELRICHTUNG", self.flat)
        self.assertNotIn("REALITAETSREGEL", self.flat.replace(
            "(REALITAETSREGEL)", ""))


if __name__ == "__main__":
    unittest.main()
