#!/usr/bin/env python3
"""Tests: controller/quorum_execution_gate.py (MAX-BEST, VIBE-XXXII).

Fail-closed, UNKNOWN nie PASS, Quorum erweitert nie Berechtigungen.
Alle Beispiele sind neutral-synthetisch.
"""
from __future__ import annotations

import pytest

from controller.agent_consensus import Decision
from controller.quorum_execution_gate import (
    ALL_CATEGORIES,
    ALLOWED_VERDICTS,
    HUMAN_APPROVAL_CATEGORIES,
    HONEST_LIMITS,
    LOW_RISK_CATEGORIES,
    SCOPE_LOCAL,
    VERDICT_BLOCKED,
    VERDICT_EXECUTION_PERMITTED,
    VERDICT_HUMAN_APPROVAL_REQUIRED,
    ActionGrant,
    GateRequest,
    GateResult,
    QuorumExecutionGateError,
    gate_execution,
    validate_grant,
)


def _grant(**kwargs):
    defaults = dict(action_id="action-report-draft", category="report_draft",
                    scope=SCOPE_LOCAL, reversible=True)
    defaults.update(kwargs)
    return ActionGrant(**defaults)


def _request(**kwargs):
    defaults = dict(decision=Decision.ACCEPT, grant=_grant(),
                    capability_ok=True, policy_ok=True, state_ok=True,
                    revoked=False)
    defaults.update(kwargs)
    return GateRequest(**defaults)


def _gate(request, grants=None):
    if grants is None:
        grants = [_grant()]
    return gate_execution(request, grants)


# ------------------------------------------------------------------ Guards
def test_non_request_raises():
    with pytest.raises(QuorumExecutionGateError):
        gate_execution("request", [])


def test_non_sequence_predeclared_raises():
    with pytest.raises(QuorumExecutionGateError):
        _gate(_request(), grants="liste")


def test_non_grant_in_predeclared_raises():
    with pytest.raises(QuorumExecutionGateError):
        _gate(_request(), grants=[_grant(), "eintrag"])


def test_non_grant_validation_raises():
    with pytest.raises(QuorumExecutionGateError):
        validate_grant("grant")


def test_empty_recheck_values_are_boolean_checked():
    r = _gate(_request(capability_ok=None))
    assert r.verdict == VERDICT_BLOCKED
    assert "receiver recheck failed: capability_ok" in r.reasons


# ------------------------------------------------------------------ Quorum
def test_reject_decision_is_blocked():
    r = _gate(_request(decision=Decision.REJECT))
    assert r.verdict == VERDICT_BLOCKED


def test_no_quorum_is_blocked_never_implicit_approval():
    r = _gate(_request(decision=Decision.NO_QUORUM))
    assert r.verdict == VERDICT_BLOCKED
    assert any("not ACCEPT" in reason for reason in r.reasons)


def test_accept_without_predeclared_grant_is_blocked():
    """Kernregel: Quorum kann keine neue Freigabe erzeugen."""
    r = _gate(_request(), grants=[])
    assert r.verdict == VERDICT_BLOCKED
    assert any("not predeclared" in reason for reason in r.reasons)


def test_accept_with_altered_grant_is_blocked():
    other = _grant(action_id="action-nicht-deklariert")
    r = _gate(_request(grant=other), grants=[_grant()])
    assert r.verdict == VERDICT_BLOCKED


def test_revoked_grant_is_blocked():
    r = _gate(_request(revoked=True))
    assert r.verdict == VERDICT_BLOCKED
    assert any("revoked" in reason for reason in r.reasons)


# ------------------------------------------------------------------ Kategorien
def test_low_risk_accept_with_rechecks_is_permitted():
    r = _gate(_request())
    assert r.verdict == VERDICT_EXECUTION_PERMITTED


def test_every_low_risk_category_can_be_permitted():
    for category in LOW_RISK_CATEGORIES:
        grant = _grant(action_id="a-" + category, category=category)
        r = _gate(_request(grant=grant), grants=[grant])
        assert r.verdict == VERDICT_EXECUTION_PERMITTED, category


