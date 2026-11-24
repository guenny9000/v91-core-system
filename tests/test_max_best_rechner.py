"""
Tests fuer controller/max_best_rechner (ausfuehrbare Kernformeln).

Max-BEST-Formeln sind hier RECHENBAR und die Ehrlichkeitsregeln sind
verriegelt: UNKNOWN propagiert (niemals 0, niemals geraten),
Domainverletzungen sind fail-closed Fehler (KEIN stilles Clampen),
Nebenbedingungen werden NICHT simuliert (RECHNEN != ENTSCHEIDEN).
Jede Formelfunktion deckt den Abschnitt-2-Katalog des Kern-Dokuments
ab (Formel != Messung: Eingaben sind ANGABEN).
"""
from __future__ import annotations

import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from controller import max_best_rechner as mbr


class FormelTest(unittest.TestCase):
    def test_gesamtnutzen_exakt(self):
        r = mbr.gesamtnutzen(80, 5, 15)
        self.assertEqual(r, {"wert": 60.0, "status": "BERECHNET"})

    def test_risiko_formel(self):
        self.assertEqual(mbr.risiko(0.1, 100)["wert"], 10.0)

    def test_restrisiko_formel(self):
        self.assertAlmostEqual(mbr.restrisiko(10.0, 0.8)["wert"], 2.0)
        self.assertEqual(mbr.restrisiko(10.0, 1.0)["wert"], 0.0)

    def test_nutzen_pro_aufwand_und_aufwand_null(self):
        self.assertEqual(mbr.nutzen_pro_aufwand(80, 100)["wert"], 0.8)
        self.assertEqual(mbr.nutzen_pro_aufwand(80, 0)["status"],
                         "NICHT_GEPRUEFT")

    def test_vertrauen(self):
        self.assertAlmostEqual(mbr.vertrauen(1.0, 0.5, 0.5)["wert"], 0.25)

    def test_unknown_propagation_alle_quellen(self):
        for unknown in (None, "UNKNOWN", "Unbekannt", float("nan")):
            self.assertEqual(mbr.risiko(unknown, 100)["status"],
                             "NICHT_GEPRUEFT")
            self.assertIsNone(mbr.risiko(unknown, 100)["wert"])
        self.assertEqual(mbr.risiko(0.1, None)["status"], "NICHT_GEPRUEFT")
        self.assertEqual(mbr.gesamtnutzen(None, None, None)["status"],
                         "NICHT_GEPRUEFT")


class DomainTest(unittest.TestCase):
    def test_wahrscheinlichkeit_ueber_eins_fail_closed(self):
        with self.assertRaises(mbr.MaxBestInputError):
            mbr.risiko(1.5, 100)

    def test_negative_werte_fail_closed(self):
        with self.assertRaises(mbr.MaxBestInputError):
            mbr.gesamtnutzen(-1, 0, 0)
        with self.assertRaises(mbr.MaxBestInputError):
            mbr.effizienz(10, -2)

    def test_booles_und_typen_fail_closed(self):
        with self.assertRaises(mbr.MaxBestInputError):
            mbr.vertrauen(True, 0.5, 0.5)
        with self.assertRaises(mbr.MaxBestInputError):
            mbr.risiko("vielleicht", 100)

    def test_unendlich_fail_closed(self):
        with self.assertRaises(mbr.MaxBestInputError):
            mbr.gesamtnutzen(float("inf"), 0, 1)

    def test_bilanz_zaehlt_richtig(self):
        report = mbr.berechne({"gesamtnutzen": {"nutzen": 10, "schaden": 0,
                                                "aufwand": 10},
                               "risiko": {"wahrscheinlichkeit": None,
                                          "schadenshoehe": 1}})
        self.assertEqual(report["bilanz"]["formeln"], 2)
        self.assertEqual(report["bilanz"]["nicht_geprueft"], 1)

    def test_unbekannter_bereich_fail_closed(self):
        with self.assertRaises(mbr.MaxBestInputError):
            mbr.berechne({"welteroberung": {}})


class CliTest(unittest.TestCase):
    def test_exit_0_wenn_alles_berechenbar(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = mbr.main(["/tmp/a.json"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["bilanz"]["nicht_geprueft"], 0)

    def test_exit_1_bei_unknown_ehrlich(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as tf:
            json.dump({"restrisiko": {"risiko": None, "wirksamkeit": 0.5}},
                      tf)
            path = tf.name
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = mbr.main([path])
        self.assertEqual(code, 1)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["restrisiko"]["status"], "NICHT_GEPRUEFT")

    def test_exit_2_bei_domainfehler(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = mbr.main(["/tmp/c.json"])
        self.assertEqual(code, 2)
        self.assertIn("fail-closed", buf.getvalue())

    def test_fehlende_datei_exit_2(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = mbr.main(["/tmp/existiert-nicht-xyz.json"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
