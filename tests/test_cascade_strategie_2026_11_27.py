"""Tests: Kaskaden-Strategie 27.11.2026 (#533-Folge, Betreiber-Auftrag
Macro-F1 >= 0.900). Rechnet alle gepinnten Werte aus der abgelegten
Datenbasis NEU (weicht die Basis, schlagen die Tests bewusst aus).
TEXTDOC != MESSUNG: Pins hier sind gegen die JSONL, nicht gegen Prosa.
"""

from __future__ import annotations

import pathlib
import unittest

from controller import cascade_history_eval as che

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = REPO_ROOT / "docs/cascade-history/v91-ci-suiten-2026-11-25-bis-27.jsonl"
DOC = REPO_ROOT / "docs/V91-KASKADEN-STRATEGIE-2026-11-27.md"

_report = che.evaluate(DATA)
_det = _report["detectors"] if _report["state"] == "EVALUATED" else {}


def _gap_detector(minutes: float):
    return lambda pair: pair["prev_red"] and pair["gap_min"] <= minutes


class TestDatenbasisFensterZwei(unittest.TestCase):
    def test_suites_und_paare(self):
        self.assertEqual(_report["suites_total"], 233)
        self.assertEqual(_report["suites_red"], 29)
        self.assertEqual(_report["follow_pairs"], 154)
        self.assertEqual(_report["pairs_target_red"], 13)
        self.assertEqual(_report["pairs_prev_red"], 29)

    def test_heilungsquote(self):
        self.assertEqual(_report["healed_after_prev_red"], 16)
        self.assertAlmostEqual(_report["healing_ratio_after_red"], 16 / 29, places=4)

    def test_fn_null_alle_kaskadendetektoren(self):
        for name, res in _det.items():
            if "zeit" == name:
                continue
            self.assertEqual(res["confusion"]["fn"], 0, name)


class TestDetektorwerte(unittest.TestCase):
    def test_kaskade_baseline(self):
        res = _det["detector_kaskade_prev_rot"]
        self.assertEqual(res["confusion"], {"tp": 13, "fp": 16, "fn": 0, "tn": 125})
        self.assertAlmostEqual(res["macro_f1"], 0.7794, places=4)

    def test_zeit_negativkontrolle(self):
        res = _det["detector_zeit"]
        self.assertEqual(res["confusion"]["fp"], 116)
        self.assertAlmostEqual(res["macro_f1"], 0.2422, places=4)

    def test_gap_1_0_hauptkandidat_insample(self):
        pairs = che.follow_pairs(che.load_suites(DATA)["suites"])
        cm = che.confusion(pairs, _gap_detector(1.0))
        sc = che.class_scores(cm)
        self.assertEqual(cm, {"tp": 13, "fp": 5, "fn": 0, "tn": 136})
        self.assertAlmostEqual(sc["macro_f1"], 0.9103, places=4)

    def test_gap_0_5_robustheitsvariante(self):
        pairs = che.follow_pairs(che.load_suites(DATA)["suites"])
        cm = che.confusion(pairs, _gap_detector(0.5))
        sc = che.class_scores(cm)
        self.assertEqual(cm["fn"], 4)
        self.assertEqual(cm["fp"], 0)
        self.assertAlmostEqual(sc["macro_f1"], 0.902, places=3)

    def test_gap_trennzone(self):
        pairs = che.follow_pairs(che.load_suites(DATA)["suites"])
        tp_gaps = [p["gap_min"] for p in pairs if p["prev_red"] and p["cur_red"]]
        fp_gaps = [p["gap_min"] for p in pairs if p["prev_red"] and not p["cur_red"]]
        self.assertLessEqual(max(tp_gaps), 0.72)
        self.assertGreater(min(fp_gaps), 0.64)


class TestMetrikMechanikF1Null(unittest.TestCase):
    def test_immer_rot_ergibt_f1_gruen_null(self):
        pairs = che.follow_pairs(che.load_suites(DATA)["suites"])
        cm = che.confusion(pairs, lambda pair: True)
        sc = che.class_scores(cm)
        self.assertEqual(sc["f1_green"], 0.0)
        self.assertAlmostEqual(sc["f1_red"], 2 * (13 / 154) / (1 + 13 / 154), places=6)

    def test_immer_gruen_ergibt_f1_rot_null(self):
        pairs = che.follow_pairs(che.load_suites(DATA)["suites"])
        cm = che.confusion(pairs, lambda pair: False)
        sc = che.class_scores(cm)
        self.assertEqual(sc["f1_red"], 0.0)
        self.assertEqual(cm["fn"], 13)

    def test_leere_klasse_zaehlt_als_null(self):
        # Detektor, der nie ROT sagt auf einem Fenster ohne ROT-Ziel
        # zeigt die Konvention _safe_div(0, 0) = 0.0 -> F1 = 0.000.
        sc = che.class_scores({"tp": 0, "fp": 0, "fn": 0, "tn": 10})
        self.assertEqual(sc["f1_red"], 0.0)
        self.assertEqual(sc["macro_f1"], (0.0 + 1.0) / 2.0)


class TestStrategieDocPins(unittest.TestCase):
    def test_doc_vorhanden_und_ascii(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertGreater(len(text), 3000)
        text.encode("ascii")

    def test_vorregistrierung_und_oneshot(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("ERFOLGSKRITERIUM (vorregistriert)", text)
        self.assertIn("ONE-SHOT", text)
        self.assertIn("IN-SAMPLE != VALIDIERT", text)

    def test_12_testfaelle_und_grenzen(self):
        text = DOC.read_text(encoding="utf-8")
        for i in range(1, 13):
            self.assertIn("\n%d. " % i, text)
        self.assertIn("KEINE_SIGNIFIKANZ_BEI_KLEINEM_N", text)

    def test_negativfaelle_und_f1_null_erklart(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("Heilungen", text)
        self.assertIn("F1 = 0.000 erklaert", text)
        self.assertIn("IMMER-ROT", text)


if __name__ == "__main__":
    unittest.main()
