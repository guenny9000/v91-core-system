#!/usr/bin/env python3
"""Tests: controller/gemeinwohl_check.py (MAX-BEST, VIBE-XXX).

Fail-closed, UNKNOWN nie PASS, keine erfundenen Zahlen, keine
Erfolgsquoten. Alle Beispiele sind neutral-synthetisch.
"""
from __future__ import annotations

import pytest

from controller.gemeinwohl_check import (
    ALLOWED_REBOUND_VERDICTS,
    RULE_KEYS,
    SCHUTZREGELN,
    VERDICT_GEMEINWOHLTAUGLICH,
    GemeinwohlError,
    GemeinwohlInitiative,
    ImpactPlanIndicator,
    assess_gemeinwohl,
    messplan_report,
    validate_messplan_entry,
)
from controller.impact_area_registry import EvidenceBundle, IndicatorStatus
from controller.rebound_conflict_check import (
    VERDICT_NICHT_ENTSCHEIDBAR,
    VERDICT_VERTRAEGLICH,
    VERDICT_ZIELKONFLIKT,
)


def _evidence(source="quelle-g", method="verfahren-g"):
    return EvidenceBundle(
        source=source,
        method=method,
        period_start="2026-11-01T00:00:00Z",
        period_end="2026-11-21T00:00:00Z",
        reference="MAX-BEST VIBE-XXX",
    )


def _entry(**kwargs):
    defaults = dict(
        name="Teilhabe-Stunden",
        unit="Stunden",
        baseline=0.0,
        target=100.0,
        period_start="2026-11-21T00:00:00Z",
        period_end="2027-12-31T00:00:00Z",
        method="Einsatznachweise",
        verifier="Register des Pilotteams",
        source="Pilotkonzept",
        uncertainty=10.0,
    )
    defaults.update(kwargs)
    return ImpactPlanIndicator(**defaults)


def _full_initiative(**kwargs):
    rule_evidence = {key: _evidence() for key in RULE_KEYS}
    return GemeinwohlInitiative(
        initiative_id="initiative-1",
        description="Freiwillige Teilhabe-Pilotinitiative (Beispiel)",
        rule_evidence=rule_evidence,
        messplan=[_entry()],
        **kwargs,
    )


# ------------------------------------------------------------------ Guards
def test_non_initiative_raises():
    with pytest.raises(GemeinwohlError):
        assess_gemeinwohl("initiative")


def test_missing_initiative_id_raises():
    with pytest.raises(GemeinwohlError):
        assess_gemeinwohl(GemeinwohlInitiative(
            initiative_id="  ", description="d",
            rule_evidence={}, messplan=[]))


def test_missing_description_raises():
    with pytest.raises(GemeinwohlError):
        assess_gemeinwohl(GemeinwohlInitiative(
            initiative_id="i", description=" ",
            rule_evidence={}, messplan=[]))


def test_unknown_rule_key_raises():
    with pytest.raises(GemeinwohlError):
        assess_gemeinwohl(GemeinwohlInitiative(
            initiative_id="i", description="d",
            rule_evidence={"rule_erfunden": _evidence()}, messplan=[]))


def test_non_evidence_rule_value_raises():
    with pytest.raises(GemeinwohlError):
        assess_gemeinwohl(GemeinwohlInitiative(
            initiative_id="i", description="d",
            rule_evidence={"rule_voluntary_participation": "ok"}, messplan=[]))


def test_non_indicator_messplan_entry_raises():
    with pytest.raises(GemeinwohlError):
        assess_gemeinwohl(GemeinwohlInitiative(
            initiative_id="i", description="d",
            rule_evidence={}, messplan=["eintrag"]))


def test_invalid_rebound_verdict_raises():
    with pytest.raises(GemeinwohlError):
        assess_gemeinwohl(_full_initiative(rebound_verdict="SUPER"))


# -------------------------------------------------------------- Vollstaendig
def test_full_initiative_is_gemeinwohltauglich():
    r = assess_gemeinwohl(_full_initiative())
    assert r["verdict"] == VERDICT_GEMEINWOHLTAUGLICH
    assert r["problems"] == []
    assert r["messplan"]["messplan_ok"] is True


def test_all_eight_rules_must_be_documented():
    r = assess_gemeinwohl(_full_initiative())
    for key in RULE_KEYS:
        assert r["indicators"][key]["status"] == IndicatorStatus.BELEGT.value


def test_missing_rule_makes_nicht_entscheidbar():
    rule_evidence = {key: _evidence() for key in RULE_KEYS}
    del rule_evidence["rule_voluntary_participation"]
    r = assess_gemeinwohl(GemeinwohlInitiative(
        initiative_id="i", description="d",
        rule_evidence=rule_evidence, messplan=[_entry()]))
    assert r["verdict"] == VERDICT_NICHT_ENTSCHEIDBAR
    assert any("rule_voluntary_participation" in p for p in r["problems"])


