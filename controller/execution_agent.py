#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Execution Agent (VIBE-LXXXVIII): first plan-only orchestration increment.

This module validates a caller-supplied task through an injected existing
validator, checks that its action matches a predeclared grant, and delegates
the authorization decision to quorum_execution_gate. It never executes,
queues, persists, contacts a network, starts a process, or changes files.

READY_FOR_EXECUTOR means only that the existing gate returned
EXECUTION_PERMITTED. It is NOT a worker handoff or execution record.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from controller.agent_consensus import Decision
from controller.quorum_execution_gate import (
    ActionGrant,
    GateRequest,
    VERDICT_BLOCKED,
    VERDICT_EXECUTION_PERMITTED,
    VERDICT_HUMAN_APPROVAL_REQUIRED,
    gate_execution,
)

STATUS_BLOCKED = "BLOCKED"
STATUS_HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
STATUS_READY_FOR_EXECUTOR = "READY_FOR_EXECUTOR"

HONEST_LIMITS = (
    "PLAN_ONLY: this module never executes or hands off a task.",
    "READY_FOR_EXECUTOR is a gate result, not an execution receipt.",
    "REQUEST != AUTHORIZATION; quorum cannot expand predeclared grants.",
    "UNKNOWN != PASS; receiver rechecks must be exactly True.",
    "NO_DUPLICATE_SYSTEMS: task validation is delegated to an injected existing validator.",
)


@dataclass(frozen=True)
class ExecutionCandidate:
    """One explicit local task candidate and its current authorization context."""

    task_id: str
    task: Mapping[str, Any]
    grant: ActionGrant
    decision: Decision
    capability_ok: bool
    policy_ok: bool
    state_ok: bool
    revoked: bool = False


TaskValidator = Callable[[Mapping[str, Any], str], tuple[str, str, str]]


def _blocked(task_id: str, reason: str, action: str = "") -> dict[str, Any]:
    return {
        "schema": "v91.execution_agent.plan.v1",
        "task_id": task_id if isinstance(task_id, str) else "",
        "action": action,
        "status": STATUS_BLOCKED,
        "gate_verdict": VERDICT_BLOCKED,
        "reasons": (reason,),
        "executed": False,
        "worker_handoff": False,
        "honest_limits": HONEST_LIMITS,
    }


def prepare_execution(
    candidate: ExecutionCandidate,
    *,
    validator: TaskValidator,
    predeclared: Sequence[ActionGrant],
) -> dict[str, Any]:
    """Return a fail-closed plan; deliberately does not call an executor.

    The validator should be the existing worker task-envelope validator.
    The callback boundary prevents this coordinator from reimplementing the
    worker's action allowlist or task schema.
    """
    if not isinstance(candidate, ExecutionCandidate):
        return _blocked("", "candidate must be an ExecutionCandidate")
    if not isinstance(candidate.task_id, str) or not candidate.task_id.strip():
        return _blocked("", "task_id missing")
    if not isinstance(candidate.task, Mapping):
        return _blocked(candidate.task_id, "task must be a mapping")
    if not callable(validator):
        return _blocked(candidate.task_id, "existing task validator unavailable")
    if not isinstance(candidate.grant, ActionGrant):
        return _blocked(candidate.task_id, "predeclared ActionGrant missing")
    if not isinstance(predeclared, (list, tuple)):
        return _blocked(candidate.task_id, "predeclared grants must be a list or tuple")
    if not isinstance(candidate.decision, Decision):
        return _blocked(candidate.task_id, "decision missing or invalid")

    try:
        validated = validator(candidate.task, candidate.task_id)
    except Exception as exc:
        return _blocked(
            candidate.task_id,
            "task validation failed: " + type(exc).__name__,
        )

    if (not isinstance(validated, tuple) or len(validated) != 3
            or any(not isinstance(value, str) or not value.strip()
                   for value in validated)):
        return _blocked(candidate.task_id, "validator returned an invalid task envelope")

    action, purpose, expected_effect = (value.strip() for value in validated)
    if candidate.grant.action_id != action:
        return _blocked(
            candidate.task_id,
            "task action does not match the predeclared grant",
            action,
        )

    try:
        gate_result = gate_execution(
            GateRequest(
                decision=candidate.decision,
                grant=candidate.grant,
                capability_ok=candidate.capability_ok,
                policy_ok=candidate.policy_ok,
                state_ok=candidate.state_ok,
                revoked=candidate.revoked,
            ),
            predeclared,
        )
    except Exception as exc:
        return _blocked(
            candidate.task_id,
            "execution gate failed closed: " + type(exc).__name__,
            action,
        )

    if gate_result.verdict == VERDICT_EXECUTION_PERMITTED:
        status = STATUS_READY_FOR_EXECUTOR
    elif gate_result.verdict == VERDICT_HUMAN_APPROVAL_REQUIRED:
        status = STATUS_HUMAN_APPROVAL_REQUIRED
    else:
        status = STATUS_BLOCKED

    return {
        "schema": "v91.execution_agent.plan.v1",
        "task_id": candidate.task_id,
        "action": action,
        "purpose": purpose,
        "expected_effect": expected_effect,
        "status": status,
        "gate_verdict": gate_result.verdict,
        "reasons": tuple(gate_result.reasons),
        "executed": False,
        "worker_handoff": False,
        "honest_limits": HONEST_LIMITS,
    }
