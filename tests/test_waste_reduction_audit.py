"""Tests for controller/waste_reduction_audit.py (Issue #268 section 5).

Waste-cut proposals fail closed when they remove services, human
contact, local jobs or support routes without measured outcome
evidence and an equivalent-access replacement, when they compare
purchase price only, when preferred alternatives (repair, local
capacity, open standards, durable tools, cooperative purchasing)
are cheaper but ignored without justification, and when existing
structures are cut without duplicate or unused evidence.
People are never a cost centre.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.waste_reduction_audit import (
    WasteReductionAuditError,
    validate_spend_cut,
)


def valid_unused_software() -> dict:
    return {
        "audit_id": "WRA-2026-0001",
        "date": "2026-11-21",
        "reviewer": "session-vibe",
        "cut_type": "unused_software",
        "removes_service": False,
        "removes_human_contact": False,
        "removes_local_jobs": False,
        "removes_support_route": False,
        "people_as_cost_centre": False,
        "automated_replacement_cheaper_only": False,
        "lifecycle_cost_required": False,
        "conflicts_of_interest": {"confirmed_none": True},
        "duplicate_or_unused_evidence": {
            "finding": "0 logins in 180 days per IdP export 2026-11-01",
            "checked_by": "it-auditor-2",
        },
        "uncertainty_note": "export covers SSO only, local logins possible",
    }


def valid_people_safe_reduction() -> dict:
    record = valid_unused_software()
    record.update(
        {
            "cut_type": "service_reduction",
            "removes_service": True,
            "lifecycle_cost_required": True,
            "lifecycle_cost_comparison": {
                "purchase_price_only": False,
                "procurement_eur": 40000,
                "maintenance_eur": 5000,
                "energy_eur": 800,
                "travel_eur": 0,
                "environmental_effects": "one avoided on-site trip per week",
                "accessibility_effects": "phone line kept, WCAG 2.2 AA portal",
                "failure_rate": "vendor SLA 99.5, fallback phone line",
                "hidden_burdens_shifted": {"justified_none": True},
            },
            "outcome_evidence": {
                "measured_outcome": "processing time -38% in 12-week shadow run",
                "measured_on": "2026-11-14",
                "method": "shadow run, 400 cases, two-tailed test",
            },
            "replacement_guarantee": {
                "equivalent_access": True,
                "transition_support": "two training sessions plus hotline for 8 weeks",
            },
            "alternatives_considered": [
                {
                    "option": "open_standard",
                    "lifecycle_cost_total_eur": 52000,
                    "access_equivalent": True,
                }
            ],
            "chosen_lifecycle_cost_total_eur": 45800,
        }
    )
    return record


class WasteReductionAuditTest(unittest.TestCase):
    def test_valid_unused_software_passes(self):
        out = validate_spend_cut(valid_unused_software())
        self.assertEqual(out["decision"], "APPROVED_WITH_CONDITIONS")
        self.assertEqual(out["audit_id"], "WRA-2026-0001")
        self.assertEqual(out["violations"], [])

    def test_non_dict_fails_closed(self):
        with self.assertRaises(WasteReductionAuditError):
            validate_spend_cut(None)

    def test_service_cut_without_evidence_rejected(self):
        record = valid_people_safe_reduction()
        del record["outcome_evidence"]
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(
            any("people_guard:measured_outcome_evidence_missing" in v
                for v in out["violations"])
        )

    def test_automation_cheaper_only_rejected(self):
        record = valid_people_safe_reduction()
        record["automated_replacement_cheaper_only"] = True
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(
            any("people_not_cost_centre" in v for v in out["violations"])
        )

    def test_replacement_without_equivalent_access_rejected(self):
        record = valid_people_safe_reduction()
        record["replacement_guarantee"]["equivalent_access"] = False
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(
            any("replacement_access_not_proven_equivalent" in v
                for v in out["violations"])
        )

    def test_transition_support_required(self):
        record = valid_people_safe_reduction()
        record["replacement_guarantee"]["transition_support"] = ""
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(
            any("transition_support_missing" in v for v in out["violations"])
        )

    def test_purchase_price_only_rejected(self):
        record = valid_people_safe_reduction()
        record["lifecycle_cost_comparison"]["purchase_price_only"] = True
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(
            any("purchase_price_is_not_a_cost_comparison" in v
                for v in out["violations"])
        )

    def test_hidden_burdens_unaddressed_rejected(self):
        record = valid_people_safe_reduction()
        record["lifecycle_cost_comparison"]["hidden_burdens_shifted"] = None
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(
            any("hidden_burdens" in v for v in out["violations"])
        )

    def test_hidden_burdens_quantified_ok(self):
        record = valid_people_safe_reduction()
        record["lifecycle_cost_comparison"]["hidden_burdens_shifted"] = {
            "hours_per_week": 1.5,
            "cost_estimate_eur": 900,
        }
        out = validate_spend_cut(record)
        self.assertEqual(
            any("hidden_burdens" in v for v in out["violations"]), False
        )

    def test_lifecycle_component_missing_rejected(self):
        record = valid_people_safe_reduction()
        del record["lifecycle_cost_comparison"]["energy_eur"]
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(
            any("lifecycle:component_missing:energy_eur" in v
                for v in out["violations"])
        )

    def test_cheaper_repair_ignored_rejected(self):
        record = valid_people_safe_reduction()
        record["alternatives_considered"].append(
            {
                "option": "repair",
                "lifecycle_cost_total_eur": 21000,
                "access_equivalent": True,
            }
        )
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(
            any("preferred_alternative_lower_cost_without_justification" in v
                for v in out["violations"])
        )

    def test_cheaper_repair_with_justification_passes(self):
        record = valid_people_safe_reduction()
        record["procurement_deviation_justification"] = (
            "repair does not reach WCAG 2.2 AA, accessibility documented in "
            "lifecycle comparison"
        )
        record["alternatives_considered"].append(
            {
                "option": "repair",
                "lifecycle_cost_total_eur": 21000,
                "access_equivalent": True,
            }
        )
        out = validate_spend_cut(record)
        self.assertEqual(out["violations"], [])

    def test_no_alternatives_considered_rejected(self):
        record = valid_people_safe_reduction()
        record["alternatives_considered"] = []
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(any("alternatives:none_considered" in v
                           for v in out["violations"]))

    def test_duplicate_structure_without_evidence_rejected(self):
        record = valid_unused_software()
        del record["duplicate_or_unused_evidence"]
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(
            any("duplicate_or_unused_proof_missing" in v
                for v in out["violations"])
        )

    def test_unknown_cut_type_rejected(self):
        record = valid_unused_software()
        record["cut_type"] = "cheaper_automation_replacement"
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(any("unknown_cut_type" in v for v in out["violations"]))

    def test_people_as_cost_centre_rejected(self):
        record = valid_unused_software()
        record["people_as_cost_centre"] = True
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(
            any("people_not_cost_centre" in v for v in out["violations"])
        )

    def test_uncertainty_note_required(self):
        record = valid_unused_software()
        record["uncertainty_note"] = "  "
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(any("uncertainty_note_missing" in v
                           for v in out["violations"]))

    def test_conflicts_of_interest_required(self):
        record = valid_unused_software()
        record["conflicts_of_interest"] = {}
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        self.assertTrue(
            any("conflicts_of_interest_not_addressed" in v
                for v in out["violations"])
        )

    def test_declared_conflict_passes(self):
        record = valid_unused_software()
        record["conflicts_of_interest"] = {"declared": True}
        out = validate_spend_cut(record)
        self.assertEqual(out["violations"], [])

    def test_honesty_limits_stated(self):
        out = validate_spend_cut(valid_unused_software())
        self.assertIn("SCRIPTED != INSTALLED", out["honesty_limits"])
        self.assertIn("REVIEW != DECISION", out["honesty_limits"])

    def test_all_violations_collected(self):
        record = valid_people_safe_reduction()
        record["automated_replacement_cheaper_only"] = True
        del record["outcome_evidence"]
        del record["replacement_guarantee"]
        record["people_as_cost_centre"] = True
        out = validate_spend_cut(record)
        self.assertEqual(out["decision"], "REJECTED")
        merged = " | ".join(out["violations"])
        self.assertIn("automation_price", merged)
        self.assertIn("outcome_evidence_missing", merged)
        self.assertIn("replacement_missing", merged)
        self.assertIn("cost_centre", merged)


if __name__ == "__main__":
    unittest.main()
