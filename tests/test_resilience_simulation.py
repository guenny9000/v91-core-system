"""Tests for the deterministic resilience scenario engine."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.resilience_simulation import (  # noqa: E402
    EnergyState, NutrientVector, SimulationInputError, SocialCapacity,
    SparePartInventory, simulate_weeks,
)


def base_inputs():
    nutrients = NutrientVector(grain_kg=100.0, hay_kg=200.0, protein_feed_kg=50.0,
                               animals=10)
    energy = EnergyState(electricity_kwh=500.0, heat_kwh=800.0, water_m3=60.0,
                        weekly_draw_electricity_kwh=20.0, weekly_draw_heat_kwh=40.0,
                        weekly_draw_water_m3=2.0)
    spares = SparePartInventory(spare_parts=12, operating_machines=1,
                                tools_available=True, repair_knowledge_available=True)
    social = SocialCapacity(work_hours_per_week=50.0, care_hours_per_week=30.0,
                            weekly_work_needed=40.0, weekly_care_needed=10.0,
                            weekly_rest_recovery_hours=40.0)
    return nutrients, energy, spares, social


class DeterminismTest(unittest.TestCase):
    def test_identical_inputs_identical_outputs(self):
        a = simulate_weeks(*base_inputs(), weeks=52)
        b = simulate_weeks(*base_inputs(), weeks=52)
        self.assertEqual(a, b)

    def test_long_run_tracks_deterministic_depletion(self):
        reports = simulate_weeks(*base_inputs(), weeks=52)
        self.assertEqual(len(reports), 52)
        # Deterministic depletion points of the base scenario:
        # 12 spare parts at 1/week -> first deficit in week 13.
        self.assertTrue(all(r.ok for r in reports[:12]))
        self.assertIn("spare_parts", reports[12].deficits)
        # Grain: 100 kg at 2.5 kg/week -> first grain deficit in week 41.
        self.assertNotIn("grain", reports[39].deficits)
        self.assertIn("grain", reports[40].deficits)
        # Stocks floor at zero, never negative, and stay deterministic.
        self.assertEqual(reports[-1].state["spare_parts"], 0)
        self.assertEqual(reports[-1].state["grain_kg"], 0.0)


class DeficitPathTest(unittest.TestCase):
    def test_feed_depletion_flags_deficit_in_order(self):
        _, energy, spares, social = base_inputs()
        # 10 animals x 0.25 kg grain/week = 2.5 kg/week; 10 kg last 4 weeks.
        depleted = NutrientVector(grain_kg=10.0, hay_kg=200.0, protein_feed_kg=50.0,
                                  animals=10)
        reports = simulate_weeks(depleted, energy, spares, social, weeks=52)
        first_bad = next(r for r in reports if not r.ok)
        self.assertEqual(first_bad.week, 5)
        self.assertIn("grain", first_bad.deficits)

    def test_spare_part_exhaustion_flagged(self):
        nutrients, energy, spares, social = base_inputs()
        low_spares = SparePartInventory(spare_parts=3, operating_machines=1,
                                        tools_available=True,
                                        repair_knowledge_available=True)
        reports = simulate_weeks(nutrients, energy, low_spares, social, weeks=10)
        bad = [r for r in reports if "spare_parts" in r.deficits]
        self.assertEqual(len(bad), 7)  # weeks 4..10

    def test_missing_repair_prerequisites_flagged_immediately(self):
        nutrients, energy, spares, social = base_inputs()
        no_tools = SparePartInventory(spare_parts=50, operating_machines=1,
                                      tools_available=False,
                                      repair_knowledge_available=True)
        reports = simulate_weeks(nutrients, energy, no_tools, social, weeks=2)
        self.assertIn("repair_prerequisites_missing", reports[0].deficits)

    def test_energy_shortfall_flagged_per_stock(self):
        nutrients, energy, spares, social = base_inputs()
        dry = EnergyState(electricity_kwh=10.0, heat_kwh=800.0, water_m3=1.0,
                          weekly_draw_electricity_kwh=20.0, weekly_draw_heat_kwh=40.0,
                          weekly_draw_water_m3=2.0)
        reports = simulate_weeks(nutrients, dry, spares, social, weeks=1)
        self.assertIn("electricity", reports[0].deficits)
        self.assertIn("water", reports[0].deficits)
        self.assertNotIn("heat", reports[0].deficits)

    def test_social_capacity_burn_and_recovery(self):
        nutrients, energy, spares, social = base_inputs()
        overworked = SocialCapacity(work_hours_per_week=10.0, care_hours_per_week=30.0,
                                    weekly_work_needed=40.0, weekly_care_needed=10.0,
                                    weekly_rest_recovery_hours=0.0)
        reports = simulate_weeks(nutrients, energy, spares, overworked, weeks=1)
        self.assertIn("work_hours", reports[0].deficits)


class FailClosedTest(unittest.TestCase):
    def test_invalid_inputs_refused(self):
        nutrients, energy, spares, social = base_inputs()
        bad_nutrients = NutrientVector(grain_kg=float("nan"), hay_kg=1.0,
                                       protein_feed_kg=1.0, animals=2)
        with self.assertRaises(SimulationInputError):
            simulate_weeks(bad_nutrients, energy, spares, social, weeks=1)
        with self.assertRaises(SimulationInputError):
            simulate_weeks(nutrients, energy, spares, social, weeks=0)
        with self.assertRaises(SimulationInputError):
            simulate_weeks(nutrients, energy, spares, social, weeks=521)
        with self.assertRaises(SimulationInputError):
            simulate_weeks(nutrients, energy, spares, social, weeks=True)

    def test_bool_rejected_for_numeric_fields(self):
        nutrients, energy, spares, social = base_inputs()
        bool_energy = EnergyState(electricity_kwh=True, heat_kwh=1.0, water_m3=1.0,
                                  weekly_draw_electricity_kwh=0.0,
                                  weekly_draw_heat_kwh=0.0, weekly_draw_water_m3=0.0)
        with self.assertRaises(SimulationInputError):
            simulate_weeks(nutrients, bool_energy, spares, social, weeks=1)


if __name__ == "__main__":
    unittest.main()
