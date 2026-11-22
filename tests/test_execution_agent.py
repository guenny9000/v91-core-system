#!/usr/bin/env python3
"""Tests for the plan-only V91 execution-agent coordinator."""
from __future__ import annotations

import unittest

from controller.agent_consensus import Decision
from controller.execution_agent import (
    ExecutionCandidate,
    STATUS_BLOCKED,
    STATUS_HUMAN_APPROVAL_REQUIRED,
    STATUS_READY_FOR_EXECUTOR,
    prepare_execution,
)
from controller.quorum_execution_gate import ActionGrant


TASK = {
    "task_id": "task-001",
    "action": "sha256_file",
    "purpose": "verify a local workspace artifact",
    "expected_effect": "produce a digest without changing the artifact",
}
GRANT = ActionGrant(action_id="sha256_file", category="inventory_read")


def validator(task, task_id):
    if task.get("task_id") != task_id:
        raise ValueError("task ID mismatch")
    action = task.get("action")
    if action != "sha256_file":
        raise ValueError("unsupported action")
    return action, task["purpose"], task["expected_effect"]


def candidate(**overrides):
    values = {
        "task_id": "task-001",
        "task": TASK,
        "grant": GRANT,
        "decision": Decision.ACCEPT,
        "capability_ok": True,
        "policy_ok": True,
        "state_ok": True,
        "revoked": False,
    }
    values.update(overrides)
    return ExecutionCandidate(**values)


class ExecutionAgentTests(unittest.TestCase):
    def test_valid_local_grant_is_ready_but_not_executed_or_handed_off(self):
        plan = prepare_execution(
            candidate(), validator=validator, predeclared=(GRANT,))
        self.assertEqual(plan["status"], STATUS_READY_FOR_EXECUTOR)
        self.assertEqual(plan["gate_verdict"], "EXECUTION_PERMITTED")
        self.assertFalse(plan["executed"])
        self.assertFalse(plan["worker_handoff"])
        self.assertIn("PLAN_ONLY", " ".join(plan["honest_limits"]))

    def test_missing_predeclared_grant_blocks(self):
        plan = prepare_execution(candidate(), validator=validator, predeclared=())
        self.assertEqual(plan["status"], STATUS_BLOCKED)
        self.assertFalse(plan["executed"])

    def test_action_must_match_grant(self):
        wrong = ActionGrant(action_id="verify_sha256", category="inventory_read")
        plan = prepare_execution(
            candidate(grant=wrong), validator=validator, predeclared=(wrong,))
        self.assertEqual(plan["status"], STATUS_BLOCKED)
        self.assertIn("does not match", plan["reasons"][0])

    def test_no_quorum_blocks(self):
        plan = prepare_execution(
            candidate(decision=Decision.NO_QUORUM),
            validator=validator, predeclared=(GRANT,))
        self.assertEqual(plan["status"], STATUS_BLOCKED)

    def test_receiver_unknown_or_false_blocks(self):
        for field in ("capability_ok", "policy_ok", "state_ok"):
            with self.subTest(field=field):
                plan = prepare_execution(
                    candidate(**{field: None}),
                    validator=validator, predeclared=(GRANT,))
                self.assertEqual(plan["status"], STATUS_BLOCKED)

    def test_revoked_grant_blocks(self):
        plan = prepare_execution(
            candidate(revoked=True), validator=validator, predeclared=(GRANT,))
        self.assertEqual(plan["status"], STATUS_BLOCKED)

    def test_external_side_effect_requires_human_approval(self):
        grant = ActionGrant(
            action_id="sha256_file", category="external_side_effect")
        plan = prepare_execution(
            candidate(grant=grant), validator=validator, predeclared=(grant,))
        self.assertEqual(plan["status"], STATUS_HUMAN_APPROVAL_REQUIRED)
        self.assertFalse(plan["executed"])

    def test_validator_exception_fails_closed_without_leaking_details(self):
        def broken(_task, _task_id):
            raise RuntimeError("private detail")
        plan = prepare_execution(
            candidate(), validator=broken, predeclared=(GRANT,))
        self.assertEqual(plan["status"], STATUS_BLOCKED)
        self.assertIn("RuntimeError", plan["reasons"][0])
        self.assertNotIn("private detail", plan["reasons"][0])

    def test_invalid_validator_return_fails_closed(self):
        plan = prepare_execution(
            candidate(), validator=lambda _task, _task_id: ("sha256_file",),
            predeclared=(GRANT,))
        self.assertEqual(plan["status"], STATUS_BLOCKED)

    def test_unsupported_action_is_rejected_by_injected_worker_validator(self):
        task = dict(TASK, action="shell")
        def strict_validator(payload, task_id):
            if payload.get("action") != "sha256_file":
                raise ValueError("unsupported")
            return validator(payload, task_id)
        plan = prepare_execution(
            candidate(task=task), validator=strict_validator,
            predeclared=(GRANT,))
        self.assertEqual(plan["status"], STATUS_BLOCKED)

    def test_missing_validator_blocks(self):
        plan = prepare_execution(candidate(), validator=None, predeclared=(GRANT,))
        self.assertEqual(plan["status"], STATUS_BLOCKED)

    def test_wrong_candidate_type_blocks(self):
        plan = prepare_execution({}, validator=validator, predeclared=(GRANT,))
        self.assertEqual(plan["status"], STATUS_BLOCKED)


if __name__ == "__main__":
    unittest.main()
