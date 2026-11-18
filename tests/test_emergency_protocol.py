#!/usr/bin/env python3
"""Tests for the emergency protocol decision support (Beschluss 2026-11-01)."""
from __future__ import annotations

import unittest

from controller.emergency_protocol import (
    CrisisMeasure,
    CrisisSituation,
    EmergencyProtocolError,
    evaluate_crisis,
)


def measure(mid: str, harm: int, **over) -> CrisisMeasure:
    base = dict(measure_id=mid, description="candidate", expected_lives_saved=1,
                expected_total_harm=harm, protects_uninvolved=True,
                time_limited=True, reversible=True, scope="minimal")
    base.update(over)
    return CrisisMeasure(**base)


class EmergencyProtocolTest(unittest.TestCase):
    def test_no_life_threat_is_normal_case_no_intervention(self) -> None:
        s = CrisisSituation(situation_id="s1", description="storm damage",
                            human_life_directly_threatened=False, full_prevention_possible=True)
        d = evaluate_crisis(s, [])
        self.assertEqual(d.protocol, "NO_INTERVENTION")
        self.assertFalse(d.requires_human_authorization)
        self.assertIsNone(d.selected_measure_id)

    def test_life_threat_without_measures_requires_human_decision(self) -> None:
        s = CrisisSituation(situation_id="s2", description="flood",
                            human_life_directly_threatened=True, full_prevention_possible=True)
        d = evaluate_crisis(s, [])
        self.assertEqual(d.protocol, "LIFE_PRIORITY_LIMITED_INTERVENTION")
        self.assertTrue(d.requires_human_authorization)
        self.assertIsNone(d.selected_measure_id)

    def test_full_prevention_selects_least_harm_admissible_measure(self) -> None:
        s = CrisisSituation(situation_id="s3", description="fire",
                            human_life_directly_threatened=True, full_prevention_possible=True)
        d = evaluate_crisis(s, [measure("a", 5), measure("b", 2), measure("c", 9)])
        self.assertEqual(d.selected_measure_id, "b")
        self.assertTrue(d.requires_human_authorization)

    def test_no_full_prevention_uses_least_harm_rule(self) -> None:
        s = CrisisSituation(situation_id="s4", description="war-related collapse",
                            human_life_directly_threatened=True, full_prevention_possible=False)
        d = evaluate_crisis(s, [measure("a", 7), measure("b", 3)])
        self.assertEqual(d.protocol, "LEAST_HARM_CHOICE")
        self.assertEqual(d.selected_measure_id, "b")

    def test_measures_violating_protection_rules_are_rejected(self) -> None:
        s = CrisisSituation(situation_id="s5", description="crisis",
                            human_life_directly_threatened=True, full_prevention_possible=False)
        d = evaluate_crisis(s, [
            measure("harmful", 1, protects_uninvolved=False),
            measure("unbounded", 1, time_limited=False),
            measure("irreversible", 1, reversible=False),
            measure("overboard", 1, scope="extended"),
        ])
        self.assertIsNone(d.selected_measure_id)
        self.assertTrue(d.requires_human_authorization)
        self.assertTrue(any("FAIL-CLOSED" in r for r in d.rationale))

    def test_every_intervention_still_requires_human_authorization(self) -> None:
        s = CrisisSituation(situation_id="s6", description="crisis",
                            human_life_directly_threatened=True, full_prevention_possible=True)
        d = evaluate_crisis(s, [measure("good", 1)])
        self.assertTrue(d.requires_human_authorization)
        self.assertIn("Im Ledger protokollieren", d.required_controls)
        self.assertIn("Wiederherstellung nach Gefahrenende einplanen", d.required_controls)

    def test_lives_saved_breaks_ties_on_equal_harm(self) -> None:
        s = CrisisSituation(situation_id="s7", description="crisis",
                            human_life_directly_threatened=True, full_prevention_possible=False)
        d = evaluate_crisis(s, [measure("x", 4, expected_lives_saved=1),
                                measure("y", 4, expected_lives_saved=5)])
        self.assertEqual(d.selected_measure_id, "y")

    def test_fail_closed_on_malformed_input(self) -> None:
        s = CrisisSituation(situation_id="s8", description="crisis",
                            human_life_directly_threatened="yes",  # type: ignore[arg-type]
                            full_prevention_possible=True)
        with self.assertRaises(EmergencyProtocolError):
            evaluate_crisis(s, [])
        s2 = CrisisSituation(situation_id="s9", description="crisis",
                             human_life_directly_threatened=True, full_prevention_possible=True)
        with self.assertRaises(EmergencyProtocolError):
            evaluate_crisis(s2, [measure("neg", -1)])
        with self.assertRaises(EmergencyProtocolError):
            evaluate_crisis("not-a-situation", [])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
