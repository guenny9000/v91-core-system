"""Conservative, deterministic V91 use-domain policy classification.

This module classifies an explicitly supplied use-domain label. It does NOT
inspect or understand task content, verify who supplied the label, authorize
execution, terminate processes, or affect third-party systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UseDomain(str, Enum):
    CIVILIAN_SUSTAINABILITY = "CIVILIAN_SUSTAINABILITY"
    HUMANITARIAN = "HUMANITARIAN"
    EDUCATION = "EDUCATION"
    GENERAL_RESEARCH = "GENERAL_RESEARCH"
    CRITICAL_SUPPLY_PROTECTION = "CRITICAL_SUPPLY_PROTECTION"
    WEAPONS_DEVELOPMENT = "WEAPONS_DEVELOPMENT"
    TARGETING = "TARGETING"
    COMBAT_OPERATIONS = "COMBAT_OPERATIONS"
    MILITARY_SURVEILLANCE = "MILITARY_SURVEILLANCE"
    ARMS_PRODUCTION = "ARMS_PRODUCTION"
    UNKNOWN = "UNKNOWN"


class PolicyDecision(str, Enum):
    ALLOW_FOR_REVIEWED_WORKFLOW = "ALLOW_FOR_REVIEWED_WORKFLOW"
    BLOCK_RESTRICTED_DOMAIN = "BLOCK_RESTRICTED_DOMAIN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class UsePolicyResult:
    domain: str
    decision: PolicyDecision
    execution_authorized: bool
    reason: str


_ALLOWED_DOMAINS = {
    UseDomain.CIVILIAN_SUSTAINABILITY.value,
    UseDomain.HUMANITARIAN.value,
    UseDomain.EDUCATION.value,
    UseDomain.GENERAL_RESEARCH.value,
    UseDomain.CRITICAL_SUPPLY_PROTECTION.value,
}
_RESTRICTED_DOMAINS = {
    UseDomain.WEAPONS_DEVELOPMENT.value,
    UseDomain.TARGETING.value,
    UseDomain.COMBAT_OPERATIONS.value,
    UseDomain.MILITARY_SURVEILLANCE.value,
    UseDomain.ARMS_PRODUCTION.value,
}


def evaluate_use_domain(value: object) -> UsePolicyResult:
    """Return a policy classification; never authorize or execute a task.

    Only exact, enumerated string values are accepted. Missing, malformed,
    or unrecognized values require review. Restricted domains are blocked.
    An allowed classification is not proof that the task is benign: the
    caller must separately validate provenance, scope, and authorization.
    """
    if not isinstance(value, str):
        return UsePolicyResult(
            domain=UseDomain.UNKNOWN.value,
            decision=PolicyDecision.REVIEW_REQUIRED,
            execution_authorized=False,
            reason="Use domain is missing or not a string; fail closed.",
        )

    domain = value
    if domain in _RESTRICTED_DOMAINS:
        return UsePolicyResult(
            domain=domain,
            decision=PolicyDecision.BLOCK_RESTRICTED_DOMAIN,
            execution_authorized=False,
            reason="The declared use domain is restricted by V91 policy.",
        )

    if domain in _ALLOWED_DOMAINS:
        return UsePolicyResult(
            domain=domain,
            decision=PolicyDecision.ALLOW_FOR_REVIEWED_WORKFLOW,
            execution_authorized=False,
            reason=(
                "Domain is eligible for a separately authorized civilian workflow; "
                "this classification does not authorize execution or prove task intent."
            ),
        )

    return UsePolicyResult(
        domain=UseDomain.UNKNOWN.value,
        decision=PolicyDecision.REVIEW_REQUIRED,
        execution_authorized=False,
        reason="Unrecognized use domain; UNKNOWN is not PASS.",
    )
