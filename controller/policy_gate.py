"""V91 policy gate: classify requests before any controller action.

This module does not execute commands, launch containers, or modify external systems.
It is a project policy gate for closed, non-operational tests—not a legal determination.
Unknown or insufficiently specified requests fail closed.
"""

from dataclasses import dataclass


BLOCKED_CATEGORIES = frozenset({
    "weapon_design",
    "weapon_testing",
    "lethal_targeting",
    "weapon_effect_optimization",
    "harmful_operation",
})

SANDBOX_ONLY_CATEGORIES = frozenset({
    "disarmament_analysis",
    "civilian_protection",
    "environmental_impact_audit",
    "defensive_security_audit",
})


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reason: str


def evaluate_request(category: str, *, scope_is_closed: bool = False,
                     evidence_documented: bool = False) -> PolicyDecision:
    """Return BLOCK, HOLD, or SANDBOX_ONLY; never authorize live execution."""
    if not isinstance(category, str) or not category.strip():
        return PolicyDecision("HOLD", "NO_DATA_AVAILABLE: missing request category")

    normalized = category.strip().lower()

    if normalized in BLOCKED_CATEGORIES:
        return PolicyDecision(
            "BLOCK",
            "V91_POLICY: weapons development/testing or lethal harm is disallowed",
        )

    if normalized not in SANDBOX_ONLY_CATEGORIES:
        return PolicyDecision(
            "HOLD",
            "PENDING_WITNESS: category is unknown; require human review and evidence",
        )

    if not evidence_documented:
        return PolicyDecision(
            "HOLD",
            "PENDING_WITNESS: documented evidence is required before analysis",
        )

    if not scope_is_closed:
        return PolicyDecision(
            "HOLD",
            "FAIL_CLOSED: closed, isolated test scope has not been confirmed",
        )

    return PolicyDecision(
        "SANDBOX_ONLY",
        "POLICY_PASS: documented, non-operational analysis in a closed sandbox only",
    )
