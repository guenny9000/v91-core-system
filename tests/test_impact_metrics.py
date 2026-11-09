import unittest

from v91_impact_metrics.metrics import evaluate_dataset, evaluate_measurement


def measurement(**overrides):
    value = {
        "metric_id": "peatland-001",
        "domain": "peatland",
        "indicator": "Area under verified restoration",
        "unit": "hectares",
        "location": "Named restoration site",
        "baseline": 100.0,
        "measured": 120.0,
        "baseline_at": "2026-01-01T00:00:00Z",
        "measured_at": "2026-11-09T00:00:00Z",
        "direction": "higher_is_better",
        "implementation_status": "COMPLETED",
        "sources": [],
    }
    value.update(overrides)
    return value


class ImpactMetricsTests(unittest.TestCase):
    def test_computes_measured_improvement(self):
        result = evaluate_measurement(measurement())
        self.assertEqual(result["outcome"], "IMPROVED")
        self.assertEqual(result["improvement_percent"], 20.0)
        self.assertFalse(result["global_impact_claim_permitted"])

    def test_lower_is_better(self):
        result = evaluate_measurement(measurement(
            domain="water", indicator="Water consumption", unit="m3",
            baseline=100, measured=75, direction="lower_is_better"
        ))
        self.assertEqual(result["improvement_percent"], 25.0)

    def test_zero_baseline_is_unknown_percent_not_division_error(self):
        result = evaluate_measurement(measurement(baseline=0, measured=4))
        self.assertIsNone(result["improvement_percent"])
        self.assertEqual(result["outcome"], "UNKNOWN")

    def test_empty_dataset_is_unknown_not_zero_impact(self):
        result = evaluate_dataset({"measurements": []})
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["global_impact_status"], "UNKNOWN")
        self.assertIsNone(result["global_impact_total"])

    def test_caller_flag_alone_cannot_create_verified_evidence(self):
        result = evaluate_measurement(measurement(independently_verified=True))
        self.assertEqual(result["evidence_status"], "UNKNOWN")

    def test_caller_cannot_self_attest_independent_verification(self):
        sources = [
            {"publisher": "Primary registry", "url": "https://example.org/a"},
            {"publisher": "Independent auditor", "url": "https://example.net/b"},
        ]
        result = evaluate_measurement(measurement(
            sources=sources, independently_verified=True,
            verification_method="independent_site_inspection"
        ))
        self.assertEqual(result["evidence_status"], "CORROBORATED")
        self.assertTrue(result["verification_claim_received"])

    def test_invalid_timestamp_and_non_finite_values_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_measurement(measurement(measured_at="yesterday"))
        with self.assertRaises(ValueError):
            evaluate_measurement(measurement(measured=float("nan")))

    def test_http_source_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_measurement(measurement(
                sources=[{"publisher": "Registry", "url": "http://example.org"}]
            ))


if __name__ == "__main__":
    unittest.main()
