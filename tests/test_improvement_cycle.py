#!/usr/bin/env python3
"""Tests: controller/improvement_cycle.py (MAX-BEST, VIBE-XXXIII).

Fail-closed, UNKNOWN nie PASS, keine Erfolgsquoten.
Alle Beispiele sind neutral-synthetisch.
"""
from __future__ import annotations

import pytest

from controller.impact_area_registry import EvidenceBundle
from controller.improvement_cycle import (
    ALLOWED_VERDICTS,
    HONEST_LIMITS,
    MAX_AFFECTED_NODES,
    VERDICT_APPROVED_FOR_BOUNDED_ROLLOUT,
    VERDICT_BLOCKED,
    VERDICT_ROLLBACK_RECOMMENDED,
    VERDICT_ROLLOUT_DONE_EVIDENCED,
    ImprovementCycleError,
    ImprovementProposal,
    RolloutPlan,
    evaluate_proposal,
    record_post_change,
)


def _evidence(reference="vorschlag-1"):
    return EvidenceBundle(
        source="quelle-i",
        method="verfahren-i",
        period_start="2026-11-01T00:00:00Z",
        period_end="2026-11-21T00:00:00Z",
        reference=reference,
    )


def _rollout(**kwargs):
    defaults = dict(affected_nodes=3, observation_period_hours=48,
                    rollback_target="version-beispiel-1")
    defaults.update(kwargs)
    return RolloutPlan(**defaults)


def _proposal(**kwargs):
    defaults = dict(
        proposal_id="vorschlag-1",
        description="Synthetisches Beispiel: Konfigurationsentlastung",
        owner="team-b",
        human_authorized=True,
        authorization_reference="freigabe-4711",
        tests_green=True,
        test_evidence=_evidence(),
        rollout=_rollout(),
        post_change_check="Fehlerquote im Beobachtungszeitraum messen",
    )
    defaults.update(kwargs)
    return ImprovementProposal(**defaults)


# ------------------------------------------------------------------ Guards
def test_non_proposal_raises():
    with pytest.raises(ImprovementCycleError):
        evaluate_proposal("vorschlag")


def test_empty_proposal_id_blocks():
    r = evaluate_proposal(_proposal(proposal_id=" "))
    assert r["verdict"] == VERDICT_BLOCKED
    assert any("proposal_id" in p for p in r["problems"])


def test_missing_description_blocks():
    r = evaluate_proposal(_proposal(description=" "))
    assert any("description missing" in p for p in r["problems"])


def test_missing_owner_blocks():
    r = evaluate_proposal(_proposal(owner=" "))
    assert any("owner missing" in p for p in r["problems"])


# ------------------------------------------------------------------ Tor 1
def test_complete_proposal_is_approved():
    r = evaluate_proposal(_proposal())
    assert r["verdict"] == VERDICT_APPROVED_FOR_BOUNDED_ROLLOUT
    assert r["problems"] == ()


def test_no_authorization_blocks():
    r = evaluate_proposal(_proposal(human_authorized=False))
    assert r["verdict"] == VERDICT_BLOCKED
    assert "human authorization missing (REQUEST != AUTHORIZATION)" in r["problems"]


def test_authorization_without_reference_blocks():
    r = evaluate_proposal(_proposal(authorization_reference=" "))
    assert any("authorization reference missing" in p for p in r["problems"])


def test_tests_claimed_but_not_evidenced_blocks():
    r = evaluate_proposal(_proposal(test_evidence=None))
    assert any("test evidence bundle missing" in p for p in r["problems"])


def test_flawed_test_evidence_blocks():
    r = evaluate_proposal(_proposal(
        test_evidence=_evidence(reference=" ").__class__(
            source="q", method=" ",
            period_start="2026-11-01T00:00:00Z",
            period_end="2026-11-02T00:00:00Z", reference="r")))
    assert any("test evidence: method missing" in p for p in r["problems"])


def test_unbounded_rollout_blocks():
    r = evaluate_proposal(_proposal(
        rollout=_rollout(affected_nodes=MAX_AFFECTED_NODES + 1)))
    assert r["verdict"] == VERDICT_BLOCKED
    assert any("rollout not bounded" in p for p in r["problems"])


