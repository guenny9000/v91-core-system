import pytest

from controller.use_policy import PolicyDecision, evaluate_use_domain


@pytest.mark.parametrize("domain", [
    "WEAPONS_DEVELOPMENT",
    "TARGETING",
    "COMBAT_OPERATIONS",
    "MILITARY_SURVEILLANCE",
    "ARMS_PRODUCTION",
])
def test_restricted_domains_are_blocked(domain):
    result = evaluate_use_domain(domain)
    assert result.decision is PolicyDecision.BLOCK_RESTRICTED_DOMAIN
    assert result.execution_authorized is False


@pytest.mark.parametrize("domain", [
    "CIVILIAN_SUSTAINABILITY",
    "HUMANITARIAN",
    "EDUCATION",
    "GENERAL_RESEARCH",
    "CRITICAL_SUPPLY_PROTECTION",
])
def test_civilian_domains_are_only_eligible_for_review(domain):
    result = evaluate_use_domain(domain)
    assert result.decision is PolicyDecision.ALLOW_FOR_REVIEWED_WORKFLOW
    # Classification is not execution authority.
    assert result.execution_authorized is False


@pytest.mark.parametrize("value", [None, "", "UNKNOWN", "military", "TARGETING ", 7, True, {}])
def test_missing_or_unrecognized_domain_requires_review(value):
    result = evaluate_use_domain(value)
    assert result.decision is PolicyDecision.REVIEW_REQUIRED
    assert result.domain == "UNKNOWN"
    assert result.execution_authorized is False
