import unittest

from disarmament.monitor import evaluate_dataset, evaluate_record


def source(publisher, role, source_type="international_body"):
    return {
        "url": "https://example.org/evidence",
        "publisher": publisher,
        "source_type": source_type,
        "role": role,
        "retrieved_at": "2026-11-09T10:00:00Z",
        "sha256": "a" * 64,
    }


def record(**overrides):
    value = {
        "record_id": "sample-001",
        "category": "nuclear",
        "claim": "A treaty-related report was published.",
        "scope": "Treaty report",
        "observed_at": "2026-11-09T09:00:00Z",
        "verification_method": "none",
        "sources": [],
    }
    value.update(overrides)
    return value


class DisarmamentMonitorTests(unittest.TestCase):
    def test_no_sources_is_unknown_not_pass(self):
        result = evaluate_record(record())
        self.assertEqual(result["evidence_grade"], "UNKNOWN")
        self.assertFalse(result["global_claim_permitted"])

    def test_one_source_is_documented_not_verified(self):
        result = evaluate_record(record(sources=[source("UN source", "primary_record")]))
        self.assertEqual(result["evidence_grade"], "DOCUMENTED")

    def test_two_publishers_are_corroborated(self):
        result = evaluate_record(record(sources=[
            source("Publisher A", "primary_record"),
            source("Publisher B", "corroborating", "independent_research"),
        ]))
        self.assertEqual(result["evidence_grade"], "CORROBORATED")

    def test_verified_requires_strong_method_and_independent_verifier(self):
        sources = [
            source("Treaty body", "primary_record"),
            source("Independent inspector", "independent_verifier", "independent_research"),
        ]
        result = evaluate_record(record(
            verification_method="independent_on_site_inspection", sources=sources
        ))
        self.assertEqual(result["evidence_grade"], "VERIFIED")

    def test_two_sources_without_strong_method_are_not_verified(self):
        result = evaluate_record(record(sources=[
            source("Publisher A", "primary_record"),
            source("Publisher B", "independent_verifier", "independent_research"),
        ]))
        self.assertEqual(result["evidence_grade"], "CORROBORATED")

    def test_satellite_is_not_automatically_a_weapon(self):
        result = evaluate_record(record(
            category="space_security", space_object_class="civilian"
        ))
        self.assertEqual(result["space_object_class"], "civilian")
        self.assertEqual(result["operational_action"], "NONE")

    def test_invalid_url_and_digest_are_rejected(self):
        bad = source("Publisher", "primary_record")
        bad["url"] = "http://example.org"
        with self.assertRaises(ValueError):
            evaluate_record(record(sources=[bad]))
        bad = source("Publisher", "primary_record")
        bad["sha256"] = "not-a-digest"
        with self.assertRaises(ValueError):
            evaluate_record(record(sources=[bad]))

    def test_dataset_never_infers_global_disarmament(self):
        result = evaluate_dataset({"records": [record()]})
        self.assertEqual(result["scope"], "supplied_records_only")
        self.assertEqual(result["global_disarmament_status"], "UNKNOWN")
        self.assertIsNone(result["global_inventory_total"])
        self.assertFalse(result["operational_controls"])

    def test_empty_dataset_is_unknown(self):
        result = evaluate_dataset({"records": []})
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
