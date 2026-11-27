"""Tests fuer den Verbund-Stufen-Audit (Stufenplan A-E, Verbund-
Vertrag #590 ANHANG Abschnitt 10: "Jede Stufe ist separat zu
implementieren und zu verifizieren. Nicht implementierte Stufen
bleiben sichtbar offen.").

Pinnen: Evidenz-Verdrahtung gegen den echten Bestand, Verdikte
BELEGT/TEILWEISE_BELEGT/NICHT_GEFUNDEN, fail-closed bei
Messfehlern, KEINE Laufzeit-/Vollzugsbehauptung.
AUDIT != LAUFZEIT, BESTAND != BETRIEB, SCRIPTED != RUNNING.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller import verbund_stufen_audit as vsa


class StufenDefinitionTest(unittest.TestCase):
    def test_fuenf_stufen_a_bis_e(self):
        stufen = [s[0] for s in vsa.STUFEN]
        self.assertEqual(stufen, ["A", "B", "C", "D", "E"])

    def test_kanon_verweis_existiert(self):
        self.assertTrue((ROOT / vsa.KANON_VERWEIS).exists(),
                        "Kanon-Verweisziel fehlt")

    def test_verdikt_vokabular_geschlossen(self):
        # Evidenzpfade duerfen nur in belegten Quellwurzeln liegen; seit
        # dem Ehrlichkeitsfix auch v91_impact_metrics/ (reale
        # messmatrix-Implementierung statt Phantom controller/messmatrix.py).
        erlaubte_prefixe = ("controller/", "v91_impact_metrics/")
        for stufe, beschreibung, bausteine, luecken in vsa.STUFEN:
            self.assertTrue(beschreibung)
            for modul, testdatei in bausteine:
                self.assertTrue(modul.startswith(erlaubte_prefixe),
                                "unerlaubter Evidenzpfad: " + modul)
                self.assertTrue(testdatei.startswith("tests/"))


class EchterBestandTest(unittest.TestCase):
    """Verdikte gegen den echten main-Baum (Messtand: Lookup-Jetzt)."""

    @classmethod
    def setUpClass(cls):
        cls.ergebnis = vsa.audit(str(ROOT))
        cls.nach_stufe = {s["stufe"]: s for s in cls.ergebnis["stufen"]}

    def test_stufe_a_belegt(self):
        stufe = self.nach_stufe["A"]
        self.assertEqual(stufe["verdikt"], "BELEGT")
        self.assertEqual(stufe["evidenz"][0]["modul"],
                         "controller/verbund_arbeitszyklus.py")
        self.assertGreater(stufe["evidenz"][0]["test_funktionen"], 0)

    def test_stufe_b_belegt_mit_geschalossener_luecke(self):
        stufe = self.nach_stufe["B"]
        # PR #600 schloss die Luecken (getrennte Instanzen + E2E):
        # alle 5 Primitive vorhanden, Restluecke dokumentiert offen.
        self.assertEqual(stufe["verdikt"], "TEILWEISE_BELEGT")
        self.assertGreater(len(stufe["evidenz"]), 1)
        self.assertTrue(all(
            b["modul_vorhanden"] and b["test_funktionen"] > 0
            for b in stufe["evidenz"]))
        joined = " ".join(stufe["offene_luecken"])
        self.assertIn("Kriterium 1 von #592", joined)
        self.assertNotIn("getrennte lokale Testinstanzen", joined)

    def test_stufe_c_nicht_gefunden(self):
        stufe = self.nach_stufe["C"]
        self.assertEqual(stufe["verdikt"], "NICHT_GEFUNDEN")
        self.assertEqual(stufe["evidenz"], [])
        self.assertTrue(stufe["offene_luecken"])

    def test_stufe_d_teilweise(self):
        stufe = self.nach_stufe["D"]
        self.assertEqual(stufe["verdikt"], "TEILWEISE_BELEGT")
        joined = " ".join(stufe["offene_luecken"])
        self.assertIn("#101/#103", joined)
        # Ehrlichkeitspins: keine Phantom-Evidenz, Baseline-Register
        # als Stufe-D-Baustein, alle Module existieren wirklich.
        module = [b["modul"] for b in stufe["evidenz"]]
        self.assertNotIn("controller/messmatrix.py", module)
        self.assertIn("v91_impact_metrics/metrics.py", module)
        self.assertIn("controller/baseline_register.py", module)
        self.assertTrue(all(b["modul_vorhanden"] and b["test_funktionen"] > 0
                             for b in stufe["evidenz"]))

    def test_stufe_e_nicht_gefunden(self):
        self.assertEqual(self.nach_stufe["E"]["verdikt"],
                         "NICHT_GEFUNDEN")

    def test_regeln_dokumentiert(self):
        for regel in ("AUDIT != LAUFZEIT", "BESTAND != BETRIEB",
                      "NICHT_GEFUNDEN != NICHT_EXISTIERT"):
            self.assertIn(regel, self.ergebnis["regeln"])

    def test_alle_verdikte_im_vokabular(self):
        for stufe in self.ergebnis["stufen"]:
            self.assertIn(stufe["verdikt"],
                         ("BELEGT", "TEILWEISE_BELEGT", "NICHT_GEFUNDEN"))


class TempTreeVerhaltenTest(unittest.TestCase):
    def test_leerer_baum_nicht_gefunden(self):
        with tempfile.TemporaryDirectory() as tmp:
            ergebnis = vsa.audit(tmp)
            for stufe in ergebnis["stufen"]:
                if stufe["evidenz"]:
                    self.assertEqual(stufe["verdikt"],
                                     "NICHT_GEFUNDEN")

    def test_unvollstaendiger_baum_teilweise(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "controller"))
            with open(os.path.join(tmp, "controller",
                                   "verbund_arbeitszyklus.py"), "w",
                      encoding="utf-8") as handle:
                handle.write("x = 1\n")
            ergebnis = vsa.audit(tmp)
            stufe_a = {s["stufe"]: s for s in ergebnis["stufen"]}["A"]
            self.assertEqual(stufe_a["verdikt"], "TEILWEISE_BELEGT")
            self.assertFalse(
                stufe_a["evidenz"][0]["testdatei_vorhanden"])

    def test_wurzel_ungueltig_fail_closed(self):
        with self.assertRaises(vsa.VerbundStufenAuditError):
            vsa.audit(os.path.join(tempfile.gettempdir(),
                                   "gibt-es-nicht-2190"))

    def test_syntaxfehler_ist_messfehler(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "tests"))
            with open(os.path.join(tmp, "tests",
                                   "test_verbund_arbeitszyklus.py"),
                      "w", encoding="utf-8") as handle:
                handle.write("def test_x(:\n")
            with self.assertRaises(SyntaxError):
                vsa.audit(tmp)

    def test_zaehle_test_funktionen_ast(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = os.path.join(tmp, "t.py")
            with open(pfad, "w", encoding="utf-8") as handle:
                handle.write(
                    "def test_a():\n    pass\n\n"
                    "def helper():\n    pass\n\n"
                    "class T:\n    def test_b(self):\n        pass\n")
            self.assertEqual(vsa._zaehle_test_funktionen(pfad), 2)


class CliTest(unittest.TestCase):
    def test_cli_json_rundlauf(self):
        proc = subprocess.run(
            [sys.executable, "-m", "controller.verbund_stufen_audit",
             "--path", str(ROOT), "--json"],
            capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        daten = json.loads(proc.stdout)
        self.assertEqual(len(daten["stufen"]), 5)
        self.assertEqual(daten["version"], vsa.VERSION)

    def test_cli_self_check(self):
        proc = subprocess.run(
            [sys.executable, "-m", "controller.verbund_stufen_audit",
             "--path", str(ROOT), "--self-check"],
            capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SELF-CHECK OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
