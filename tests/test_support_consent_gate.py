"""Tests for controller/support_consent_gate.py (Issue #268 third slice).

Ethical support/therapy records fail closed without voluntariness
(or a documented legal mandate with offered independent oversight),
informed consent disclosures, agreed goals, no coercion, no
refusal-as-incapacity, honest treatment classification and
privacy minimum-necessary sharing.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.support_consent_gate import (
    SupportConsentGateError,
    validate_support_record,
)


def valid_support() -> dict:
    return {
        "support_id": "SUP-2026-0001",
        "date": "2026-11-21",
        "provider": "practice-07",
        "voluntary": True,
        "informed_consent": {
            "risks": "side effects listed in leaflet, discussed",
            "alternatives": "two other approaches offered",
            "costs": "covered by insurance, no private payment",
            "conflicts_of_interest": "none declared",
            "questions_invited": True,
        },
        "goals_agreed_with_person": True,
        "refusal_treated_as_incapacity": False,
        "coercive_treatment": False,
        "humiliating_treatment": False,
        "punitive_purpose": False,
        "identity_erasing_treatment": False,
        "treatment_classification": "evidence_based",
        "minimum_necessary_sharing": True,
        "privacy_legal_basis": "consent per Art. 9 GDPR, documented 2026-11-21",
    }


class SupportConsentGateTest(unittest.TestCase):
    def test_valid_voluntary_support_passes(self):
        out = validate_support_record(valid_support())
        self.assertEqual(out["support_id"], "SUP-2026-0001")

    def test_non_dict_fails_closed(self):
        with self.assertRaises(SupportConsentGateError):
            validate_support_record(None)

    def test_missing_disclosure_fails(self):
        record = valid_support()
        del record["informed_consent"]["risks"]
        with self.assertRaises(SupportConsentGateError) as ctx:
            validate_support_record(record)
        self.assertTrue(any("informed_consent.risks" in v
                            for v in ctx.exception.args[0]))

    def test_consent_without_questions_invited_fails(self):
        record = valid_support()
        record["informed_consent"]["questions_invited"] = False
        with self.assertRaises(SupportConsentGateError):
            validate_support_record(record)

    def test_involuntary_without_legal_basis_fails(self):
        record = valid_support()
        record["voluntary"] = False
        del record["informed_consent"]
        with self.assertRaises(SupportConsentGateError):
            validate_support_record(record)

    def test_involuntary_with_documented_mandate_passes(self):
        record = valid_support()
        record["voluntary"] = False
        record["legal_mandate"] = {
            "legal_basis": "court order AZ 2026-X, dated 2026-11-20",
            "independent_oversight_offered": True,
        }
        out = validate_support_record(record)
        self.assertFalse(out["voluntary"])

    def test_goals_imposed_fails(self):
        record = valid_support()
        record["goals_agreed_with_person"] = False
        with self.assertRaises(SupportConsentGateError):
            validate_support_record(record)

    def test_refusal_as_incapacity_fails(self):
        record = valid_support()
        record["refusal_treated_as_incapacity"] = True
        with self.assertRaises(SupportConsentGateError):
            validate_support_record(record)

    def test_coercive_treatment_fails(self):
        record = valid_support()
        record["coercive_treatment"] = True
        with self.assertRaises(SupportConsentGateError):
            validate_support_record(record)

    def test_identity_erasing_treatment_fails(self):
        record = valid_support()
        record["identity_erasing_treatment"] = True
        with self.assertRaises(SupportConsentGateError):
            validate_support_record(record)

    def test_missing_classification_fails(self):
        record = valid_support()
        del record["treatment_classification"]
        with self.assertRaises(SupportConsentGateError):
            validate_support_record(record)

    def test_experimental_without_acknowledgement_fails(self):
        record = valid_support()
        record["treatment_classification"] = "experimental"
        with self.assertRaises(SupportConsentGateError) as ctx:
            validate_support_record(record)
        self.assertTrue(any("experimental_status_acknowledged" in v
                            for v in ctx.exception.args[0]))

    def test_experimental_with_acknowledgement_passes(self):
        record = valid_support()
        record["treatment_classification"] = "experimental"
        record["informed_consent"]["experimental_status_acknowledged"] = True
        out = validate_support_record(record)
        self.assertEqual(out["treatment_classification"], "experimental")

    def test_missing_privacy_legal_basis_fails(self):
        record = valid_support()
        record["privacy_legal_basis"] = ""
        with self.assertRaises(SupportConsentGateError):
            validate_support_record(record)

    def test_over_sharing_fails(self):
        record = valid_support()
        record["minimum_necessary_sharing"] = False
        with self.assertRaises(SupportConsentGateError):
            validate_support_record(record)


if __name__ == "__main__":
    unittest.main()
