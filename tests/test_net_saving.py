"""Net-saving accounting tests (protocol section 5).

Every test pins the fail-closed rules: unknown terms, missing currency
or horizon, imputed zeros and silent verification are all rejected.
"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.net_saving import NetSavingError, compute_net_saving


GOOD = {
    "gross_monetary_benefit": 100000.0,
    "implementation_cost": 40000.0,
    "operating_cost_delta": -0.0,
    "currency": "EUR",
    "horizon": "2026-11-01/2027-10-31 (12 months)",
}


class ComputeNetSavingTest(unittest.TestCase):
    def test_positive_net(self):
        result = compute_net_saving(GOOD)
        self.assertEqual(result["candidate_status"], "NET_POSITIVE_CANDIDATE")
        self.assertAlmostEqual(result["net_saving"], 60000.0, places=6)

    def test_negative_net(self):
        terms = dict(GOOD, gross_monetary_benefit=10000.0)
        result = compute_net_saving(terms)
        self.assertEqual(result["candidate_status"], "NET_NEGATIVE_CANDIDATE")
        self.assertAlmostEqual(result["net_saving"], -30000.0, places=6)

    def test_zero_net(self):
        terms = dict(GOOD, gross_monetary_benefit=40000.0)
        result = compute_net_saving(terms)
        self.assertEqual(result["candidate_status"], "NET_ZERO_CANDIDATE")

    def test_missing_currency_rejected(self):
        with self.assertRaises(NetSavingError):
            compute_net_saving({k: v for k, v in GOOD.items()
                               if k != "currency"})

    def test_missing_horizon_rejected(self):
        with self.assertRaises(NetSavingError):
            compute_net_saving({k: v for k, v in GOOD.items()
                               if k != "horizon"})

    def test_missing_gross_rejected(self):
        with self.assertRaises(NetSavingError):
            compute_net_saving({k: v for k, v in GOOD.items()
                               if k != "gross_monetary_benefit"})

    def test_unknown_cost_term_rejected(self):
        with self.assertRaises(NetSavingError):
            compute_net_saving(dict(GOOD, implementaton_cost=1.0))

    def test_negative_cost_rejected(self):
        with self.assertRaises(NetSavingError):
            compute_net_saving(dict(GOOD, migration_cost=-5.0))

    def test_non_finite_cost_rejected(self):
        with self.assertRaises(NetSavingError):
            compute_net_saving(dict(GOOD, disposal_cost=float("inf")))

    def test_bool_rejected(self):
        with self.assertRaises(NetSavingError):
            compute_net_saving(dict(GOOD, training_cost=True))

    def test_all_costs_non_negative_pass(self):
        terms = dict(GOOD)
        terms.pop("operating_cost_delta")
        terms["maintenance_cost_delta"] = 0.0
        result = compute_net_saving(terms)
        self.assertAlmostEqual(
            result["total_lifecycle_costs"], 40000.0, places=6)

    def test_fsum_precision(self):
        terms = dict(GOOD)
        terms.pop("operating_cost_delta")
        terms.pop("implementation_cost")
        terms["other_material_cost"] = 0.1
        terms["migration_cost"] = 0.2
        result = compute_net_saving(terms)
        self.assertAlmostEqual(
            result["total_lifecycle_costs"], 0.3, places=10)
        self.assertAlmostEqual(
            result["net_saving"], 100000.0 - 0.3, places=6)

    def test_candidate_never_independently_verified(self):
        result = compute_net_saving(GOOD)
        self.assertEqual(result["review_status"],
                         "NOT_INDEPENDENTLY_VERIFIED")
        self.assertEqual(result["attribution"], "CALCULATED_ONLY")

    def test_deterministic(self):
        first = compute_net_saving(GOOD)
        second = compute_net_saving(GOOD)
        self.assertEqual(first, second)

    def test_non_dict_rejected(self):
        with self.assertRaises(NetSavingError):
            compute_net_saving([GOOD])


if __name__ == "__main__":
    unittest.main()