def test_rule_with_thin_evidence_is_never_belegt():
    rule_evidence = {key: _evidence() for key in RULE_KEYS}
    rule_evidence["rule_independent_effect_control"] = _evidence(source=" ")
    r = assess_gemeinwohl(GemeinwohlInitiative(
        initiative_id="i", description="d",
        rule_evidence=rule_evidence, messplan=[_entry()]))
    assert r["indicators"]["rule_independent_effect_control"]["status"] \
        == IndicatorStatus.NICHT_GEPRUEFT.value
    assert r["verdict"] == VERDICT_NICHT_ENTSCHEIDBAR


def test_empty_initiative_is_never_pass():
    r = assess_gemeinwohl(GemeinwohlInitiative(
        initiative_id="i", description="d", rule_evidence={}, messplan=[]))
    assert r["verdict"] == VERDICT_NICHT_ENTSCHEIDBAR
    assert len(r["problems"]) >= len(RULE_KEYS)


# ------------------------------------------------------------------ Messplan
def test_messplan_entry_validation_catches_all_gaps():
    problems = validate_messplan_entry(_entry(
        name=" ", unit="", baseline=-1.0, target="x",
        period_start="kaputt", period_end="auch",
        method="", verifier="", source="", uncertainty=-2.0))
    for expected in ("name missing", "unit missing", "baseline", "target",
                     "period invalid", "method missing", "verifier missing",
                     "source missing", "uncertainty"):
        assert any(expected in p for p in problems)


def test_valid_messplan_entry_has_no_problems():
    assert validate_messplan_entry(_entry()) == []


def test_messplan_report_counts_invalid_entries():
    init = GemeinwohlInitiative(
        initiative_id="i", description="d", rule_evidence={},
        messplan=[_entry(), _entry(source=" ")])
    report = messplan_report(init)
    assert report["entry_count"] == 2
    assert report["invalid_count"] == 1
    assert report["messplan_ok"] is False


def test_empty_messplan_is_not_ok():
    report = messplan_report(GemeinwohlInitiative(
        initiative_id="i", description="d", rule_evidence={}, messplan=[]))
    assert report["messplan_ok"] is False


# --------------------------------------------------------------- Rebound-Bruecke
def test_zielkonflikt_blocks_gemeinwohl():
    r = assess_gemeinwohl(_full_initiative(rebound_verdict=VERDICT_ZIELKONFLIKT))
    assert r["verdict"] == VERDICT_ZIELKONFLIKT
    assert any("Reboundpruefung blockt" in p for p in r["problems"])


def test_open_rebound_stays_open():
    r = assess_gemeinwohl(_full_initiative(rebound_verdict=VERDICT_NICHT_ENTSCHEIDBAR))
    assert r["verdict"] == VERDICT_NICHT_ENTSCHEIDBAR
    assert any("Reboundpruefung unentscheidbar" in p for p in r["problems"])


def test_vertraeglich_rebound_does_not_block():
    r = assess_gemeinwohl(_full_initiative(rebound_verdict=VERDICT_VERTRAEGLICH))
    assert r["verdict"] == VERDICT_GEMEINWOHLTAUGLICH


# ------------------------------------------------------------------ Registry
def test_registry_covers_eight_schutzregeln():
    assert len(SCHUTZREGELN) == 8
    keys = [d.key for d in SCHUTZREGELN]
    assert len(keys) == len(set(keys)) == len(RULE_KEYS)


def test_rebound_verdict_whitelist_is_closed():
    assert VERDICT_ZIELKONFLIKT in ALLOWED_REBOUND_VERDICTS
    assert VERDICT_NICHT_ENTSCHEIDBAR in ALLOWED_REBOUND_VERDICTS
    assert VERDICT_VERTRAEGLICH in ALLOWED_REBOUND_VERDICTS
    assert None in ALLOWED_REBOUND_VERDICTS
    assert "ALLES_GUT" not in ALLOWED_REBOUND_VERDICTS


def test_report_never_contains_percent_or_quota():
    blob = str(assess_gemeinwohl(_full_initiative()))
    for forbidden in ("percent", "erreichung", "progress", "Erfolgsquote"):
        assert forbidden not in blob


def test_report_pins_messmatrix_limits():
    blob = str(assess_gemeinwohl(_full_initiative()))
    assert "MATRIZ != WIRKUNG" in blob
    assert "ZIELWERT != ERGEBNIS" in blob
    assert "AUSGEFUELLT != GELEBT" in blob
    assert "REVIEW != ENTSCHEIDUNG" in blob


def test_schema_is_pinned():
    assert assess_gemeinwohl(_full_initiative())["schema"] \
        == "v91.gemeinwohl_check.v1"


def test_deterministic_assessment():
    assert assess_gemeinwohl(_full_initiative()) == assess_gemeinwohl(_full_initiative())
