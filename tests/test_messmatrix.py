"""Tests fuer die Messmatrix v1.0 (Global Impact Engine Modul-Schritt 3)."""
import unittest

from v91_impact_metrics.metrics import evaluate_messmatrix


def _indicator(role="WIRKUNG", **overrides):
    value = {
        "role": role,
        "name": "Zurueckgehaltenes Wasser",
        "unit": "m3",
        "baseline": 1000.0,
        "target": 1500.0,
        "period": {"baseline_at": "2026-01-01T00:00:00Z",
                   "target_at": "2027-01-01T00:00:00Z"},
        "method": "Wasserstandsmessung an definierten Pegeln",
        "verifier": "Wasserwerk der Kommune",
        "uncertainty": 50.0,
        "alternative_comparison": "Deque-Ausbau am Unterlauf (Kosten je m3 hoeher)",
    }
    value.update(overrides)
    return value


def _matrix(**overrides):
    value = {
        "initiative_id": "pilot-a-moor-wasser",
        "description": "Moorrenaturierung mit Wasserstandssensorik und Paludikultur",
        "watcher": "wasser",
        "maturity": "R2",
        "indicators": [
            _indicator("WIRKUNG"),
            _indicator("KOSTEN", name="Kosten", unit="EUR",
                       target=200000.0, alternative_comparison=None),
            _indicator("RESILIENZ", name="Inselfaehigkeit Wasser",
                       unit="Stunden", target=72.0,
                       alternative_comparison=None),
        ],
    }
    value.update(overrides)
    return value


class MessmatrixTests(unittest.TestCase):
    def test_valid_matrix_described(self):
        result = evaluate_messmatrix(_matrix())
        self.assertEqual(result["matrix_status"], "MASSE_BESCHRIEBEN")
        self.assertEqual(sorted(result["roles_covered"]),
                         ["KOSTEN", "RESILIENZ", "WIRKUNG"])
        self.assertFalse(result["impact_claim_permitted"])

    def test_all_seven_watchers_accepted(self):
        for watcher in ("wasser", "energie", "ernaehrung", "gesundheit",
                        "natur", "frieden", "technologie"):
            result = evaluate_messmatrix(_matrix(watcher=watcher))
            self.assertEqual(result["watcher"], watcher)

    def test_unknown_watcher_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_messmatrix(_matrix(watcher="raumfahrt"))

    def test_maturity_r0_to_r6_accepted_above_rejected(self):
        for maturity in ("R0", "R3", "R6"):
            self.assertEqual(
                evaluate_messmatrix(_matrix(maturity=maturity))["maturity"],
                maturity)
        with self.assertRaises(ValueError):
            evaluate_messmatrix(_matrix(maturity="R7"))

    def test_missing_role_fail_closed(self):
        matrix = _matrix()
        del matrix["indicators"][2]
        with self.assertRaisesRegex(ValueError, "RESILIENZ"):
            evaluate_messmatrix(matrix)

    def test_wirkung_requires_alternative_comparison(self):
        with self.assertRaisesRegex(ValueError, "alternative_comparison"):
            evaluate_messmatrix(_matrix(indicators=[
                _indicator("WIRKUNG", alternative_comparison=None),
                _indicator("KOSTEN"), _indicator("RESILIENZ"),
            ]))

    def test_missing_method_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "method"):
            evaluate_messmatrix(_matrix(indicators=[
                _indicator("WIRKUNG", method=""),
                _indicator("KOSTEN"), _indicator("RESILIENZ"),
            ]))

    def test_missing_verifier_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "verifier"):
            evaluate_messmatrix(_matrix(indicators=[
                _indicator("WIRKUNG", verifier=" "),
                _indicator("KOSTEN"), _indicator("RESILIENZ"),
            ]))

    def test_negative_target_and_uncertainty_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            evaluate_messmatrix(_matrix(indicators=[
                _indicator("WIRKUNG", target=-1.0),
                _indicator("KOSTEN"), _indicator("RESILIENZ"),
            ]))
        with self.assertRaisesRegex(ValueError, "uncertainty"):
            evaluate_messmatrix(_matrix(indicators=[
                _indicator("WIRKUNG", uncertainty=-0.5),
                _indicator("KOSTEN"), _indicator("RESILIENZ"),
            ]))

    def test_period_order_enforced(self):
        with self.assertRaisesRegex(ValueError, "period.target_at"):
            evaluate_messmatrix(_matrix(indicators=[
                _indicator("WIRKUNG", period={
                    "baseline_at": "2026-01-01T00:00:00Z",
                    "target_at": "2025-01-01T00:00:00Z"}),
                _indicator("KOSTEN"), _indicator("RESILIENZ"),
            ]))

    def test_multiplier_computed_and_optional(self):
        result = evaluate_messmatrix(_matrix(multiplier={
            "added_benefit": 10.0, "added_effort": 2.0}))
        self.assertEqual(result["multiplier"], 5.0)
        self.assertEqual(result["multiplier_status"], "MODELED")
        without = evaluate_messmatrix(_matrix())
        self.assertIsNone(without["multiplier"])
        self.assertEqual(without["multiplier_status"], "UNKNOWN")

    def test_multiplier_fail_closed_on_bad_values(self):
        for bad in ({"added_benefit": -1.0, "added_effort": 2.0},
                    {"added_benefit": 1.0, "added_effort": 0.0}):
            with self.assertRaises(ValueError):
                evaluate_messmatrix(_matrix(multiplier=bad))

    def test_impact_claim_never_permitted_and_limits_present(self):
        result = evaluate_messmatrix(_matrix())
        self.assertFalse(result["impact_claim_permitted"])
        self.assertTrue(any("MATRIZ != WIRKUNG" in item
                             for item in result["limitations"]))


if __name__ == "__main__":
    unittest.main()
