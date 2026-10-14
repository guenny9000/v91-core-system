"""Reality-First shutdown policy planner.

This module does NOT shut down real systems. It records bounded proposals for
review. Global or irreversible shutdowns are never executed by this module.
"""
from __future__ import annotations

from typing import Any

AREAS = (
    "luxury_overhead",
    "war_related_activity",
    "overproduction",
    "redundant_waiting",
)


def plan_cleanup(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    """Create evidence-labelled, non-executing cleanup proposals.

    Each inventory item must identify a concrete target and its evidence.
    No evidence means UNKNOWN; a policy goal is not proof that a system exists
    or has been changed. Authorization never substitutes for evidence.
    """
    if not isinstance(inventory, list):
        raise TypeError("inventory must be a list")

    proposals: list[dict[str, Any]] = []
    for index, item in enumerate(inventory):
        if not isinstance(item, dict):
            raise TypeError(f"inventory[{index}] must be an object")

        target = item.get("target")
        area = item.get("area")
        evidence = item.get("evidence")
        if not isinstance(target, str) or not target.strip():
            target = f"target-{index}"
        if area not in AREAS:
            area = "unspecified"
        if not isinstance(evidence, list) or any(not isinstance(x, str) for x in evidence):
            evidence = []

        authorized = item.get("authorized") is True
        reversible = item.get("reversible") is True
        baseline = item.get("baseline")
        measured_impact = item.get("measured_impact")

        if not evidence:
            action = "collect_read_only_evidence"
            status = "UNKNOWN"
            reason = "No target evidence supplied; no shutdown or cleanup is claimed."
        elif not authorized:
            action = "recommend_for_human_review"
            status = "DOCUMENTED"
            reason = "Evidence is supplied, but authorization is not established."
        elif not reversible:
            action = "request_independent_review"
            status = "PENDING_WITNESS"
            reason = "Irreversible or non-reversible changes are not auto-executed."
        elif baseline is None or measured_impact is None:
            action = "measure_baseline_and_impact"
            status = "DOCUMENTED"
            reason = "Comparable baseline and measured impact are required."
        else:
            action = "propose_isolated_test"
            status = "PROPOSAL_ONLY"
            reason = "Inputs are present; isolated testing and independent review remain required."

        proposals.append({
            "target": target,
            "area": area,
            "status": status,
            "action": action,
            "reason": reason,
            "evidence": evidence,
            "execution_performed": False,
        })

    return {
        "protocol": "V91_MAX_BEST_REALITY_FIRST_CLEANUP",
        "mode": "read_only_proposal",
        "status": "PROPOSAL_ONLY",
        "global_shutdown_performed": False,
        "external_systems_inspected": False,
        "real_world_changes_performed": False,
        "proposals": proposals,
        "limitations": [
            "No external system, device, agent, or service was inspected.",
            "No war-related, luxury, production, or waiting process was stopped.",
            "This report is not a WORM ledger or a cryptographic verification.",
        ],
    }
