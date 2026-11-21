#!/usr/bin/env python3
"""Tests: controller/impact_area_registry.py (MAX-BEST Statusmodell, VIBE-XXVII).

Alle Tests pruefen fail-closed: kein erfundener Fortschritt, kein BELEGT
ohne vollstaendige Evidenz, UNKNOWN nie PASS, keine Prozent-Erfindung.
"""
from __future__ import annotations

import pytest

from controller.impact_area_registry import (
    Area,
    EvidenceBundle,
    ImpactAreaRegistryError,
    IndicatorDefinition,
    IndicatorStatus,
    MeasurementClaim,
    MeasurementScope,
    UnavailableClaim,
    assess_indicator,
    registry_report,
    verify_determinism,
    DEFAULT_REGISTRY,
)


def _ev(source="meter-1", method="direct measurement", start="2026-01-01T00:00:00Z",
        end="2026-12-31T23:59:59Z", reference=""):
    return EvidenceBundle(source, method, start, end, reference)


def _def_local():
    return IndicatorDefinition("test_local", Area.AUTARKIE, "Lokaler Anteil",
                               "share_0_1", MeasurementScope.LOCAL_ENVIRONMENT)


# ---------------------------------------------------------------- Evidence
def test_valid_evidence_yields_belegt():
    d = _def_local()
    r = assess_indicator(d, MeasurementClaim(0.62, "share_0_1", _ev()))
    assert r["status"] == IndicatorStatus.BELEGT
    assert r["value"] == 0.62


def test_no_submission_is_nicht_geprueft():
    r = assess_indicator(_def_local(), None)
    assert r["status"] == IndicatorStatus.NICHT_GEPRUEFT
    assert r["problems"] == ["no measurement submitted"]


def test_missing_source_is_never_belegt():
    r = assess_indicator(_def_local(), MeasurementClaim(0.5, "share_0_1", _ev(source="  ")))
    assert r["status"] == IndicatorStatus.NICHT_GEPRUEFT
    assert "source missing" in r["problems"]


def test_missing_method_is_never_belegt():
    r = assess_indicator(_def_local(), MeasurementClaim(0.5, "share_0_1", _ev(method="")))
    assert r["status"] == IndicatorStatus.NICHT_GEPRUEFT


def test_period_start_after_end_is_invalid():
    r = assess_indicator(_def_local(), MeasurementClaim(
        0.5, "share_0_1", _ev(start="2027-01-01T00:00:00Z", end="2026-01-01T00:00:00Z")))
    assert r["status"] == IndicatorStatus.NICHT_GEPRUEFT
    assert any("period" in p for p in r["problems"])


def test_naive_period_without_timezone_is_invalid():
    r = assess_indicator(_def_local(), MeasurementClaim(
        0.5, "share_0_1", _ev(start="2026-01-01T00:00:00", end="2026-02-01T00:00:00")))
    assert r["status"] == IndicatorStatus.NICHT_GEPRUEFT


def test_unit_mismatch_is_invalid():
    r = assess_indicator(_def_local(), MeasurementClaim(62.0, "%", _ev()))
    assert r["status"] == IndicatorStatus.NICHT_GEPRUEFT
    assert any("unit mismatch" in p for p in r["problems"])


def test_boolean_value_is_invalid():
    r = assess_indicator(_def_local(), MeasurementClaim(True, "share_0_1", _ev()))
    assert r["status"] == IndicatorStatus.NICHT_GEPRUEFT


def test_negative_value_is_invalid():
    r = assess_indicator(_def_local(), MeasurementClaim(-0.1, "share_0_1", _ev()))
    assert r["status"] == IndicatorStatus.NICHT_GEPRUEFT


@pytest.mark.parametrize("bad", [float("inf"), float("nan")])
def test_non_finite_value_is_invalid(bad):
    r = assess_indicator(_def_local(), MeasurementClaim(bad, "share_0_1", _ev()))
    assert r["status"] == IndicatorStatus.NICHT_GEPRUEFT


def test_missing_evidence_bundle_is_invalid():
    class Fake:  # MeasurementClaim ohne EvidenceBundle
        pass
    r = registry_report([_def_local()], {}).get("indicators")
    assert r["test_local"]["status"] == IndicatorStatus.NICHT_GEPRUEFT


# ---------------------------------------------------------- Unavailable
def test_unavailable_claim_with_reason_is_nicht_verfuegbar():
    r = assess_indicator(_def_local(), UnavailableClaim("kein Sensor vorhanden"))
    assert r["status"] == IndicatorStatus.NICHT_VERFUEGBAR
    assert r["reason"] == "kein Sensor vorhanden"


def test_unavailable_claim_without_reason_is_open():
    r = assess_indicator(_def_local(), UnavailableClaim("  "))
    assert r["status"] == IndicatorStatus.NICHT_GEPRUEFT


def test_unavailable_claim_with_non_string_reason_is_open():
    r = assess_indicator(_def_local(), UnavailableClaim(42))
    assert r["status"] == IndicatorStatus.NICHT_GEPRUEFT


