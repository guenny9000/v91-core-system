"""Tests fuer controller/regression_auswahl.py (unittest, stdlib-only).

Pinnen nach dem Kodex-Muster: kuratierte Tier-Module und Smoke-Tests
existieren AM ECHTEN BESTAND, Auswahl bleibt EMPFEHLUNG != PASS,
fail-closed Sonden, CLI-Exitcodes, NIEMALS Ersatz fuer Full-Run."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.regression_auswahl import (
    RegressionAuswahlError,
    SMOKE_TESTS,
    TIERS,
    TIER_MODULE,
    main,
    test_datei_fuer as datei_fuer,
    tier_fuer_module,
    waehle_regression,
)


class BestandsPinTest(unittest.TestCase):
    def test_tier_module_existieren_am_bestand(self):
        for tier, module in TIER_MODULE.items():
            self.assertIn(tier, TIERS)
            for mod in module:
                self.assertTrue(
                    (ROOT / "controller" / f"{mod}.py").exists(),
                    f"Tier-{tier}-Modul fehlt im Bestand: {mod}",
                )

    def test_smoke_tests_existieren_am_bestand(self):
        for eintrag in SMOKE_TESTS:
            self.assertTrue((ROOT / eintrag).exists(), f"Smoke-Test fehlt: {eintrag}")

    def test_kein_modul_in_zwei_tiers(self):
        alle = [m for module in TIER_MODULE.values() for m in module]
        self.assertEqual(len(alle), len(set(alle)), "Modul in mehreren Tiers")


class AuswahlLogikTest(unittest.TestCase):
    def test_tier0_aenderung_verlangt_groesseren_regressionsteil(self):
        out = waehle_regression(["controller/emergency_stop.py"])
        self.assertEqual(out["tier"], 0)
        self.assertIn("PFLICHT-EMPFEHLUNG", out["hinweis"])

    def test_tier1_hat_smoke_kern(self):
        out = waehle_regression(["controller/status_exchange.py"])
        self.assertEqual(out["tier"], 1)
        self.assertTrue(set(SMOKE_TESTS) <= set(out["empfohlene_tests_ebene_3_pr"]))

    def test_tier2_ist_modulbezogen_plus_kern(self):
        out = waehle_regression(["controller/index_lint.py"])
        self.assertEqual(out["tier"], 2)
        self.assertIn("tests/test_index_lint.py", out["empfohlene_tests_ebene_3_pr"])

    def test_nur_testdatei_geaendert(self):
        out = waehle_regression(["tests/test_formeln_konsolidierung.py"])
        self.assertIsNone(out["tier"])
        self.assertIn("tests/test_formeln_konsolidierung.py", out["empfohlene_tests_ebene_3_pr"])

    def test_nightly_und_release_sind_unersetzbar(self):
        out = waehle_regression(["controller/trockenlauf.py"])
        self.assertIn("NIE durch Auswahl ersetzbar", out["nightly_full_run"])
        self.assertIn("Security Scan", out["release_gate"])
        self.assertTrue(any("NIGHTLY/RELEASE BLEIBEN UNERSETZBAR" in h or "Nightly/Release bleiben unersetzbar" in h for h in out["ehrengrenzen"]))

    def test_empfehlung_ist_kein_pass(self):
        out = waehle_regression(["controller/ledger.py"])
        for grenze in out["ehrengrenzen"]:
            self.assertIsInstance(grenze, str)
        self.assertIn("AUSWAHL != AUSFUEHRUNG", out["ehrengrenzen"][0])


class FailClosedTest(unittest.TestCase):
    def test_unbekannte_datei_abgelehnt(self):
        with self.assertRaises(RegressionAuswahlError):
            waehle_regression(["controller/gibtsnicht.py"])

    def test_leere_liste_abgelehnt(self):
        with self.assertRaises(RegressionAuswahlError):
            waehle_regression([])

    def test_leerer_string_abgelehnt(self):
        with self.assertRaises(RegressionAuswahlError):
            waehle_regression(["  "])

    def test_doppelte_datei_abgelehnt(self):
        with self.assertRaises(RegressionAuswahlError):
            waehle_regression(["controller/ledger.py", "controller/ledger.py"])

    def test_unbekanntes_tier_bleibt_ehrlich(self):
        # Modul im Bestand, aber unkuriert -> Tier None, kein Vertrauensvorschuss
        out = waehle_regression(["controller/appeal_process.py"])
        self.assertIsNone(out["tier"])
        self.assertIn("appeal_process", out["unbekannte_tier_module"])
        self.assertIn("UNBEKANNT", out["tier_beschreibung"])


class CliTest(unittest.TestCase):
    def test_cli_changed_exit_0(self):
        proc = subprocess.run(
            [sys.executable, "controller/regression_auswahl.py",
             "--changed", "controller/worker.py"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertEqual(out["tier"], 1)

    def test_cli_unbekannt_exit_2(self):
        proc = subprocess.run(
            [sys.executable, "controller/regression_auswahl.py",
             "--changed", "controller/gibtsnicht.py"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 2)

    def test_cli_ohne_args_exit_2(self):
        proc = subprocess.run(
            [sys.executable, "controller/regression_auswahl.py"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 2)

    def test_self_check_markiert_synthetisch(self):
        proc = subprocess.run(
            [sys.executable, "controller/regression_auswahl.py", "--self-check"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("SYNTHETISCH", proc.stdout)
        self.assertIn("NICHT_GEPRUEFT", proc.stdout)

    def test_helper_tier_und_testdatei(self):
        self.assertEqual(tier_fuer_module("controller/emergency_stop.py"), 0)
        self.assertEqual(datei_fuer("controller/index_lint.py"), "tests/test_index_lint.py")


if __name__ == "__main__":
    unittest.main()
