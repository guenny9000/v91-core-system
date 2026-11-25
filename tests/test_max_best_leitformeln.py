"""
Doku- und Logik-pinnende Tests fuer controller/max_best_leitformeln.py
(P6, 25.11.2026): die vier Leitformeln aus docs/V91-FORMELN.md sind
maschinenpruefbar ausfuehrbar; Disziplin REUSE aus max_best_rechner.
Gesichtet wird: Handrechnungen, Unknown-Propagation, fail-closed
Domains, Grenzen-Deklaration, CLI-Exitcodes. Tests sind self-contained
(nur eigene tempdateien; NIE Dateien ausserhalb tempfile).
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller import max_best_leitformeln as lf
from controller.max_best_rechner import MaxBestInputError


class MitwirkungTest(unittest.TestCase):
    def test_handrechnung(self):
        r = lf.mitwirkung_w(1.0, 2.0, 3.0, 4.0, 1.0, 1.0, 1.0, 0.5)
        self.assertEqual(r["status"], "BERECHNET")
        self.assertAlmostEqual(r["wert"], 1 + 2 + 3 - 2.0)

    def test_unknown_propagiert_nicht_null(self):
        r = lf.mitwirkung_w(1.0, 2.0, 3.0, 4.0, None, 1.0, 1.0, 0.5)
        self.assertEqual(r["status"], "NICHT_GEPRUEFT")
        self.assertIsNone(r["wert"])

    def test_parameter_muss_echt_positiv(self):
        for schlechter_wert in (0.0, -1.0):
            with self.assertRaises(MaxBestInputError):
                lf.mitwirkung_w(schlechter_wert, 1, 1, 1, 1, 1, 1, 1)

    def test_eingaben_nicht_negativ(self):
        with self.assertRaises(MaxBestInputError):
            lf.mitwirkung_w(1, 1, 1, 1, -0.1, 1, 1, 1)


class StabilitaetTest(unittest.TestCase):
    def test_handrechnung(self):
        r = lf.stabilitaet_g(1.0, 1.0, 0.0, 1.0, 0.0)
        self.assertEqual(r["status"], "BERECHNET")
        self.assertAlmostEqual(r["wert"], 1.0)

    def test_uebermut_dmpft(self):
        r = lf.stabilitaet_g(1.0, 1.0, 0.5, 1.0, 1.0)
        self.assertAlmostEqual(r["wert"], 0.75)

    def test_demut_echt_groesser_null(self):
        with self.assertRaises(MaxBestInputError):
            lf.stabilitaet_g(1, 1, 0.5, 0.0, 0.0)

    def test_dankbarkeit_domain(self):
        with self.assertRaises(MaxBestInputError):
            lf.stabilitaet_g(1, 1, 1.5, 0.5, 0.0)

    def test_unknown_propagiert(self):
        r = lf.stabilitaet_g(1, 1, 0.5, None, 0.0)
        self.assertEqual(r["status"], "NICHT_GEPRUEFT")


class VerbesserungTest(unittest.TestCase):
    def test_handrechnung(self):
        r = lf.verbesserung_schritt(10.0, 0.5, 20.0)
        self.assertEqual(r["status"], "BERECHNET")
        self.assertAlmostEqual(r["wert"], 15.0)

    def test_eta_offen_links(self):
        for schlecht in (0.0, 1.5, -0.1):
            with self.assertRaises(MaxBestInputError):
               lf.verbesserung_schritt(10.0, schlecht, 20.0)

    def test_eta_eins_errechnet_optimum(self):
        r = lf.verbesserung_schritt(10.0, 1.0, 20.0)
        self.assertAlmostEqual(r["wert"], 20.0)


class BestandspflegeTest(unittest.TestCase):
    def test_handrechnung(self):
        r = lf.bestandspflege_q(10, 1, 1)
        self.assertAlmostEqual(r["wert"], 10.0 / 3.0)

    def test_null_ist_ein_gueltiger_zaehlwert(self):
        r = lf.bestandspflege_q(0, 0, 5)
        self.assertEqual(r["status"], "BERECHNET")
        self.assertEqual(r["wert"], 0.0)

    def test_unknown_propagiert_nichts_erfunden(self):
        r = lf.bestandspflege_q(None, 1, 1)
        self.assertEqual(r["status"], "NICHT_GEPRUEFT")
        self.assertIsNone(r["wert"])


class AuftragUndCliTest(unittest.TestCase):
    def test_berechne_bericht_und_grenzen(self):
        bericht = lf.berechne({"bestandspflege": {"i_geprueft": 9,
                                                  "r_unnoetig": 0,
                                                  "f_ungeprueft": 0}})
        self.assertEqual(bericht["bilanz"]["nicht_geprueft"], 0)
        self.assertTrue(bericht["grenzen"]["rechnen != entscheiden"])
        self.assertIn("ANGABE != BEWEIS", bericht["grenzen"]["eingaben"])

    def test_unbekannter_bereich_fail_closed(self):
        with self.assertRaises(MaxBestInputError):
            lf.berechne({"wunderformel": {}})

    def _cli(self, payload) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            datei = pathlib.Path(tmp) / "auftrag.json"
            datei.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(ROOT / "controller" / "max_best_leitformeln.py"),
                 str(datei)], capture_output=True, text=True)

    def test_cli_exit0_komplett(self):
        p = self._cli({"stabilitaet": {"lambda": 1, "kappa": 1,
                                      "dankbarkeit": 0.5, "demut": 1.0,
                                      "uebermut": 0.0}})
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_cli_exit1_bei_unknown(self):
        p = self._cli({"verbesserung": {"b_n": None, "eta": 0.5,
                                        "o_real": 1.0}})
        self.assertEqual(p.returncode, 1)

    def test_cli_exit2_bei_kaputt(self):
        p = self._cli({"mitwirkung": {"alpha": "definitiv keine Zahl"}})
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