# --------------------------------------------------------------- Guards
def test_wrong_definition_type_raises():
    with pytest.raises(ImpactAreaRegistryError):
        assess_indicator("klima", None)


def test_wrong_submission_type_raises():
    with pytest.raises(ImpactAreaRegistryError):
        assess_indicator(_def_local(), "davon 85 Prozent")


# --------------------------------------------------------------- Report
def test_report_area_all_belegt():
    reg = (IndicatorDefinition("a", Area.AUTARKIE, "q", "share_0_1", MeasurementScope.LOCAL_ENVIRONMENT),
           IndicatorDefinition("b", Area.AUTARKIE, "q", "share_0_1", MeasurementScope.LOCAL_ENVIRONMENT))
    subs = {k: MeasurementClaim(0.5, "share_0_1", _ev()) for k in ("a", "b")}
    report = registry_report(reg, subs)
    assert report["areas"]["AUTARKIE"]["status"] == IndicatorStatus.BELEGT.value
    assert report["overall_status"] == IndicatorStatus.BELEGT.value


def test_report_any_open_keeps_area_open():
    reg = (IndicatorDefinition("a", Area.AUTARKIE, "q", "share_0_1", MeasurementScope.LOCAL_ENVIRONMENT),
           IndicatorDefinition("b", Area.AUTARKIE, "q", "share_0_1", MeasurementScope.LOCAL_ENVIRONMENT))
    report = registry_report(reg, {"a": MeasurementClaim(0.5, "share_0_1", _ev())})
    assert report["areas"]["AUTARKIE"]["status"] == IndicatorStatus.NICHT_GEPRUEFT.value
    assert report["overall_status"] == IndicatorStatus.NICHT_GEPRUEFT.value


def test_report_all_unavailable_area():
    reg = (IndicatorDefinition("a", Area.FRIEDEN, "q", "persons", MeasurementScope.EXTERNAL_WORLD),)
    report = registry_report(reg, {"a": UnavailableClaim("keine vertrauenswuerdige Quelle verfuegbar")})
    assert report["areas"]["FRIEDEN"]["status"] == IndicatorStatus.NICHT_VERFUEGBAR.value
    assert report["overall_status"] == IndicatorStatus.NICHT_VERFUEGBAR.value


def test_report_mixed_belegt_unavailable_is_teilweise():
    reg = (IndicatorDefinition("a", Area.FRIEDEN, "q", "persons", MeasurementScope.EXTERNAL_WORLD),
           IndicatorDefinition("b", Area.AUTARKIE, "q", "share_0_1", MeasurementScope.LOCAL_ENVIRONMENT))
    report = registry_report(reg, {
        "a": UnavailableClaim("keine Quelle"),
        "b": MeasurementClaim(0.5, "share_0_1", _ev())})
    assert report["areas"]["AUTARKIE"]["status"] == IndicatorStatus.BELEGT.value
    assert report["areas"]["FRIEDEN"]["status"] == IndicatorStatus.NICHT_VERFUEGBAR.value
    assert report["overall_status"] == IndicatorStatus.TEILWEISE_VERFUEGBAR.value


def test_report_rejects_unknown_submission_key():
    with pytest.raises(ImpactAreaRegistryError):
        registry_report(list(DEFAULT_REGISTRY), {"erfundener_indikator": None})


def test_report_rejects_duplicate_keys():
    d = _def_local()
    with pytest.raises(ImpactAreaRegistryError):
        registry_report((d, d), {})


def test_report_rejects_empty_registry():
    with pytest.raises(ImpactAreaRegistryError):
        registry_report((), {})


def test_report_never_contains_percent_progress():
    report = registry_report(list(DEFAULT_REGISTRY), {})
    blob = str(report)
    for forbidden in ("progress", "percent", "erreichung"):
        assert forbidden not in blob
    assert report["overall_status"] == IndicatorStatus.NICHT_GEPRUEFT.value


# ---------------------------------------------------------- Determinismus
def test_determinism_equal_outputs_pass():
    assert verify_determinism(lambda x: x * 2, [1, 2, 3]) is True


def test_determinism_diverging_outputs_fail(monkeypatch):
    calls = {"n": 0}
    def unstable(x):
        calls["n"] += 1
        return x if calls["n"] <= 3 else x + 1
    assert verify_determinism(unstable, [1, 2, 3]) is False


def test_determinism_raising_function_fails_closed():
    with pytest.raises(ImpactAreaRegistryError):
        verify_determinism(lambda x: 1 / 0, [1])


def test_default_registry_covers_all_five_areas():
    areas = {d.area for d in DEFAULT_REGISTRY}
    assert areas == {Area.KLIMA, Area.FRIEDEN, Area.AUTARKIE,
                     Area.DETERMINISMUS, Area.GEMEINWOHL}


def test_default_registry_keys_unique():
    keys = [d.key for d in DEFAULT_REGISTRY]
    assert len(keys) == len(set(keys))
