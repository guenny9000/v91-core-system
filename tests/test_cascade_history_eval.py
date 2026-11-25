"""Tests fuer controller.cascade_history_eval (historische Kaskaden-Validierung).

Pinnen die GEMESSENEN Werte gegen die abgelegte Datenbasis in
docs/cascade-history/v91-ci-suiten-2026-11-23-bis-25.jsonl: die Zahlen
im Test sind kein Anspruch, sondern Rechenpruefung der Basis (CLAIM
!= EVIDENCE: weicht die Basis, schlagen diese Tests bewusst aus und
erzwingen einen dokumentierten Datenbasis-Entscheid, KEIN STILLes
Nachziehen).
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

from controller.cascade_history_eval import (  # noqa: E402
    HONESTY_LIMITS,
    class_scores,
    confusion,
    evaluate,
    follow_pairs,
    load_suites,
)

DATA = ROOT / "docs" / "cascade-history" / "v91-ci-suiten-2026-11-23-bis-25.jsonl"


class DataBasisTest(unittest.TestCase):
    def test_data_file_exists(self):
        self.assertTrue(DATA.exists(), "Datenbasis fehlt (CLAIM != EVIDENCE)")

    def test_data_basis_shape(self):
        loaded = load_suites(DATA)
        self.assertTrue(loaded["ok"])
        self.assertEqual(161, len(loaded["suites"]))
        self.assertEqual(0, loaded["malformed_lines"])
        self.assertEqual(24, sum(1 for s in loaded["suites"] if s["red"]))

    def test_no_assertion_without_basis_in_limits(self):
        self.assertIn("VERGANGENHEIT != VORHERSAGE", HONESTY_LIMITS)
        self.assertIn("KEINE_SIGNIFIKANZ_BEI_KLEINEM_N", HONESTY_LIMITS)
        self.assertIn("PROJEKTINTERN != ALLGEMEIN", HONESTY_LIMITS)


class MeasuredValuesTest(unittest.TestCase):
    """Rechenpruefung der veröffentlichten Momentaufnahme (25.11.2026)."""

    @classmethod
    def setUpClass(cls):
        cls.report = evaluate(DATA)

    def test_state_evaluated(self):
        self.assertEqual("EVALUATED", self.report["state"])

    def test_follow_pairs_and_targets(self):
        self.assertEqual(43, self.report["follow_pairs"])
        self.assertEqual(8, self.report["pairs_target_red"])
        self.assertEqual(22, self.report["pairs_prev_red"])

    def test_all_red_targets_followed_a_red_suite(self):
        # 8/8 ROT-Folgesuiten kamen nach ROT (Kaskaden-Clumping),
        # FN=0 beim Kaskaden-Detektor.
        cm = self.report["detectors"]["detector_kaskade_prev_rot"]["confusion"]
        self.assertEqual({"tp": 8, "fp": 14, "fn": 0, "tn": 21}, cm)

    def test_healing_ratio_after_red(self):
        # 14 von 22 Nachlaeufen nach ROT wurden gruen: Kaskaden
        # muenden ueberwiegend in Heilung, nicht in Aufschaukelung.
        self.assertEqual(14, self.report["healed_after_prev_red"])
        self.assertAlmostEqual(0.6363636363636364,
                               self.report["healing_ratio_after_red"], places=12)

    def test_detector_kaskade_macro_f1(self):
        det = self.report["detectors"]["detector_kaskade_prev_rot"]
        self.assertAlmostEqual(0.36363636363636365, det["precision_red"], places=12)
        self.assertAlmostEqual(1.0, det["recall_red"], places=12)
        self.assertAlmostEqual(0.5333333333333333, det["f1_red"], places=12)
        self.assertAlmostEqual(0.7499999999999999, det["f1_green"], places=12)
        self.assertAlmostEqual(0.6416666666666666, det["macro_f1"], places=12)

    def test_detector_zeit_macro_f1(self):
        det = self.report["detectors"]["detector_zeit"]
        self.assertAlmostEqual(0.1877777777777778, det["macro_f1"], places=12)

    def test_zeit_rule_is_worse_than_cascade_rule(self):
        # Gemessener Befund: Zeitaehe ALLEIN ist ein schwacher
        # Diskriminator (Macro-F1 0.188 gegen 0.642); die Kaskaden-
        # Regel (Vorher-ROT) ist die traegerische Struktur.
        a = self.report["detectors"]["detector_zeit"]["macro_f1"]
        b = self.report["detectors"]["detector_kaskade_prev_rot"]["macro_f1"]
        self.assertLess(a, b)


class FailClosedTest(unittest.TestCase):
    def test_missing_file_not_evaluated(self):
        report = evaluate(pathlib.Path(tempfile.gettempdir()) / "gibtsnicht-4711.jsonl")
        self.assertEqual("NOT_EVALUATED", report["state"])

    def test_malformed_lines_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "bad.jsonl"
            p.write_text('{"branch": "b"}\nnot json\n\n', encoding="utf-8")
            report = evaluate(p)
            self.assertEqual("NOT_EVALUATED", report["state"])  # keine gueltige Suite

    def test_confusion_math_synthetic(self):
        pairs = [
            {"cur_red": True, "prev_red": True, "gap_min": 1.0},
            {"cur_red": False, "prev_red": True, "gap_min": 2.0},
            {"cur_red": True, "prev_red": False, "gap_min": 5.0},
            {"cur_red": False, "prev_red": False, "gap_min": 99.0},
        ]
        by_prev = confusion(pairs, lambda p: p["prev_red"])
        self.assertEqual({"tp": 1, "fp": 1, "fn": 1, "tn": 1}, by_prev)
        sc = class_scores(by_prev)
        self.assertAlmostEqual(0.5, sc["precision_red"], places=12)
        self.assertAlmostEqual(0.5, sc["recall_red"], places=12)
        self.assertAlmostEqual(0.5, sc["f1_red"], places=12)
        self.assertAlmostEqual(0.5, sc["f1_green"], places=12)
        self.assertAlmostEqual(0.5, sc["macro_f1"], places=12)

    def test_follow_pairs_needs_same_branch(self):
        suites = [
            {"branch": "a", "sha": "s1", "t": "2026-11-23T10:00:00Z", "red": True},
            {"branch": "a", "sha": "s2", "t": "2026-11-23T10:30:00Z", "red": False},
            {"branch": "b", "sha": "s3", "t": "2026-11-23T10:15:00Z", "red": True},
        ]
        pairs = follow_pairs(suites)
        self.assertEqual(1, len(pairs))
        self.assertEqual(30.0, pairs[0]["gap_min"])

    def test_cli_exit_2_on_missing_data(self):
        result = subprocess.run(
            [sys.executable, "-m", "controller.cascade_history_eval", "gibtsnicht.jsonl"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("NOT_EVALUATED", result.stdout)


if __name__ == "__main__":
    unittest.main()
