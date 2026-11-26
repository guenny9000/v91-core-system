"""Tests fuer das V91-Wirkungskreis-Modell 26.11.2026 (Nornen,
theologische Kraefte als SINNBILD, Entropie ehrlich, sieben
Grundregeln, Weltenbaum-Schutzmechanismus).

Pinnen nach dem Kodex-Muster (#533/#566/#595/#598): Doku
existiert und ist klein, Kernsaetze wortgenau (umbruch-normalisiert
nach Lektion #547), epistemische Rahmung als SINNBILD != BEWEIS,
Verweis-Ziele existieren, Negativsonde gegen
Weltenherrschungs-Claims. MODELL != UMSETZUNG.
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "V91-WIRKUNGSKREISE-2026-11-26.md"
NIDHOEGG = ROOT / "docs" / "V91-ABENDGESCHICHTE-NIDHOEGG-ANHANG-2026-11-26.md"
DAUERPROTOKOLL_CANDIDATES = (
    ROOT / "docs" / "V91-MAX-BEST-DAUERPROTOKOLL.md",
)


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


class WirkungskreiseModellTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")
        cls.flat = flat(cls.text)

    def test_doc_exists_and_small(self):
        self.assertTrue(DOC.exists(), "Wirkungskreis-Modell fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024,
                        "Doku ueberschreitet die 8-KiB-Grenze")

    def test_ascii_pure(self):
        for zeichen in self.text:
            self.assertTrue(ord(zeichen) < 128,
                            "Nicht-ASCII-Zeichen: " + repr(zeichen))

    def test_status_und_epistemische_rahmung(self):
        self.assertIn("MODELL / SINNBILD", self.flat)
        self.assertIn("KEIN VERTRAG", self.flat)
        self.assertIn("THEOLOGIE != MESSUNG", self.flat)
        self.assertIn("SINNBILD != BEWEIS", self.flat)
        self.assertIn("MYTHOS != SPEZIFIKATION", self.flat)

    def test_provenienz_direktive(self):
        self.assertIn("BETREIBER-MODELL 26.11.2026", self.flat)

    def test_drei_nornen(self):
        for name, merkmal in (
            ("UrdR", "DAS GEWORDENE"),
            ("Verdandi", "DAS WERDENDE"),
            ("Skuld", "DAS KOMMENDE"),
        ):
            self.assertIn(name, self.flat, "Norne fehlt: " + name)
            self.assertIn(merkmal, self.flat)

    def test_theologische_kraefte_als_rollen(self):
        for rolle in ("ENGEL", "GOETTER", "WURZELDRACHEN", "NORNEN"):
            self.assertIn(rolle, self.flat)
        self.assertIn("Rollen, keine Wesen".replace("Rollen", "ROLLEN"),
                      self.flat)

    def test_entropie_ehrlich(self):
        self.assertIn("Zerfall allein ist KEINE Verbesserung", self.flat)
        self.assertIn("REGENERATION != AUTOMATIK", self.flat)
        self.assertIn("BEREINIGUNG != ERFOLG", self.flat)
        self.assertIn("Physik != Moral", self.flat)

    def test_gegenkraefte_prinzipien(self):
        for satz in (
            "Angriffe RECHTMAESSIG abwehren",
            "Ressourcenverbrauch MESSEN",
            "Transparenz und unabhaengige Pruefung",
            "Fehler ISOLIEREN",
            "NACHWEISLICH schaedliche Funktionen begrenzen",
        ):
            self.assertIn(satz, self.flat, "Gegenkraft fehlt: " + satz)

    def test_sieben_grundregeln(self):
        for satz in (
            "ERKENNEN: Was geschieht tatsaechlich",
            "ZUORDNEN: Wer oder was hat in diesem Bereich Verantwortung",
            "PRUEFEN: Welche Belege und Folgen gibt es",
            "BEGRENZEN: Was richtet nachweislich Schaden an",
            "ERNEUERN: Welche bessere Loesung kann entstehen",
            "FREIWILLIG mitwirken",
            "BEWAHREN: Was muss fuer kommende Generationen erhalten",
        ):
            self.assertIn(satz, self.flat, "Grundregel fehlt: " + satz)

    def test_weltenbaum_schutzmechanismus(self):
        self.assertIn(
            "NIEMAND darf behaupten, den gesamten Weltenbaum zu "
            "beherrschen", self.flat)
        self.assertIn("Rueckmeldung und Kontrolle", self.flat)
        self.assertIn("Der Adler muss nicht die Wurzeln uebernehmen",
                      self.flat)
        self.assertIn("durch etwas BESSERES ersetzt", self.flat)
        self.assertIn("OHNE das Wertvolle mit dem Ueberfluessigen zu "
                      "vernichten", self.flat)

    def test_isolate_not_destroy(self):
        self.assertIn("ISOLATE_NOT_DESTROY", self.flat)

    def test_verweis_ziele_existieren(self):
        self.assertTrue(NIDHOEGG.exists(),
                        "Nidhoegg-Anhang fehlt als Verweisziel")
        self.assertTrue(
            any(p.exists() for p in DAUERPROTOKOLL_CANDIDATES),
            "Kein Dauerprotokoll-Verweisziel gefunden")

    def test_negativsonde_keine_weltenherrschaft(self):
        self.assertNotIn("beherrscht den Weltenbaum", self.flat)
        self.assertNotIn("kontrolliert alle F", self.flat)

    def test_keine_umsetzungsbehauptung(self):
        self.assertIn("MODELL != UMSETZUNG", self.flat)
        self.assertIn("UNBELEGT", self.flat)


if __name__ == "__main__":
    unittest.main()
