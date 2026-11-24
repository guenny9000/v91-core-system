"""Tests fuer controller/decoupling_audit.py (Mini-Runner-kompatibel, stdlib-only)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller.decoupling_audit import (
    AUDIT_STATUS,
    DecouplingAuditError,
    PLAN_MARKER,
    REVIEW_REQUIRED,
    UNKNOWN_TIER,
    evaluate_decoupling_plan,
    evaluate_entry,
    local_global_ratio,
    main,
)


def essential(evidence="ledger::water-pump-001"):
    return {"component": "water pump", "tier": "essential", "evidence": evidence}


class EntryTests(unittest.TestCase):
    def test_essential_with_valid_evidence(self):
        r = evaluate_entry(essential())
        self.assertEqual(r["state"], "ESSENTIAL_EVIDENCED")

    def test_essential_missing_evidence_fail_closed(self):
        self.assertEqual(evaluate_entry({"component": "x", "tier": "essential"})["state"], REVIEW_REQUIRED)

    def test_essential_invalid_evidence_fail_closed(self):
        self.assertEqual(evaluate_entry(essential(evidence="   "))["state"], REVIEW_REQUIRED)

    def test_essential_http_reference_valid(self):
        self.assertEqual(evaluate_entry(essential(evidence="https://example.org/ledger/1"))["state"], "ESSENTIAL_EVIDENCED")

    def test_unknown_tier_rejected(self):
        self.assertEqual(evaluate_entry({"component": "x", "tier": "mystery"})["state"], UNKNOWN_TIER)

    def test_tier_case_insensitive_trimmed(self):
        r = evaluate_entry({"component": "x", "tier": "  ESSENTIAL  ", "evidence": "doi:10.0000/x"})
        self.assertEqual(r["tier"], "essential")

    def test_circulating_and_opulence_classified_without_evidence(self):
        self.assertEqual(evaluate_entry({"component": "a", "tier": "circulating"})["state"], "CLASSIFIED_CIRCULATING")
        self.assertEqual(evaluate_entry({"component": "b", "tier": "opulence"})["state"], "CLASSIFIED_OPULENCE")

    def test_non_dict_entry_raises(self):
        with self.assertRaises(DecouplingAuditError):
            evaluate_entry("kein objekt")

    def test_empty_component_name_raises(self):
        with self.assertRaises(DecouplingAuditError):
            evaluate_entry({"component": "  ", "tier": "opulence"})


class PlanTests(unittest.TestCase):
    def test_counts_and_gates(self):
        plan = evaluate_decoupling_plan([
            essential(),
            {"component": "satellite link", "tier": "circulating"},
            {"component": "mega datacenter", "tier": "opulence"},
            {"component": "y", "tier": "essential"},
            {"component": "z", "tier": "weird"},
        ])
        self.assertEqual(plan["tier_counts"], {"essential": 2, "circulating": 1, "opulence": 1})
        self.assertEqual(plan["review_required"], 1)
        self.assertEqual(plan["unknown_tiers"], 1)
        self.assertEqual(plan["review_status"], AUDIT_STATUS)
        self.assertTrue(plan[PLAN_MARKER])

    def test_duplicate_component_fail_closed(self):
        with self.assertRaises(DecouplingAuditError):
            evaluate_decoupling_plan([essential(), essential(evidence="doi:10.1/y")])

    def test_empty_entries_rejected(self):
        for bad in ([], "nope", None):
            with self.assertRaises(DecouplingAuditError):
                evaluate_decoupling_plan(bad)

    def test_ratio_attached_and_labeled(self):
        plan = evaluate_decoupling_plan([essential()], ratio=local_global_ratio(25.0, 100.0))
        self.assertEqual(plan["ratio"]["ratio"], 0.25)
        self.assertEqual(plan["ratio"]["ratio_status"], "CALCULATED_ONLY")
        self.assertEqual(plan["ratio"]["calibration_status"], "UNKNOWN")

    def test_bad_ratio_object_rejected(self):
        with self.assertRaises(DecouplingAuditError):
            evaluate_decoupling_plan([essential()], ratio="25/100")


class RatioTests(unittest.TestCase):
    def test_ratio_value(self):
        self.assertEqual(local_global_ratio(1, 4)["ratio"], 0.25)

    def test_bool_rejected(self):
        with self.assertRaises(DecouplingAuditError):
            local_global_ratio(True, 100)

    def test_negative_and_zero_rejected(self):
        with self.assertRaises(DecouplingAuditError):
            local_global_ratio(-1, 100)
        with self.assertRaises(DecouplingAuditError):
            local_global_ratio(1, 0)

    def test_local_exceeding_total_rejected(self):
        with self.assertRaises(DecouplingAuditError):
            local_global_ratio(101, 100)

    def test_nan_and_string_rejected(self):
        with self.assertRaises(DecouplingAuditError):
            local_global_ratio(float("nan"), 100)
        with self.assertRaises(DecouplingAuditError):
            local_global_ratio("25", 100)


class CliTests(unittest.TestCase):
    def _run(self, payload):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ, PYTHONPATH=root)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(payload, fh)
            name = fh.name
        try:
            proc = subprocess.run(
                [sys.executable, os.path.join(root, "controller", "decoupling_audit.py"), name],
                capture_output=True, text=True, env=env,
            )
        finally:
            os.unlink(name)
        return proc

    def test_exit_0_on_clean_plan(self):
        proc = self._run({"entries": [essential(), {"component": "a", "tier": "opulence"}]})
        self.assertEqual(proc.returncode, 0)
        self.assertIn(PLAN_MARKER, proc.stdout)

    def test_exit_1_on_review_required(self):
        proc = self._run({"entries": [{"component": "a", "tier": "essential"}]})
        self.assertEqual(proc.returncode, 1)
        self.assertIn(REVIEW_REQUIRED, proc.stdout)

    def test_exit_2_on_invalid_input(self):
        proc = self._run({"entries": []})
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error", proc.stdout)


if __name__ == "__main__":
    unittest.main()
