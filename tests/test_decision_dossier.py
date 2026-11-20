"""Tests for controller/decision_dossier.py (Issue #268 second slice).

The dossier keeps facts, personal account, inference and decision
STRICTLY separate: a fact without source is not a fact, an inference
without uncertainty note is not allowed, and the person's side is
recorded (given or explicitly declined). Fail-closed everywhere.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.decision_dossier import (
    DecisionDossierError,
    validate_decision_dossier,
)


def valid_dossier() -> dict:
    return {
        "dossier_id": "DOS-2026-0001",
        "decision_id": "D-2026-0001",
        "date": "2026-11-21",
        "assessor": "caseworker-01",
        "uncertainty": "income data partially self-reported, one pay slip missing",
        "decision": "benefit remains at level A",
        "outcome": "no change; correction of pay slip accepted",
        "escalation_route": "unit Q head, then statutory appeal",
        "verified_facts": [
            {"fact": "monthly income 1420 EUR per pay slips",
             "source": "pay slip 09/2026, submitted copy"},
        ],
        "personal_account": {
            "mode": "given",
            "text": "person states childcare costs were not counted",
        },
        "inferences": [
            {"inference": "benefit level A appropriate",
             "basis": "verified income above threshold X",
             "uncertainty_note": "threshold sheet version unconfirmed",
             "marked_uncertain": True},
        ],
        "correction_invited": True,
        "corrections": [
            {"error": "childcare costs missing",
             "correction": "childcare allowance applied before recheck"},
        ],
        "response_deadline_days": 14,
        "statutory_external_rights_preserved": True,
        "human_review_before_automation": True,
    }


class DecisionDossierTest(unittest.TestCase):
    def test_valid_dossier_passes(self):
        out = validate_decision_dossier(valid_dossier())
        self.assertEqual(out["dossier_id"], "DOS-2026-0001")

    def test_missing_personal_account_fails(self):
        record = valid_dossier()
        del record["personal_account"]
        with self.assertRaises(DecisionDossierError):
            validate_decision_dossier(record)

    def test_account_given_without_text_fails(self):
        record = valid_dossier()
        record["personal_account"] = {"mode": "given"}
        with self.assertRaises(DecisionDossierError):
            validate_decision_dossier(record)

    def test_account_declined_without_record_entry_fails(self):
        record = valid_dossier()
        record["personal_account"] = {"mode": "declined_with_record"}
        with self.assertRaises(DecisionDossierError):
            validate_decision_dossier(record)

    def test_inference_without_uncertainty_fails(self):
        record = valid_dossier()
        record["inferences"] = [
            {"inference": "unfit", "basis": "gut feeling",
             "marked_uncertain": False}]
        with self.assertRaises(DecisionDossierError) as ctx:
            validate_decision_dossier(record)
        self.assertTrue(any("inferences[0]" in v for v in ctx.exception.args[0]))

    def test_empty_inference_list_is_honest_and_valid(self):
        record = valid_dossier()
        record["inferences"] = []
        out = validate_decision_dossier(record)
        self.assertEqual(out["inferences"], [])

    def test_correction_not_invited_fails(self):
        record = valid_dossier()
        record["correction_invited"] = False
        with self.assertRaises(DecisionDossierError):
            validate_decision_dossier(record)

    def test_zero_deadline_days_fails(self):
        record = valid_dossier()
        record["response_deadline_days"] = 0
        with self.assertRaises(DecisionDossierError):
            validate_decision_dossier(record)

    def test_statutory_rights_not_preserved_fails(self):
        record = valid_dossier()
        record["statutory_external_rights_preserved"] = False
        with self.assertRaises(DecisionDossierError):
            validate_decision_dossier(record)

    def test_missing_human_review_fails(self):
        record = valid_dossier()
        record["human_review_before_automation"] = False
        with self.assertRaises(DecisionDossierError):
            validate_decision_dossier(record)

    def test_dossier_chains_with_dignity_gate(self):
        from controller.person_dignity_gate import (
            PersonDignityGateError,
            validate_consequential_decision,
        )
        decision = {
            "decision_id": "D-2026-0001",
            "decision_type": "benefits",
            "date": "2026-11-21",
            "decision_maker": "caseworker-01",
            "reasons": ["income above threshold X"],
            "criteria": "criteria sheet v3",
            "consequences": "no change",
            "appeal_route": "written appeal to unit Q",
            "accommodations_considered": True,
            "traits_used_as_stated_reason": False,
            "retaliation_for_appeal": False,
            "hearing": {"offered": True, "mode": "accepted",
                        "statement": "person corrected childcare costs"},
            "second_review": {"reviewer": "caseworker-02",
                              "qualification": "senior caseworker"},
        }
        self.assertEqual(
            validate_consequential_decision(decision)["decision_id"],
            validate_decision_dossier(valid_dossier())["decision_id"])
        with self.assertRaises(PersonDignityGateError):
            validate_consequential_decision({})


if __name__ == "__main__":
    unittest.main()
