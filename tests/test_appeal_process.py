'''Tests for controller.appeal_process (Issue #276, capability 7).

All test data remains pure ASCII (<= 0x7F) per repo convention.
'''

import unittest

from controller import appeal_process as ap


def valid_appeal(aid="A-001", decision="D-001"):
    return {
        "appeal_id": aid,
        "decision_id": decision,
        "decision_maker": "maker@example",
        "appellant": "person@example",
        "filed_on": "2026-11-21",
        "grounds": ["factual_error", "criticism_of_decision"],
        "effects_suspended": True,
    }


def valid_assignment(reviewer="reviewer@example"):
    return {"reviewer": reviewer, "qualification": "trained appeal reviewer"}


def valid_resolution(outcome="upheld"):
    base = {
        "resolved_by": "reviewer@example",
        "outcome": outcome,
        "resolved_on": "2026-11-21",
        "statement": "reviewed the record and the evidence",
    }
    if outcome == "remanded":
        base["remand_instructions"] = "new decision with corrected facts"
    return base


class TestFiling(unittest.TestCase):
    def test_file_appeal_pending(self):
        load = ap.new_caseload()
        self.assertEqual(ap.file_appeal(load, valid_appeal()), "PENDING")

    def test_effects_must_be_suspended(self):
        load = ap.new_caseload()
        appeal = valid_appeal()
        appeal["effects_suspended"] = False
        with self.assertRaises(ap.AppealProcessError):
            ap.file_appeal(load, appeal)

    def test_unknown_ground_rejected(self):
        load = ap.new_caseload()
        appeal = valid_appeal()
        appeal["grounds"] = ["revenge"]
        with self.assertRaises(ap.AppealProcessError):
            ap.file_appeal(load, appeal)

    def test_criticism_ground_allowed(self):
        load = ap.new_caseload()
        appeal = valid_appeal()
        appeal["grounds"] = ["criticism_of_decision"]
        self.assertEqual(ap.file_appeal(load, appeal), "PENDING")

    def test_empty_grounds_rejected(self):
        load = ap.new_caseload()
        appeal = valid_appeal()
        appeal["grounds"] = []
        with self.assertRaises(ap.AppealProcessError):
            ap.file_appeal(load, appeal)

    def test_missing_appellant_rejected(self):
        load = ap.new_caseload()
        appeal = valid_appeal()
        appeal["appellant"] = " "
        with self.assertRaises(ap.AppealProcessError):
            ap.file_appeal(load, appeal)

    def test_duplicate_id_rejected(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        with self.assertRaises(ap.AppealProcessError):
            ap.file_appeal(load, valid_appeal())

    def test_duplicate_open_appeal_same_appellant_decision(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal("A-001"))
        with self.assertRaises(ap.AppealProcessError):
            ap.file_appeal(load, valid_appeal("A-002"))

    def test_second_appeal_after_resolution_allowed(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal("A-001"))
        ap.assign_review(load, "A-001", valid_assignment())
        ap.resolve_appeal(load, "A-001", valid_resolution("upheld"))
        self.assertEqual(ap.file_appeal(load, valid_appeal("A-002")), "PENDING")

    def test_malformed_evidence_rejected(self):
        load = ap.new_caseload()
        appeal = valid_appeal()
        appeal["evidence"] = "not-a-list"
        with self.assertRaises(ap.AppealProcessError):
            ap.file_appeal(load, appeal)


class TestReviewAssignment(unittest.TestCase):
    def test_assign_review_in_review(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        status = ap.assign_review(load, "A-001", valid_assignment())
        self.assertEqual(status, "IN_REVIEW")

    def test_reviewer_cannot_be_decision_maker(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        assignment = {"reviewer": "maker@example", "qualification": "x"}
        with self.assertRaises(ap.AppealProcessError):
            ap.assign_review(load, "A-001", assignment)

    def test_reviewer_cannot_be_appellant(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        assignment = {"reviewer": "person@example", "qualification": "x"}
        with self.assertRaises(ap.AppealProcessError):
            ap.assign_review(load, "A-001", assignment)

    def test_missing_qualification_rejected(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        assignment = {"reviewer": "reviewer@example", "qualification": " "}
        with self.assertRaises(ap.AppealProcessError):
            ap.assign_review(load, "A-001", assignment)

    def test_assign_review_twice_rejected(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        ap.assign_review(load, "A-001", valid_assignment())
        with self.assertRaises(ap.AppealProcessError):
            ap.assign_review(load, "A-001", valid_assignment())


class TestEvidence(unittest.TestCase):
    def test_appellant_may_add_evidence(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        ap.add_evidence(load, "A-001", {"person": "person@example", "source": "log sample"})
        self.assertEqual(len(load["appeals"]["A-001"]["evidence"]), 1)

    def test_third_party_evidence_rejected(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        with self.assertRaises(ap.AppealProcessError):
            ap.add_evidence(load, "A-001", {"person": "stranger@example", "source": "x"})

    def test_evidence_after_resolution_rejected(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        ap.assign_review(load, "A-001", valid_assignment())
        ap.resolve_appeal(load, "A-001", valid_resolution("upheld"))
        with self.assertRaises(ap.AppealProcessError):
            ap.add_evidence(load, "A-001", {"person": "person@example", "source": "x"})

    def test_evidence_missing_source_rejected(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        with self.assertRaises(ap.AppealProcessError):
            ap.add_evidence(load, "A-001", {"person": "person@example", "source": " "})


class TestResolution(unittest.TestCase):
    def test_upheld(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        ap.assign_review(load, "A-001", valid_assignment())
        self.assertEqual(ap.resolve_appeal(load, "A-001", valid_resolution("upheld")), "RESOLVED")

    def test_overturned_keeps_original_record(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        ap.assign_review(load, "A-001", valid_assignment())
        ap.resolve_appeal(load, "A-001", valid_resolution("overturned"))
        appeal = load["appeals"]["A-001"]
        self.assertEqual(appeal["decision_id"], "D-001")
        self.assertEqual(appeal["outcome"], "overturned")

    def test_remand_requires_instructions(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        ap.assign_review(load, "A-001", valid_assignment())
        resolution = {
            "resolved_by": "reviewer@example",
            "outcome": "remanded",
            "resolved_on": "2026-11-21",
            "statement": "facts need rework",
        }
        with self.assertRaises(ap.AppealProcessError):
            ap.resolve_appeal(load, "A-001", resolution)

    def test_remand_with_instructions(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        ap.assign_review(load, "A-001", valid_assignment())
        self.assertEqual(ap.resolve_appeal(load, "A-001", valid_resolution("remanded")), "RESOLVED")

    def test_unknown_outcome_rejected(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        ap.assign_review(load, "A-001", valid_assignment())
        with self.assertRaises(ap.AppealProcessError):
            ap.resolve_appeal(load, "A-001", valid_resolution("ignored"))

    def test_resolve_without_review_rejected(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        with self.assertRaises(ap.AppealProcessError):
            ap.resolve_appeal(load, "A-001", valid_resolution("upheld"))

    def test_resolver_must_be_assigned_reviewer(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        ap.assign_review(load, "A-001", valid_assignment("first@example"))
        resolution = valid_resolution("upheld")
        resolution["resolved_by"] = "second@example"
        with self.assertRaises(ap.AppealProcessError):
            ap.resolve_appeal(load, "A-001", resolution)

    def test_resolve_twice_rejected(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        ap.assign_review(load, "A-001", valid_assignment())
        ap.resolve_appeal(load, "A-001", valid_resolution("upheld"))
        with self.assertRaises(ap.AppealProcessError):
            ap.resolve_appeal(load, "A-001", valid_resolution("upheld"))

    def test_missing_statement_rejected(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        ap.assign_review(load, "A-001", valid_assignment())
        resolution = valid_resolution("upheld")
        resolution["statement"] = ""
        with self.assertRaises(ap.AppealProcessError):
            ap.resolve_appeal(load, "A-001", resolution)


class TestSummary(unittest.TestCase):
    def test_empty_caseload(self):
        summary = ap.summarize(ap.new_caseload())
        self.assertEqual(summary["appeals_total"], 0)
        self.assertEqual(summary["pending"], 0)

    def test_counts_all_states(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal("A-001"))
        ap.file_appeal(load, valid_appeal("A-002", decision="D-002"))
        ap.file_appeal(load, valid_appeal("A-003", decision="D-003"))
        ap.assign_review(load, "A-002", valid_assignment())
        ap.assign_review(load, "A-003", valid_assignment())
        ap.resolve_appeal(load, "A-003", valid_resolution("overturned"))
        summary = ap.summarize(load)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["in_review"], 1)
        self.assertEqual(summary["resolved"], 1)
        self.assertEqual(summary["by_outcome"]["overturned"], 1)

    def test_summary_has_no_personal_data(self):
        load = ap.new_caseload()
        ap.file_appeal(load, valid_appeal())
        rendered = repr(ap.summarize(load))
        self.assertNotIn("person@example", rendered)
        self.assertNotIn("maker@example", rendered)

    def test_malformed_caseload_rejected(self):
        with self.assertRaises(ap.AppealProcessError):
            ap.summarize({"nope": {}})

    def test_honesty_limits_present(self):
        summary = ap.summarize(ap.new_caseload())
        self.assertIn("CRITICISM != VERBOT", summary["honesty_limits"])
        self.assertIn("RECORDS != GERECHTIGKEIT", summary["honesty_limits"])


def full_lifecycle():
    load = ap.new_caseload()
    ap.file_appeal(load, valid_appeal())
    ap.assign_review(load, "A-001", valid_assignment())
    ap.resolve_appeal(load, "A-001", valid_resolution("overturned"))
    return load


if __name__ == "__main__":
    unittest.main()
