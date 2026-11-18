"""Tests for the resilience monitors (feed, aquaculture, hygiene)."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.resilience_monitors import (  # noqa: E402
    evaluate_aquaculture_quality, evaluate_hygiene_separation,
    evaluate_winter_feed_balance,
)


class WinterFeedBalanceTest(unittest.TestCase):
    def test_sufficient(self):
        result = evaluate_winter_feed_balance(grain_kg=250.0, hay_kg=100.0,
                                              animal_count=10, winter_weeks=20)
        self.assertTrue(result.sufficient)
        self.assertEqual(result.required_total_kg, 300.0)
        self.assertIn("OK", result.status_message)

    def test_insufficient(self):
        result = evaluate_winter_feed_balance(grain_kg=150.0, hay_kg=50.0,
                                              animal_count=10, winter_weeks=20)
        self.assertFalse(result.sufficient)
        self.assertIn("KRITISCH", result.status_message)

    def test_invalid_inputs_refused_fail_closed(self):
        for kwargs in (
            {"grain_kg": float("nan"), "hay_kg": 1.0, "animal_count": 1},
            {"grain_kg": float("inf"), "hay_kg": 1.0, "animal_count": 1},
            {"grain_kg": -1.0, "hay_kg": 1.0, "animal_count": 1},
            {"grain_kg": 1.0, "hay_kg": 1.0, "animal_count": -1},
            {"grain_kg": 1.0, "hay_kg": 1.0, "animal_count": True},
            {"grain_kg": 1.0, "hay_kg": 1.0, "animal_count": 1, "winter_weeks": 0},
        ):
            with self.assertRaises(ValueError, msg=str(kwargs)):
                evaluate_winter_feed_balance(**kwargs)


class AquacultureQualityTest(unittest.TestCase):
    def test_optimal(self):
        result = evaluate_aquaculture_quality(o2_mg_l=6.5, nitrit_mg_l=0.1)
        self.assertTrue(result.o2_safe and result.nitrite_safe)
        self.assertIn("OK", result.status_message)

    def test_low_oxygen(self):
        result = evaluate_aquaculture_quality(o2_mg_l=4.0, nitrit_mg_l=0.05)
        self.assertFalse(result.o2_safe)
        self.assertIn("WARNUNG", result.status_message)

    def test_high_nitrite(self):
        result = evaluate_aquaculture_quality(o2_mg_l=6.0, nitrit_mg_l=0.3)
        self.assertFalse(result.nitrite_safe)
        self.assertIn("WARNUNG", result.status_message)

    def test_non_finite_refused(self):
        with self.assertRaises(ValueError):
            evaluate_aquaculture_quality(o2_mg_l=math.inf, nitrit_mg_l=0.1)
        with self.assertRaises(ValueError):
            evaluate_aquaculture_quality(o2_mg_l=6.0, nitrit_mg_l=float("nan"))


class HygieneSeparationTest(unittest.TestCase):
    def test_both_verified_is_ok(self):
        result = evaluate_hygiene_separation(physical_air_gap=True,
                                             backflow_preventer_active=True)
        self.assertTrue(result.segregated)
        self.assertIn("OK", result.status_message)

    def test_unverified_is_risk_fail_closed(self):
        for air_gap, backflow in ((False, True), (True, False), (False, False)):
            result = evaluate_hygiene_separation(physical_air_gap=air_gap,
                                                 backflow_preventer_active=backflow)
            self.assertFalse(result.segregated)
            self.assertTrue(result.cross_contamination_risk)
            self.assertIn("KRITISCH", result.status_message)


if __name__ == "__main__":
    unittest.main()
