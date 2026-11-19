"""Integrationstest: Pilot-D-Messmatrix-Dataset (Kita-/Schulverpflegung, R2).

Das Dataset ist eine Konzeptbeschreibung (MATRIZ != WIRKUNG): Es definiert
Messkriterien, es enthaelt keine Messwerte. UNKNOWN bleibt UNKNOWN.
"""
import json
import unittest
from pathlib import Path

from v91_impact_metrics.metrics import evaluate_messmatrix

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "docs" / "messmatrix" / "pilot-d-kita-schulverpflegung-2026.json"


def _load_record():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


class PilotDMessmatrixTests(unittest.TestCase):
    def test_dataset_exists_and_is_ascii_pure(self):
        raw = DATASET_PATH.read_text(encoding="utf-8")
        self.assertTrue(DATASET_PATH.is_file())
        for char in raw:
            self.assertTrue(ord(char) < 128,
                            f"non-ASCII character {char!r} in dataset")

    def test_evaluate_is_green(self):
        result = evaluate_messmatrix(_load_record())
        self.assertEqual(result["matrix_status"], "MASSE_BESCHRIEBEN")
        self.assertEqual(sorted(result["roles_covered"]),
                         ["KOSTEN", "RESILIENZ", "WIRKUNG"])

    def test_watcher_and_maturity(self):
        result = evaluate_messmatrix(_load_record())
        self.assertEqual(result["watcher"], "ernaehrung")
        self.assertEqual(result["maturity"], "R2")

    def test_no_measured_values(self):
        raw = DATASET_PATH.read_text(encoding="utf-8")
        self.assertNotIn("measured", raw)
        record = _load_record()
        for ind in record["indicators"]:
            self.assertNotIn("measured", ind)
            self.assertGreater(ind["target"], ind["baseline"])

    def test_no_multiplier_fiction(self):
        record = _load_record()
        self.assertIsNone(record.get("multiplier"))
        result = evaluate_messmatrix(record)
        self.assertIsNone(result["multiplier"])
        self.assertEqual(result["multiplier_status"], "UNKNOWN")

    def test_impact_claim_never_permitted(self):
        result = evaluate_messmatrix(_load_record())
        self.assertFalse(result["impact_claim_permitted"])

    def test_wirkung_has_alternative_comparison_and_known_baseline(self):
        record = _load_record()
        wirkung = [i for i in record["indicators"] if i["role"] == "WIRKUNG"][0]
        self.assertEqual(wirkung["baseline"], 6000000.0)
        self.assertEqual(wirkung["target"], 6400000.0)
        self.assertTrue(str(wirkung.get("alternative_comparison", "")).strip())
        period = wirkung["period"]
        self.assertLessEqual(period["baseline_at"], period["target_at"])
        self.assertGreater(wirkung["uncertainty"], 0.0)

    def test_kosten_target_matches_investment_programmes(self):
        record = _load_record()
        kosten = [i for i in record["indicators"] if i["role"] == "KOSTEN"][0]
        self.assertEqual(kosten["target"], 7500000000.0)
        self.assertEqual(kosten["baseline"], 0.0)
        self.assertGreater(kosten["uncertainty"], 0.0)

    def test_resilienz_is_self_set_pilot_duty(self):
        record = _load_record()
        resilienz = [i for i in record["indicators"] if i["role"] == "RESILIENZ"][0]
        self.assertEqual(resilienz["target"], 6.0)
        self.assertEqual(resilienz["uncertainty"], 0.0)
        self.assertIn("Selbstgesetzte", resilienz["method"])

    def test_sources_all_https_with_publisher(self):
        record = _load_record()
        self.assertGreaterEqual(len(record["sources"]), 3)
        for src in record["sources"]:
            self.assertTrue(src["url"].startswith("https://"))
            self.assertTrue(src["publisher"].strip())

    def test_method_and_description_length_limits(self):
        record = _load_record()
        self.assertLess(len(record["description"]), 240)
        for ind in record["indicators"]:
            self.assertLess(len(ind["method"]), 240)
            self.assertLess(len(ind["name"]), 200)


if __name__ == "__main__":
    unittest.main()
