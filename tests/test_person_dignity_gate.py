"""Tests for controller/person_dignity_gate.py (Issue #268 core slice).

Fail-closed rules: UNKNOWN != PASS, CLAIM != EVIDENCE. The gate
refuses consequential person-decisions without hearing, independent
second review, retaliation-free appeal route, considered
accommodations, and refuses any diagnosis inferred from behaviour or
AI profiling.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.person_dignity_gate import (
    PersonDignityGateError,
    validate_consequential_decision,
)


def valid_record() -> dict:
    return {
        "decision_id": "D-2026-0001",
        "decision_type": "benefits",
        "date": "2026-11-21",
        "decision_maker": "caseworker-01",
        "reasons": ["income above threshold X per criteria sheet"],
        "criteria": "criteria sheet v3, threshold X",
        "consequences": "benefit reduced to level B",
        "appeal_route": "written appeal to unit Q within one month",
        "accommodations_considered": True,
        "traits_used_as_stated_reason": False,
        "retaliation_for_appeal": False,
        "hearing": {
            "offered": True,
            "mode": "accepted",
            "statement": "person corrected income data, attached pay slips",
        },
        "second_review": {
            "reviewer": "caseworker-02",
            "qualification": "senior caseworker, benefits law",
        },
    }


class PersonDignityGateTest(unittest.TestCase):
    def test_valid_decision_passes_and_normalizes(self):
        out = validate_consequential_decision(valid_record())
        self.assertEqual(out["decision_id"], "D-2026-0001")
        self.assertTrue(out["accommodations_considered"])
        self.assertFalse(out["retaliation_for_appeal"])

    def test_non_dict_fails_closed(self):
        with self.assertRaises(PersonDignityGateError):
            validate_consequential_decision(None)

    def test_missing_key_fails_closed(self):
        record = valid_record()
        del record["appeal_route"]
        with self.assertRaises(PersonDignityGateError) as ctx:
            validate_consequential_decision(record)
        self.assertTrue(any("appeal_route" in v for v in ctx.exception.args[0]))

    def test_unknown_decision_type_fails(self):
        record = valid_record()
        record["decision_type"] = "vibe-check"
        with self.assertRaises(PersonDignityGateError):
            validate_consequential_decision(record)

    def test_hearing_not_offered_fails(self):
        record = valid_record()
        record["hearing"] = {"offered": False}
        with self.assertRaises(PersonDignityGateError):
            validate_consequential_decision(record)

    def test_hearing_declined_with_record_passes(self):
        record = valid_record()
        record["hearing"] = {
            "offered": True,
            "mode": "declined_with_record",
            "record_entry": "person declined, offered again via letter",
        }
        out = validate_consequential_decision(record)
        self.assertEqual(out["hearing"]["mode"], "declined_with_record")

    def test_hearing_accepted_without_statement_fails(self):
        record = valid_record()
        record["hearing"] = {"offered": True, "mode": "accepted"}
        with self.assertRaises(PersonDignityGateError):
            validate_consequential_decision(record)

    def test_diagnosis_from_behaviour_inference_fails(self):
        record = valid_record()
        record["diagnoses"] = [
            {"label": "psychiatric condition", "source": "behaviour_inference"}]
        with self.assertRaises(PersonDignityGateError) as ctx:
            validate_consequential_decision(record)
        self.assertTrue(any("behaviour_inference" in v for v in ctx.exception.args[0]))

    def test_diagnosis_from_ai_profile_fails(self):
        record = valid_record()
        record["diagnoses"] = [
            {"label": "unfit", "source": "ai_profile_inference"}]
        with self.assertRaises(PersonDignityGateError):
            validate_consequential_decision(record)

    def test_clinically_documented_diagnosis_passes(self):
        record = valid_record()
        record["diagnoses"] = [
            {"label": "documented clinical finding", "source": "clinical_documented"}]
        out = validate_consequential_decision(record)
        self.assertEqual(out["diagnoses"][0]["source"], "clinical_documented")

    def test_traits_as_stated_reason_fails(self):
        record = valid_record()
        record["traits_used_as_stated_reason"] = True
        with self.assertRaises(PersonDignityGateError) as ctx:
            validate_consequential_decision(record)
        self.assertTrue(any("traits_used_as_stated_reason" in v
                            for v in ctx.exception.args[0]))

    def test_second_reviewer_same_as_maker_fails(self):
        record = valid_record()
        record["second_review"]["reviewer"] = "caseworker-01"
        with self.assertRaises(PersonDignityGateError):
            validate_consequential_decision(record)

    def test_missing_second_review_fails(self):
        record = valid_record()
        del record["second_review"]
        with self.assertRaises(PersonDignityGateError):
            validate_consequential_decision(record)

    def test_retaliation_for_appeal_fails(self):
        record = valid_record()
        record["retaliation_for_appeal"] = True
        with self.assertRaises(PersonDignityGateError):
            validate_consequential_decision(record)

    def test_accommodations_not_considered_fails(self):
        record = valid_record()
        record["accommodations_considered"] = False
        with self.assertRaises(PersonDignityGateError):
            validate_consequential_decision(record)

    def test_empty_reasons_fails(self):
        record = valid_record()
        record["reasons"] = []
        with self.assertRaises(PersonDignityGateError):
            validate_consequential_decision(record)

    def test_all_violations_collected_not_only_first(self):
        record = valid_record()
        record["decision_type"] = "guess"
        record["retaliation_for_appeal"] = True
        with self.assertRaises(PersonDignityGateError) as ctx:
            validate_consequential_decision(record)
        self.assertGreaterEqual(len(ctx.exception.args[0]), 2)


if __name__ == "__main__":
    unittest.main()
