#!/usr/bin/env python3
"""Tests: controller/critical_service_gate.py (VIBE-XXXIV)."""
from __future__ import annotations

import pytest

from controller.impact_area_registry import EvidenceBundle
from controller.critical_service_gate import (
    ContinuityCheck,
    CriticalServiceGateError,
    evaluate_continuity,
    gate_report,
    VERDICT_BLOCKED,
    VERDICT_CONTINUITY_BELEGT,
    VERDICT_UNDECIDABLE,
)


GOOD_EVIDENCE = EvidenceBundle(
    source="continuity runbook run 2026-11-21",
    method="supervised failover drill, Erreichbarkeit kontinuitaet checked",
    period_start="2026-11-21T10:00:00Z",
    period_end="2026-11-21T11:00:00Z",
    reference="csg-runbook-0042",
)


def good_check(**overrides) -> ContinuityCheck:
    params = dict(
        service_key="energy",
        change_description="update ingest worker, keep old as fallback",
        responsible="operator-sebastian",
        method="staged switch with parallel run",
        evidence=GOOD_EVIDENCE,
    )
    params.update(overrides)
    return ContinuityCheck(**params)


# --- Struktur-Guards -------------------------------------------------

def test_wrong_type_raises():
    with pytest.raises(CriticalServiceGateError):
        evaluate_continuity("not-a-check")


def test_empty_report_raises():
    with pytest.raises(CriticalServiceGateError):
        gate_report([])


def test_unknown_service_blocks():
    result = evaluate_continuity(good_check(service_key="cozy_shop"))
    assert result["verdict"] == VERDICT_BLOCKED
    assert any("service_key" in p for p in result["problems"])


def test_nonempty_report_type_guard():
    with pytest.raises(CriticalServiceGateError):
        gate_report("nope")


def test_missing_description_blocks():
    result = evaluate_continuity(good_check(change_description="  "))
    assert result["verdict"] == VERDICT_BLOCKED


def test_missing_responsible_blocks():
    result = evaluate_continuity(good_check(responsible=""))
    assert result["verdict"] == VERDICT_BLOCKED


def test_missing_evidence_blocks():
    result = evaluate_continuity(good_check(evidence=None))
    assert "continuity evidence missing" in result["problems"]
    assert result["verdict"] == VERDICT_BLOCKED


# --- Evidenz-Bewertung -----------------------------------------------

def test_valid_evidence_belegt():
    result = evaluate_continuity(good_check())
    assert result["verdict"] == VERDICT_CONTINUITY_BELEGT
    assert result["problems"] == ()
    assert result["evidence_source"] == GOOD_EVIDENCE.source


def test_empty_reference_blocks_to_undecidable():
    bad = EvidenceBundle(
        source="continuity runbook",
        method="failover drill continuity checked",
        period_start="2026-11-21T10:00:00Z",
        period_end="2026-11-21T11:00:00Z",
        reference="",
    )
    result = evaluate_continuity(good_check(evidence=bad))
    assert result["verdict"] == VERDICT_UNDECIDABLE
    assert any("reference" in p for p in result["problems"])


def test_method_without_continuity_undecidable():
    bad = EvidenceBundle(
        source="runbook",
        method="looked at dashboard once",
        period_start="2026-11-21T10:00:00Z",
        period_end="2026-11-21T11:00:00Z",
        reference="ref-1",
    )
    result = evaluate_continuity(good_check(evidence=bad))
    assert result["verdict"] == VERDICT_UNDECIDABLE
    assert any("continuity" in p for p in result["problems"])


def test_bad_period_undecidable():
    bad = EvidenceBundle(
        source="runbook",
        method="failover drill continuity checked",
        period_start="2026-11-21T12:00:00Z",
        period_end="2026-11-21T11:00:00Z",
        reference="ref-1",
    )
    result = evaluate_continuity(good_check(evidence=bad))
    assert result["verdict"] == VERDICT_UNDECIDABLE


def test_placeholder_reference_refused():
    bad = EvidenceBundle(
        source="runbook",
        method="failover drill continuity checked",
        period_start="2026-11-19T10:00:00Z",
        period_end="2026-11-19T11:00:00Z",
        reference="verkettet",
    )
    result = evaluate_continuity(good_check(evidence=bad))
    assert result["verdict"] == VERDICT_UNDECIDABLE


def test_all_six_critical_services_supported():
    for key in ("emergency", "accessibility", "healthcare", "energy", "transport", "payment"):
        result = evaluate_continuity(good_check(service_key=key))
        assert result["verdict"] == VERDICT_CONTINUITY_BELEGT, key


# --- Sammelbericht ----------------------------------------------------

def test_report_all_belegt():
    result = gate_report([good_check(), good_check(service_key="healthcare")])
    assert result["overall_verdict"] == VERDICT_CONTINUITY_BELEGT
    assert len(result["results"]) == 2


def test_report_single_undecidable_wins():
    bad = EvidenceBundle(
        source="x", method="y continuity drill",
        period_start="2026-11-21T10:00:00Z",
        period_end="2026-11-21T11:00:00Z", reference="")
    result = gate_report([good_check(), good_check(evidence=bad), good_check()])
    assert result["overall_verdict"] == VERDICT_UNDECIDABLE


def test_report_mixed_blocked_wins():
    result = gate_report([
        good_check(),
        good_check(service_key="unknown-sys"),
        good_check(),
    ])
    assert result["overall_verdict"] == VERDICT_BLOCKED


def test_report_mixed_undecidable():
    bad = EvidenceBundle(
        source="x", method="continuity drill",
        period_start="2026-11-21T10:00:00Z",
        period_end="2026-11-21T11:00:00Z", reference="")
    result = gate_report([good_check(), good_check(evidence=bad)])
    assert result["overall_verdict"] == VERDICT_UNDECIDABLE


# --- Determinismus / Verdict-Universum -------------------------------

def test_deterministic_repeat():
    a = evaluate_continuity(good_check())
    b = evaluate_continuity(good_check())
    assert a == b


def test_verdict_universe_closed():
    verdicts = {
        evaluate_continuity(good_check())["verdict"],
        evaluate_continuity(good_check(service_key="x"))["verdict"],
        evaluate_continuity(good_check(evidence=None))["verdict"],
        evaluate_continuity(good_check(responsible=" "))["verdict"],
    }
    assert verdicts <= set([VERDICT_CONTINUITY_BELEGT, VERDICT_UNDECIDABLE, VERDICT_BLOCKED])


def test_honest_limits_listing_stable():
    result = evaluate_continuity(good_check())
    assert isinstance(result["honest_limits"], tuple)
    assert result["honest_limits"]
