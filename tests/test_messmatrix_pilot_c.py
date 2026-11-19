"""Integrationstest: Pilot-C-Messmatrix-Dataset (Ebola-Praevention, R2).

Das Dataset ist eine Konzeptbeschreibung (MATRIZ != WIRKUNG): Es definiert
Messkriterien, es enthaelt keine Messwerte. UNKNOWN bleibt UNKNOWN.
"""
import json
import unittest
from pathlib import Path

from v91_impact_metrics.metrics import evaluate_messmatrix

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "docs" / "messmatrix" / "pilot-c-ebola-praevention-2026.json"


def _load_record():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


class PilotCMessmatrixTests(unittest.TestCase):
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
        self.assertEqual(result["watcher"], "gesundheit")
        self.assertEqual(result["maturity"], "R2")

    def test_no_multiplier_fiction(self):
        record = _load_record()
        self.assertIsNone(record.get("multiplier"))
        result = evaluate_messmatrix(record)
        self.assertIsNone(result["multiplier"])
        self.assertEqual(result["multiplier_status"], "UNKNOWN")

    def test_impact_claim_never_permitted(self):
        result = evaluate_messmatrix(_load_record())
        self.assertFalse(result["impact_claim_permitted"])

    def test_wirkung_has_alternative_comparison_and_target_period(self):
        record = _load_record()
        wirkung = [i for i in record["indicators"] if i["role"] == "WIRKUNG"][0]
        self.assertTrue(str(wirkung.get("alternative_comparison", "")).strip())
        period = wirkung["period"]
        self.assertLessEqual(period["baseline_at"], period["target_at"])
        self.assertGreater(wirkung["target"], wirkung["baseline"])
        self.assertGreater(wirkung["uncertainty"], 0.0)
        self.assertIn("Ziel-Vorgabe ist nicht selbstgesetzt", wirkung["method"])

    def test_sources_all_https_with_publisher(self):
        record = _load_record()
        sources = record.get("sources", [])
        self.assertGreaterEqual(len(sources), 1)
        for source in sources:
            self.assertTrue(str(source.get("url", "")).startswith("https://"))
            self.assertTrue(str(source.get("publisher", "")).strip())

    def test_no_measured_values_in_raw_dataset(self):
        raw = DATASET_PATH.read_text(encoding="utf-8")
        self.assertNotIn('"measured"', raw)
        self.assertNotIn('"measured_at"', raw)
        self.assertNotIn('"measurements"', raw)

    def test_resilienz_is_self_imposed_and_documented(self):
        record = _load_record()
        resilienz = [i for i in record["indicators"]
                     if i["role"] == "RESILIENZ"][0]
        self.assertIn("Selbstgesetzter Messpunkt des Pilotkonzepts",
                      resilienz["method"])

    def test_unverified_source_framed_as_such(self):
        record = _load_record()
        kosten = [i for i in record["indicators"] if i["role"] == "KOSTEN"][0]
        self.assertIn("NICHT vollstaendig geprueft", kosten["method"])


if __name__ == "__main__":
    unittest.main()
