import unittest

from disarmament.reduction_stages import validate_reduction_record


def source(publisher, role="primary_record"):
    return {
        "url": f"https://{publisher.lower().replace(' ', '-')}.example/evidence",
        "publisher": publisher,
        "role": role,
    }


def record(**overrides):
    value = {
        "record_id": "reduction-001",
        "category": "conventional",
        "jurisdiction": "Example jurisdiction",
        "responsible_authority": "Competent public authority",
        "stage": "ANNOUNCED",
        "observed_at": "2026-11-09T07:00:00Z",
        "unit": "items",
        "sources": [source("Public authority")],
    }
    value.update(overrides)
    return value


class ReductionStageTests(unittest.TestCase):
    def test_announcement_is_not_completed_disarmament(self):
        result = validate_reduction_record(record())
        self.assertEqual(result["stage"], "ANNOUNCED")
        self.assertEqual(result["evidence_status"], "DOCUMENTED")
        self.assertFalse(result["global_disarmament_claim_permitted"])
        self.assertEqual(result["operational_action"], "NONE")

    def test_funding_is_not_destruction(self):
        result = validate_reduction_record(record(stage="FUNDED"))
        self.assertEqual(result["stage"], "FUNDED")
        self.assertIsNone(result["reduction_quantity"])

    def test_comparable_baseline_calculates_reduction(self):
        result = validate_reduction_record(record(
            stage="DECOMMISSIONING_STARTED",
            baseline_quantity=100,
            remaining_quantity=75,
        ))
        self.assertEqual(result["reduction_quantity"], 25)

    def test_dismantled_requires_baseline(self):
        with self.assertRaisesRegex(ValueError, "baseline_quantity"):
            validate_reduction_record(record(stage="DISMANTLED"))

    def test_remaining_cannot_exceed_baseline(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            validate_reduction_record(record(
                baseline_quantity=10, remaining_quantity=11
            ))

    def test_destroyed_requires_zero_remaining(self):
        with self.assertRaisesRegex(ValueError, "equal to zero"):
            validate_reduction_record(record(
                stage="CERTIFIED_DESTROYED",
                baseline_quantity=10,
                remaining_quantity=2,
            ))

    def test_independent_verification_requires_distinct_publishers(self):
        with self.assertRaisesRegex(ValueError, "distinct publishers"):
            validate_reduction_record(record(
                stage="INDEPENDENTLY_VERIFIED",
                baseline_quantity=100,
                remaining_quantity=50,
                verification_method="independent_on_site_inspection",
                sources=[
                    source("Same publisher", "primary_record"),
                    source("Same publisher", "independent_verifier"),
                ],
            ))

    def test_independent_verification_requires_primary_and_verifier(self):
        with self.assertRaisesRegex(ValueError, "primary and independent-verifier"):
            validate_reduction_record(record(
                stage="INDEPENDENTLY_VERIFIED",
                baseline_quantity=100,
                remaining_quantity=50,
                verification_method="independent_on_site_inspection",
                sources=[
                    source("Publisher A", "primary_record"),
                    source("Publisher B", "corroborating"),
                ],
            ))

    def test_independent_verification_requires_timezone(self):
        with self.assertRaisesRegex(ValueError, "include a timezone"):
            validate_reduction_record(record(observed_at="2026-11-09T07:00:00"))

    def test_non_finite_and_boolean_quantities_are_rejected(self):
        for value in (True, float("nan"), float("inf"), -1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_reduction_record(record(
                        baseline_quantity=value,
                        remaining_quantity=0,
                    ))

    def test_https_sources_are_required(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_reduction_record(record(sources=[{
                "url": "http://example.org/evidence",
                "publisher": "Publisher",
                "role": "primary_record",
            }]))

    def test_verified_record_never_claims_global_disarmament(self):
        result = validate_reduction_record(record(
            stage="INDEPENDENTLY_VERIFIED",
            baseline_quantity=100,
            remaining_quantity=40,
            verification_method="treaty_verification_regime",
            sources=[
                source("Treaty authority", "primary_record"),
                source("Independent inspector", "independent_verifier"),
            ],
        ))
        # Distinct publisher labels do not authenticate sources or evidence.
        self.assertEqual(result["evidence_status"], "DOCUMENTED")
        self.assertTrue(result["verification_claimed"])
        self.assertEqual(result["reduction_quantity"], 60)
        self.assertFalse(result["global_disarmament_claim_permitted"])


if __name__ == "__main__":
    unittest.main()
