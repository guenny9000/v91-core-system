"""Tests for seed inventory and seasonal reserve evaluation."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.seed_inventory import (  # noqa: E402
    DEFAULT_RESERVE_DAYS, MIN_GERMINATION_PCT, SeedInventoryError,
    evaluate_seasonal_reserves, evaluate_seed_batch,
)


class SeedBatchTest(unittest.TestCase):
    def test_viable_samenfest_batch(self):
        s = evaluate_seed_batch(batch_id="B-2026-01", crop_name="Tomate",
                                open_pollinated=True, germination_rate_pct=86.0)
        self.assertTrue(s.viable)
        self.assertIn("OK", s.status_message)

    def test_hybrid_rejected(self):
        s = evaluate_seed_batch(batch_id="B-2026-02", crop_name="Paprika",
                                open_pollinated=False, germination_rate_pct=95.0)
        self.assertFalse(s.viable)
        self.assertIn("ABGELEHNT", s.status_message)

    def test_low_germination_warns(self):
        s = evaluate_seed_batch(batch_id="B-2026-03", crop_name="Bohne",
                                open_pollinated=True, germination_rate_pct=60.0)
        self.assertFalse(s.viable)
        self.assertIn("WARNUNG", s.status_message)

    def test_boundary_exactly_at_minimum(self):
        s = evaluate_seed_batch(batch_id="B-2026-04", crop_name="Erbsen",
                                open_pollinated=True,
                                germination_rate_pct=MIN_GERMINATION_PCT)
        self.assertTrue(s.viable)

    def test_fail_closed_inputs(self):
        for kwargs in (
            {"batch_id": "", "crop_name": "x", "open_pollinated": True, "germination_rate_pct": 80.0},
            {"batch_id": "b", "crop_name": "x", "open_pollinated": "yes", "germination_rate_pct": 80.0},
            {"batch_id": "b", "crop_name": "x", "open_pollinated": True, "germination_rate_pct": float("nan")},
            {"batch_id": "b", "crop_name": "x", "open_pollinated": True, "germination_rate_pct": -1.0},
            {"batch_id": "b", "crop_name": "x", "open_pollinated": True, "germination_rate_pct": 101.0},
            {"batch_id": "b", "crop_name": "x", "open_pollinated": True, "germination_rate_pct": True},
        ):
            with self.assertRaises(SeedInventoryError, msg=str(kwargs)):
                evaluate_seed_batch(**kwargs)


class SeasonalReserveTest(unittest.TestCase):
    def test_secure_at_default_target(self):
        s = evaluate_seasonal_reserves(reserve_days=200)
        self.assertTrue(s.secure)
        self.assertEqual(s.minimum_required_days, DEFAULT_RESERVE_DAYS)

    def test_insufficient_flags_critical(self):
        s = evaluate_seasonal_reserves(reserve_days=90, required_days=180,
                                       category="Getreide")
        self.assertFalse(s.secure)
        self.assertIn("KRITISCH", s.status_message)

    def test_boundary_exactly_at_target(self):
        s = evaluate_seasonal_reserves(reserve_days=180, required_days=180)
        self.assertTrue(s.secure)

    def test_fail_closed_inputs(self):
        for kwargs in (
            {"reserve_days": -1},
            {"reserve_days": True},
            {"reserve_days": 10, "required_days": 0},
            {"reserve_days": 10, "required_days": 4000},
            {"reserve_days": 10, "category": ""},
        ):
            with self.assertRaises(SeedInventoryError, msg=str(kwargs)):
                evaluate_seasonal_reserves(**kwargs)


if __name__ == "__main__":
    unittest.main()