def test_max_bounded_rollout_is_still_approved():
    r = evaluate_proposal(_proposal(
        rollout=_rollout(affected_nodes=MAX_AFFECTED_NODES)))
    assert r["verdict"] == VERDICT_APPROVED_FOR_BOUNDED_ROLLOUT


def test_zero_observation_period_blocks():
    r = evaluate_proposal(_proposal(
        rollout=_rollout(observation_period_hours=0)))
    assert any("observation_period_hours" in p for p in r["problems"])


def test_missing_rollback_target_blocks():
    r = evaluate_proposal(_proposal(rollout=_rollout(rollback_target=" ")))
    assert any("rollback target missing" in p for p in r["problems"])


def test_missing_post_change_check_blocks():
    r = evaluate_proposal(_proposal(post_change_check=" "))
    assert any("post-change check not defined" in p for p in r["problems"])


def test_non_rollout_plan_blocks():
    r = evaluate_proposal(_proposal(rollout="plan"))
    assert any("rollout plan missing or malformed" in p for p in r["problems"])


# ------------------------------------------------------------------ Tor 2
def test_post_change_without_approval_blocks():
    r = record_post_change(_proposal(human_authorized=False), _evidence(), False)
    assert r["verdict"] == VERDICT_BLOCKED
    assert any("approval gate not passed" in p for p in r["problems"])


def test_post_change_without_valid_reference_blocks():
    r = record_post_change(_proposal(), _evidence(reference="fremd"), False)
    assert r["verdict"] == VERDICT_BLOCKED
    assert any("FREMDEVIDENZ != NACHWEIS" in p for p in r["problems"])


def test_post_change_invalid_evidence_blocks():
    bad = EvidenceBundle(source=" ", method="m",
                        period_start="2026-11-01T00:00:00Z",
                        period_end="2026-11-21T00:00:00Z",
                        reference="vorschlag-1")
    r = record_post_change(_proposal(), bad, False)
    assert any("post-change evidence: source missing" in p for p in r["problems"])


def test_non_boolean_regression_raises():
    with pytest.raises(ImprovementCycleError):
        record_post_change(_proposal(), _evidence(), "vielleicht")


def test_post_change_clean_is_evidenced():
    r = record_post_change(_proposal(), _evidence(), False)
    assert r["verdict"] == VERDICT_ROLLOUT_DONE_EVIDENCED
    assert r["regression_found"] is False
    assert r["post_evidence_source"] == "quelle-i"


def test_regression_recommends_rollback():
    r = record_post_change(_proposal(), _evidence(), True)
    assert r["verdict"] == VERDICT_ROLLBACK_RECOMMENDED
    assert r["rollback_target"] == "version-beispiel-1"
    assert r["regression_found"] is True


# ------------------------------------------------------------------ Inhalt
def test_verdict_universe_is_closed():
    assert ALLOWED_VERDICTS == (VERDICT_APPROVED_FOR_BOUNDED_ROLLOUT,
                                VERDICT_BLOCKED,
                                VERDICT_ROLLOUT_DONE_EVIDENCED,
                                VERDICT_ROLLBACK_RECOMMENDED)


def test_report_pins_honest_limits():
    blob = str(evaluate_proposal(_proposal()))
    assert "VORSCHLAG != VERBESSERUNG" in blob
    assert "APPROVED != AUSGEFUEHRT" in blob
    assert "ROLLOUT != WIRKUNG" in blob
    assert "REGRESSION > Theorie" in blob


def test_report_never_contains_percent_or_quota():
    blob = str(record_post_change(_proposal(), _evidence(), False))
    for forbidden in ("%", "Erfolgsquote", "zielerreichung", "progress"):
        assert forbidden not in blob


def test_deterministic_evaluation():
    assert evaluate_proposal(_proposal()) == evaluate_proposal(_proposal())
    assert record_post_change(_proposal(), _evidence(), False) == \
        record_post_change(_proposal(), _evidence(), False)
