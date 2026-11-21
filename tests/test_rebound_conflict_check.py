#!/usr/bin/env python3
"""Tests: controller/rebound_conflict_check.py (MAX-BEST, VIBE-XXIX).

Fail-closed, UNKNOWN nie PASS, keine erfundenen Zahlen, keine
Erfolgsquoten. Alle Beispiele sind neutral-synthetisch.
"""
from __future__ import annotations

import dataclasses

import pytest

from controller.impact_area_registry import EvidenceBundle, IndicatorStatus
from controller.rebound_conflict_check import (
    CONFLICT_DIMENSIONS,
    DIMENSION_KEYS,
    Direction,
    DirectionImpact,
    MeasureProposal,
    ReboundConflictError,
    VERDICT_NICHT_ENTSCHEIDBAR,
    VERDICT_VERTRAEGLICH,
    VERDICT_ZIELKONFLIKT,
    assess_conflicts,
    rebound_risk,
)


def _evidence(source="quelle-a", method="verfahren-x"):
    return EvidenceBundle(
        source=source,
        method=method,
        period_start="2026-11-01T00:00:00Z",
        period_end="2026-11-21T00:00:00Z",
        reference="MAX-BEST VIBE-XXIX",
    )


def _full_impacts(direction=Direction.REDUCES):
    return {key: DirectionImpact(direction, _evidence()) for key in DIMENSION_KEYS}


def _full(direction=Direction.REDUCES, **kwargs):
    return MeasureProposal(
        measure_id="massnahme-1",
        goal="Importabhaengigkeit senken",
        claimed_primary_effect="weniger Netto-Importe",
        secondary_impacts=_full_impacts(direction),
        **kwargs,
    )


# ------------------------------------------------------------------ Guards
def test_non_proposal_raises():
    with pytest.raises(ReboundConflictError):
        assess_conflicts("massnahme")


def test_missing_measure_id_raises():
    with pytest.raises(ReboundConflictError):
        assess_conflicts(MeasureProposal(measure_id="  ", goal="g",
                                         claimed_primary_effect="e"))


def test_missing_goal_raises():
    with pytest.raises(ReboundConflictError):
        assess_conflicts(MeasureProposal(measure_id="m", goal=" ",
                                         claimed_primary_effect="e"))


def test_missing_primary_effect_raises():
    with pytest.raises(ReboundConflictError):
        assess_conflicts(MeasureProposal(measure_id="m", goal="g",
                                         claimed_primary_effect=""))


def test_non_boolean_efficiency_flag_raises():
    with pytest.raises(ReboundConflictError):
        assess_conflicts(dataclasses.replace(
            MeasureProposal(measure_id="m", goal="g",
                            claimed_primary_effect="e"), is_efficiency_gain="ja"))


def test_unknown_dimension_key_raises():
    with pytest.raises(ReboundConflictError):
        assess_conflicts(MeasureProposal(
            measure_id="m", goal="g", claimed_primary_effect="e",
            secondary_impacts={"not_a_dimension": None}))


def test_non_impact_value_raises():
    with pytest.raises(ReboundConflictError):
        assess_conflicts(MeasureProposal(
            measure_id="m", goal="g", claimed_primary_effect="e",
            secondary_impacts={"conflict_emissions_assessed": "schlecht"}))


# ------------------------------------------------------------------ Leere
def test_empty_proposal_is_nicht_entscheidbar():
    r = assess_conflicts(MeasureProposal(measure_id="m", goal="g",
                                         claimed_primary_effect="e"))
    assert r["verdict"] == VERDICT_NICHT_ENTSCHEIDBAR
    assert len(r["problems"]) >= len(DIMENSION_KEYS)
    assert r["overall_status"] == IndicatorStatus.NICHT_GEPRUEFT.value


def test_all_dimensions_must_be_examined():
    r = assess_conflicts(_full())
    for key in DIMENSION_KEYS:
        assert r["indicators"][key]["status"] == IndicatorStatus.BELEGT.value


# ------------------------------------------------------------- Konflikt
def test_increase_is_zielkonflikt():
    impacts = _full_impacts()
    impacts["conflict_emissions_assessed"] = DirectionImpact(
        Direction.INCREASES, _evidence())
    r = assess_conflicts(MeasureProposal(
        measure_id="m", goal="g", claimed_primary_effect="e",
        secondary_impacts=impacts))
    assert r["verdict"] == VERDICT_ZIELKONFLIKT
    assert any("ZIELKONFLIKT" in p and "conflict_emissions_assessed" in p
               for p in r["problems"])


def test_conflict_survives_despite_other_belegt_dimensions():
    impacts = _full_impacts()
    impacts["conflict_social_equity_assessed"] = DirectionImpact(
        Direction.INCREASES, _evidence())
    r = assess_conflicts(MeasureProposal(
        measure_id="m", goal="g", claimed_primary_effect="e",
        secondary_impacts=impacts))
    assert r["verdict"] == VERDICT_ZIELKONFLIKT
    # Zustand bleibt ehrlich: die anderen Dimensionen bleiben BELEGT
    assert r["indicators"]["conflict_emissions_assessed"]["status"] \
        == IndicatorStatus.BELEGT.value


def test_single_increase_without_others_still_conflict():
    impacts = {"conflict_environmental_burden_assessed":
               DirectionImpact(Direction.INCREASES, _evidence())}
    r = assess_conflicts(MeasureProposal(
        measure_id="m", goal="g", claimed_primary_effect="e",
        secondary_impacts=impacts))
    assert r["verdict"] == VERDICT_ZIELKONFLIKT


