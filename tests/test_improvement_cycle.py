#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Tests: controller/improvement_cycle.py (Issue #276, Faehigkeit 9).
"""
from __future__ import annotations

import unittest

from controller.impact_area_registry import EvidenceBundle
from controller.improvement_cycle import (
    AuthorizationRecord,
    ImprovementCycleError,
    ImprovementProposal,
    OutcomeReport,
    RolloutStage,
    TestRecord,
    cycle_report,
    evaluate_proposal,
    outcome_status,
    OUTCOME_NICHT_VERBESSERT,
    OUTCOME_VERBESSERT,
    POST_CHANGE_PENDING,
    VERDICT_BLOCKED,
    VERDICT_NOT_AUTHORIZED,
    VERDICT_READY,
    VERDICT_UNDECIDABLE,
    VERDICT_ZIELKONFLIKT_BLOCK,
)

EV = EvidenceBundle(
    source="operator test protocol 2026-11-21",
    method="executed regression suite",
    period_start="2026-11-21T10:00:00Z",
    period_end="2026-11-21T11:00:00Z",
    reference="protocol-4711",
)

GOOD_STAGES = (
    RolloutStage("stufe-1-canary", 0.05),
    RolloutStage("stufe-2-quartal", 0.15),
    RolloutStage("stufe-3-rest", 0.8),
)


def good_proposal(**overrides) -> ImprovementProposal:
    params = dict(
        proposal_id="imp-0001",
        node_id="node-a",
        proposer="node-a-agent",
        target_component="measurement_store",
        description="Reduce redundant re-ingest work in store.",
        goal="Halve median ingest latency without losing values.",
        tests=TestRecord(True, EV),
        authorization=AuthorizationRecord(
            authorized_by="operator-sebastian",
            proposal_id="imp-0001",
            scope="node-a measurement_store ingest path",
            expires="2026-12-31"),
        rollback_plan="revert to previous ingest worker build",
        rollback_tested=True,
        rollout_stages=GOOD_STAGES,
        rebound_verdict=None,
    )
    params.update(overrides)
    return ImprovementProposal(**params)


class ValidationTestCase(unittest.TestCase):
    def test_valid_proposal_accepted(self):
        self.assertEqual(
            evaluate_proposal(good_proposal())["verdict"], VERDICT_READY)

    def test_missing_goal_rejected(self):
        with self.assertRaises(ImprovementCycleError):
            evaluate_proposal(good_proposal(goal=" "))

    def test_rebound_verdict_unknown_rejected(self):
        with self.assertRaises(ImprovementCycleError):
            evaluate_proposal(good_proposal(rebound_verdict="ROTSPECK"))

    def test_fraction_zero_rejected(self):
        with self.assertRaises(ImprovementCycleError):
            evaluate_proposal(good_proposal(rollout_stages=(
                RolloutStage("s0", 0.0),
                RolloutStage("s1", 1.0))))

    def test_fraction_above_one_rejected(self):
        with self.assertRaises(ImprovementCycleError):
            evaluate_proposal(good_proposal(rollout_stages=(
                RolloutStage("s0", 1.5),
                RolloutStage("s1", 1.0))))


class AuthorizationTestCase(unittest.TestCase):
    def test_no_authorization_not_authorized(self):
        result = evaluate_proposal(good_proposal(authorization=None))
        self.assertEqual(result["verdict"], VERDICT_NOT_AUTHORIZED)
        self.assertIn("NOT_AUTHORIZED", result["blocking_reasons"])

    def test_self_authorization_refused(self):
        result = evaluate_proposal(good_proposal(
            authorization=AuthorizationRecord(
                authorized_by="node-a-agent",
                proposal_id="imp-0001",
                scope="x", expires="2026-12-31")))
        self.assertEqual(result["verdict"], VERDICT_NOT_AUTHORIZED)
        self.assertIn(
            "SELF_AUTHORIZATION_REFUSED", result["blocking_reasons"])

    def test_wrong_scope_authorization_refused(self):
        result = evaluate_proposal(good_proposal(
            authorization=AuthorizationRecord(
                authorized_by="operator-sebastian",
                proposal_id="imp-9999",
                scope="other", expires="2026-12-31")))
        self.assertIn(
            "WRONG_PROPOSAL_SCOPE", result["blocking_reasons"])

    def test_proposal_alone_never_ready(self):
        """REQUEST != AUTHORIZATION: ohne Autorisierung keine Tauglichkeit."""
        self.assertEqual(
            evaluate_proposal(
                good_proposal(authorization=None))["verdict"],
            VERDICT_NOT_AUTHORIZED)


class GatesTestCase(unittest.TestCase):
    def test_missing_tests_block(self):
        result = evaluate_proposal(good_proposal(tests=None))
        self.assertEqual(result["verdict"], VERDICT_BLOCKED)
        self.assertIn("TESTS_MISSING", result["blocking_reasons"])

    def test_failed_regression_blocks(self):
        result = evaluate_proposal(
            good_proposal(tests=TestRecord(False, EV)))
        self.assertIn(
            "REGRESSION_NOT_PROVEN", result["blocking_reasons"])
        self.assertEqual(result["verdict"], VERDICT_BLOCKED)

    def test_test_evidence_without_source_blocks(self):
        bad_ev = EvidenceBundle(
            source=" ", method="suite",
            period_start="2026-11-21T10:00:00Z",
            period_end="2026-11-21T11:00:00Z")
        result = evaluate_proposal(
            good_proposal(tests=TestRecord(True, bad_ev)))
        self.assertFalse(result["tests_ok"])

    def test_single_stage_rollout_blocks(self):
        result = evaluate_proposal(good_proposal(rollout_stages=(
            RolloutStage("full", 1.0),)))
        self.assertIn("MIN_2_STAGES", result["blocking_reasons"])

    def test_first_stage_too_big_blocks(self):
        result = evaluate_proposal(good_proposal(rollout_stages=(
            RolloutStage("canary-50pct", 0.5),
            RolloutStage("full", 1.0))))
        self.assertIn(
            "FIRST_STAGE_MAX_10_PERCENT", result["blocking_reasons"])

    def test_descending_stages_block(self):
        result = evaluate_proposal(good_proposal(rollout_stages=(
            RolloutStage("a", 0.1),
            RolloutStage("b", 0.05),
            RolloutStage("c", 1.0))))
        self.assertIn("STAGES_MUST_ASCEND", result["blocking_reasons"])

    def test_sum_above_100_percent_blocks(self):
        result = evaluate_proposal(good_proposal(rollout_stages=(
            RolloutStage("a", 0.1),
            RolloutStage("b", 0.4),
            RolloutStage("c", 0.4),
            RolloutStage("d", 0.4))))
        self.assertIn(
            "SUM_MAX_100_PERCENT", result["blocking_reasons"])

    def test_irreversible_always_blocks(self):
        result = evaluate_proposal(good_proposal(irreversible=True))
        self.assertIn("IRREVERSIBLE_BLOCKED", result["blocking_reasons"])
        self.assertEqual(result["verdict"], VERDICT_BLOCKED)

    def test_untested_rollback_blocks(self):
        result = evaluate_proposal(good_proposal(rollback_tested=False))
        self.assertIn("ROLLBACK_NOT_TESTED", result["blocking_reasons"])

    def test_missing_rollback_plan_raises(self):
        """Leerer Plan ist strukturell ungueltig, fail-closed als Fehler."""
        with self.assertRaises(ImprovementCycleError):
            evaluate_proposal(good_proposal(rollback_plan=""))


class CriticalServiceTestCase(unittest.TestCase):
    def test_critical_service_without_evidence_raises(self):
        with self.assertRaises(ImprovementCycleError):
            evaluate_proposal(
                good_proposal(is_critical_service=True,
                              critical_service_key="energy"))

    def test_unknown_critical_key_rejected(self):
        with self.assertRaises(ImprovementCycleError):
            evaluate_proposal(
                good_proposal(is_critical_service=True,
                              critical_service_key="cozy_commerce",
                              continuity_evidence=EV))

    def test_critical_with_evidence_ready(self):
        result = evaluate_proposal(
            good_proposal(is_critical_service=True,
                          critical_service_key="energy",
                          continuity_evidence=EV))
        self.assertEqual(result["verdict"], VERDICT_READY)
        self.assertTrue(result["continuity_ok"])

    def test_critical_bad_evidence_undecidable(self):
        bad_ev = EvidenceBundle(
            source="checklist", method="",
            period_start="2026-11-21T10:00:00Z",
            period_end="2026-11-21T11:00:00Z")
        result = evaluate_proposal(
            good_proposal(is_critical_service=True,
                          critical_service_key="healthcare",
                          continuity_evidence=bad_ev))
        self.assertEqual(result["verdict"], VERDICT_UNDECIDABLE)
        self.assertFalse(result["continuity_ok"])


class ReboundBridgeTestCase(unittest.TestCase):
    def test_zielkonflikt_blocks(self):
        result = evaluate_proposal(
            good_proposal(rebound_verdict="ZIELKONFLIKT_BELEGT"))
        self.assertEqual(result["verdict"], VERDICT_ZIELKONFLIKT_BLOCK)

    def test_undecidable_rebound_undecidable(self):
        result = evaluate_proposal(
            good_proposal(rebound_verdict="NICHT_ENTSCHEIDBAR"))
        self.assertEqual(result["verdict"], VERDICT_UNDECIDABLE)
        self.assertIn("REBOUND_UNDECIDABLE", result["undecidable_reasons"])

    def test_verttraeglich_ok(self):
        result = evaluate_proposal(
            good_proposal(rebound_verdict="VERTRAEGLICH_BELEGT"))
        self.assertEqual(result["verdict"], VERDICT_READY)


class OutcomeTestCase(unittest.TestCase):
    def test_pending_without_outcome(self):
        result = outcome_status(None)
        self.assertEqual(result["status"], POST_CHANGE_PENDING)
        self.assertIn("POST_CHANGE_EVIDENCE_MISSING", result["problems"])

    def test_improved_with_evidence(self):
        result = outcome_status(OutcomeReport(
            achieved_value=3.0, target_value=5.0,
            unit="ms", evidence=EV))
        self.assertEqual(result["status"], OUTCOME_VERBESSERT)

    def test_worse_with_evidence_not_improved(self):
        result = outcome_status(OutcomeReport(
            achieved_value=9.0, target_value=5.0,
            unit="ms", evidence=EV))
        self.assertEqual(result["status"], OUTCOME_NICHT_VERBESSERT)

    def test_bad_evidence_keeps_pending(self):
        bad_ev = EvidenceBundle(
            source="trust me", method="looked once",
            period_start="2026-11-21T12:00:00Z",
            period_end="2026-11-21T11:00:00Z")
        result = outcome_status(OutcomeReport(
            achieved_value=3.0, target_value=5.0,
            unit="ms", evidence=bad_ev))
        self.assertEqual(result["status"], POST_CHANGE_PENDING)

    def test_invalid_outcome_type_raises(self):
        with self.assertRaises(ImprovementCycleError):
            outcome_status("improved")

    def test_cycle_report_contains_both(self):
        report = cycle_report(
            good_proposal(),
            OutcomeReport(achieved_value=4.0, target_value=5.0,
                          unit="ms", evidence=EV))
        self.assertEqual(report["verdict"], VERDICT_READY)
        self.assertEqual(report["outcome"]["status"], OUTCOME_VERBESSERT)


if __name__ == "__main__":
    unittest.main()