def test_every_human_approval_category_never_permitted():
    for category in HUMAN_APPROVAL_CATEGORIES:
        grant = _grant(action_id="a-" + category, category=category)
        r = _gate(_request(grant=grant), grants=[grant])
        assert r.verdict == VERDICT_HUMAN_APPROVAL_REQUIRED, category
        assert any("human approval" in reason for reason in r.reasons)


def test_unknown_category_is_blocked():
    r = _gate(_request(grant=_grant(category="infinity")))
    assert r.verdict == VERDICT_BLOCKED
    assert any("unknown category" in reason for reason in r.reasons)


def test_category_universe_is_closed():
    assert ALL_CATEGORIES == frozenset(LOW_RISK_CATEGORIES
                                       + HUMAN_APPROVAL_CATEGORIES)
    assert "credential" in ALL_CATEGORIES
    assert "cuda_launch" not in ALL_CATEGORIES


# ------------------------------------------------------------------ Rechecks
def test_failed_capability_recheck_blocks():
    r = _gate(_request(capability_ok=False))
    assert r.verdict == VERDICT_BLOCKED
    assert "receiver recheck failed: capability_ok" in r.reasons


def test_failed_policy_recheck_blocks():
    r = _gate(_request(policy_ok=False))
    assert r.verdict == VERDICT_BLOCKED
    assert "receiver recheck failed: policy_ok" in r.reasons


def test_failed_state_recheck_blocks():
    r = _gate(_request(state_ok=False))
    assert r.verdict == VERDICT_BLOCKED
    assert "receiver recheck failed: state_ok" in r.reasons


def test_all_rechecks_failed_listed_once():
    r = _gate(_request(capability_ok=False, policy_ok=False, state_ok=False))
    assert r.verdict == VERDICT_BLOCKED
    assert len([x for x in r.reasons if "receiver recheck failed" in x]) == 1


def test_recheck_failures_override_human_approval_path():
    grant = _grant(action_id="a-destructive", category="destructive")
    r = _gate(_request(grant=grant, state_ok=False), grants=[grant])
    # Recheck-Fehler ist ein harter Block, kein Freigabe-Pfad.
    assert r.verdict == VERDICT_BLOCKED


# ------------------------------------------------------------------ Grants
def test_non_local_scope_is_blocked():
    r = _gate(_request(grant=_grant(scope="GLOBAL")))
    assert r.verdict == VERDICT_BLOCKED


def test_irreversible_grant_is_blocked():
    r = _gate(_request(grant=_grant(reversible=False)))
    assert r.verdict == VERDICT_BLOCKED


def test_empty_action_id_is_blocked():
    r = _gate(_request(grant=_grant(action_id=" ")))
    assert r.verdict == VERDICT_BLOCKED
    assert any("action_id missing" in reason for reason in r.reasons)


def test_validate_grant_clean_grant_has_no_problems():
    assert validate_grant(_grant()) == []


# ------------------------------------------------------------------ Inhalt
def test_verdict_universe_is_closed():
    assert ALLOWED_VERDICTS == (VERDICT_EXECUTION_PERMITTED,
                                VERDICT_HUMAN_APPROVAL_REQUIRED,
                                VERDICT_BLOCKED)


def test_result_pins_honest_limits():
    r = _gate(_request())
    blob = str(r)
    assert "GATE != AUSFUEHRUNG" in blob
    assert "FREIGABE != AUSGEFUEHRT" in blob
    assert "QUORUM != GEWISSEN" in blob
    assert "ACCEPT != ERLAUBNIS" in blob


def test_permitted_reason_never_claims_execution():
    r = _gate(_request())
    reasons_blob = " ".join(r.reasons).lower()
    for forbidden in ("ausgefuehrt", "executed", "erfolg"):
        assert forbidden not in reasons_blob


def test_deterministic_gate():
    assert _gate(_request()) == _gate(_request())
