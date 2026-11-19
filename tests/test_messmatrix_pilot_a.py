"""Integration tests for the Pilot A messmatrix dataset (moor + water, R2).

The dataset is a claim record, never evidence of impact: the tests pin the
honest state (maturity R2, UNKNOWN multiplier, no measured keys) so that a
later accidental upgrade from MA prose to measured results fails loudly.
"""

import json
import unittest
from pathlib import Path

from v91_impact_metrics.metrics import evaluate_messmatrix

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = REPO_ROOT / "docs" / "messmatrix" / "pilot-a-moor-wasser-2026.json"


def _load_record() -> dict:
    with DATASET_PATH.open(encoding="ascii") as handle:
        return json.load(handle)


class PilotAMessmatrixDatasetTests(unittest.TestCase):
    def test_dataset_exists_and_is_ascii_pure(self) -> None:
        raw = DATASET_PATH.read_bytes()
        raw.decode("ascii")  # raises if any non-ASCII byte survived an edit
        record = _load_record()
        self.assertEqual(record["initiative_id"], "pilot-a-moor-wasser-2026")

    def test_dataset_passes_evaluate_messmatrix(self) -> None:
        result = evaluate_messmatrix(_load_record())
        self.assertEqual(result["matrix_status"], "MASSE_BESCHRIEBEN")
        self.assertEqual(result["indicator_count"], 3)
        self.assertFalse(result["impact_claim_permitted"])

    def test_roles_covered_and_watcher_domain(self) -> None:
        result = evaluate_messmatrix(_load_record())
        self.assertEqual(result["roles_covered"], ["KOSTEN", "RESILIENZ", "WIRKUNG"])
        self.assertEqual(result["watcher"], "wasser")

    def test_maturity_is_r2_concept_stage(self) -> None:
        self.assertEqual(_load_record()["maturity"], "R2")

    def test_multiplier_stays_unknown(self) -> None:
        result = evaluate_messmatrix(_load_record())
        self.assertIsNone(result["multiplier"])
        self.assertEqual(result["multiplier_status"], "UNKNOWN")

    def test_wirkung_indicator_has_alternative_comparison(self) -> None:
        record = _load_record()
        wirkung = [i for i in record["indicators"] if i["role"] == "WIRKUNG"]
        self.assertEqual(len(wirkung), 1)
        self.assertTrue(wirkung[0]["alternative_comparison"].strip())

    def test_sources_are_https_with_publisher(self) -> None:
        record = _load_record()
        all_sources = list(record.get("sources", []))
        for indicator in record["indicators"]:
            all_sources.extend(indicator.get("sources", []))
        self.assertTrue(all_sources)
        for source in all_sources:
            self.assertTrue(source["url"].startswith("https://"))
            self.assertTrue(source["publisher"].strip())

    def test_raw_file_contains_no_measurement_claims(self) -> None:
        raw = DATASET_PATH.read_text(encoding="ascii")
        self.assertNotIn('"measured"', raw)
        self.assertNotIn("measured_at", raw)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
