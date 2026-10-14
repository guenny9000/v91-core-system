"""Pure, side-effect-free MAX BEST proposal planner.

This module analyzes caller-supplied inventory only. It does not inspect hosts,
call APIs, execute commands, change permissions, or claim external deployment.
"""
from __future__ import annotations

from typing import Any


def build_plan(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    """Return conservative, evidence-labelled proposals for supplied targets."""
    if not isinstance(inventory, list):
        raise TypeError("inventory must be a list")

    proposals: list[dict[str, Any]] = []
    for index, item in enumerate(inventory):
        if not isinstance(item, dict):
            raise TypeError(f"inventory[{index}] must be an object")

        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            name = f"target-{index}"

        evidence = item.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(x, str) for x in evidence):
            evidence = []

        authorized = item.get("authorized") is True
        reversible = item.get("reversible") is True
        baseline = item.get("baseline")
        measured_benefit = item.get("measured_benefit")

        if not evidence:
            action = "collect_evidence"
            reason = "No evidence supplied; keep state UNKNOWN and inspect read-only."
            priority = 100
        elif not authorized:
            action = "recommend_only"
            reason = "Evidence exists, but authorization is not established."
            priority = 90
        elif not reversible:
            action = "request_independent_review"
            reason = "Change is not marked reversible; do not execute automatically."
            priority = 80
        elif baseline is None or measured_benefit is None:
            action = "measure_baseline"
            reason = "A comparable baseline and measured benefit are required."
            priority = 70
        else:
            action = "isolated_test"
            reason = "Evidence, authorization, reversibility, and measurements are supplied; test in isolation before any deployment."
            priority = 60

        proposals.append({
            "target": name,
            "status": "PROPOSAL_ONLY",
            "action": action,
            "priority": priority,
            "reason": reason,
            "evidence": evidence,
            "execution_performed": False,
        })

    proposals.sort(key=lambda row: (-row["priority"], row["target"]))
    return {
        "planner": "MAX_BEST_RAGNAROK",
        "mode": "read_only_proposal",
        "status": "DOCUMENTED_INPUT_ONLY",
        "external_systems_inspected": False,
        "actions_executed": False,
        "proposals": proposals,
    }