# ----------------------------------------------------------- Vertraeglich
def test_all_reduces_is_vertraeglich():
    r = assess_conflicts(_full())
    assert r["verdict"] == VERDICT_VERTRAEGLICH
    assert r["rebound_risk_open"] is False
    assert r["problems"] == []


def test_all_neutral_is_vertraeglich():
    r = assess_conflicts(_full(direction=Direction.NEUTRAL))
    assert r["verdict"] == VERDICT_VERTRAEGLICH


# ------------------------------------------------------------- Rebound
def test_efficiency_gain_without_resource_proof_is_rebound():
    proposal = MeasureProposal(
        measure_id="m", goal="g", claimed_primary_effect="e",
        is_efficiency_gain=True, secondary_impacts=_full_impacts())
    proposal = dataclasses.replace(proposal, secondary_impacts={
        **_full_impacts(),
        "conflict_resource_use_assessed": None})
    assert rebound_risk(proposal) is True
    r = assess_conflicts(proposal)
    assert r["rebound_risk_open"] is True
    assert any("REBOUND_RISIKO_OFFEN" in p for p in r["problems"])
    assert r["verdict"] == VERDICT_NICHT_ENTSCHEIDBAR


def test_efficiency_gain_with_neutral_resource_use_is_still_rebound():
    proposal = MeasureProposal(
        measure_id="m", goal="g", claimed_primary_effect="e",
        is_efficiency_gain=True,
        secondary_impacts=_full_impacts(Direction.NEUTRAL))
    assert rebound_risk(proposal) is True


def test_efficiency_gain_with_reduces_resource_use_is_no_rebound():
    proposal = MeasureProposal(
        measure_id="m", goal="g", claimed_primary_effect="e",
        is_efficiency_gain=True,
        secondary_impacts=_full_impacts(Direction.REDUCES))
    assert rebound_risk(proposal) is False
    assert assess_conflicts(proposal)["rebound_risk_open"] is False


def test_non_efficiency_measure_never_flags_rebound():
    assert rebound_risk(_full()) is False


# --------------------------------------------------------- Evidenzpflicht
def test_direction_without_source_is_never_belegt():
    impacts = _full_impacts()
    impacts["conflict_social_equity_assessed"] = DirectionImpact(
        Direction.REDUCES, _evidence(source=" "))
    r = assess_conflicts(MeasureProposal(
        measure_id="m", goal="g", claimed_primary_effect="e",
        secondary_impacts=impacts))
    assert r["indicators"]["conflict_social_equity_assessed"]["status"] \
        == IndicatorStatus.NICHT_GEPRUEFT.value
    assert r["verdict"] == VERDICT_NICHT_ENTSCHEIDBAR


def test_direction_without_method_is_never_belegt():
    impacts = _full_impacts()
    impacts["conflict_resource_use_assessed"] = DirectionImpact(
        Direction.REDUCES, _evidence(method=""))
    r = assess_conflicts(MeasureProposal(
        measure_id="m", goal="g", claimed_primary_effect="e",
        secondary_impacts=impacts))
    assert r["indicators"]["conflict_resource_use_assessed"]["status"] \
        == IndicatorStatus.NICHT_GEPRUEFT.value
    assert any("CLAIM != EVIDENCE" in p for p in r["problems"])


def test_dimension_with_false_evidence_never_lies_belegt():
    proposal = MeasureProposal(measure_id="m", goal="g",
                               claimed_primary_effect="e",
                               secondary_impacts={
                                   "conflict_emissions_assessed":
                                   DirectionImpact(
                                       Direction.REDUCES,
                                       EvidenceBundle(source="q", method="v",
                                                      period_start="kaputt",
                                                      period_end="auch"))})
    r = assess_conflicts(proposal)  # ungueltige Periode: herabgestuft, nie BELEGT
    assert r["indicators"]["conflict_emissions_assessed"]["status"] \
        == IndicatorStatus.NICHT_GEPRUEFT.value


# ------------------------------------------------------------------ Registry
def test_registry_covers_four_dimensions():
    assert len(CONFLICT_DIMENSIONS) == 4
    keys = [d.key for d in CONFLICT_DIMENSIONS]
    assert len(keys) == len(set(keys)) == len(DIMENSION_KEYS)


def test_report_never_contains_percent_or_quota():
    r = assess_conflicts(_full())
    blob = str(r)
    for forbidden in ("percent", "erreichung", "progress", "Erfolgsquote"):
        assert forbidden not in blob


def test_report_pins_boundary_rules():
    blob = str(assess_conflicts(_full()))
    assert "DATENSATZANGABE != GEPRUEFTE_MESSUNG" in blob
    assert "DURCHSCHNITT != BEWEIS_REALER_UNABHAENGIGKEIT" in blob
    assert "KAPAZITAET != VERFUEGBARE_RESERVE" in blob
    assert "HEIMISCHE_GEWINNUNG != LIEFERKETTENFREIHEIT" in blob


def test_schema_is_pinned():
    assert assess_conflicts(_full())["schema"] == "v91.rebound_conflict_check.v1"


def test_deterministic_assessment():
    first = assess_conflicts(_full())
    second = assess_conflicts(_full())
    assert first == second
