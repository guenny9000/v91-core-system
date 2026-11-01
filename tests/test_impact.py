#!/usr/bin/env python3
"""Tests – impact measurement from real-data CSV rows."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from impact import compute_impact, record_impact, verified_summary  # noqa: E402
from ledger import HashChainLedger, verify_chain  # noqa: E402


def rows(values, day, source="direct_sensor"):
    return [
        {"timestamp": f"2026-11-{day:02d}T00:{i:02d}:00+00:00", "value": v, "source_type": source}
        for i, v in enumerate(values)
    ]


BASE = rows([100, 101, 99, 100, 102, 98], 1)
AFTER = rows([80, 81, 79, 80, 82, 78], 2)


def test_co2_factor_requires_source():
    import pytest

    with pytest.raises(ValueError):
        compute_impact("kwh", BASE, AFTER, "kWh", co2_factor_kg_per_unit=0.4)
    r = compute_impact("kwh", BASE, AFTER, "kWh", 0.4, co2_source="UBA")
    assert r["co2_factor_source"] == "UBA"


def test_real_improvement_is_valid_with_co2():
    r = compute_impact("kwh", BASE, AFTER, "kWh", co2_factor_kg_per_unit=0.4, co2_source="t")
    assert r["status"] == "VALID" and r["saved_per_sample"] == 20.0
    assert r["co2_saved_kg_per_sample"] == 8.0


def test_noise_only_is_not_significant():
    r = compute_impact("kwh", BASE, rows([100, 99, 101, 100, 102, 98], 2), "kWh")
    assert r["status"] == "QUARANTINE" and "NOT_SIGNIFICANT" in r["flags"]


def test_temporal_error_and_too_few_samples():
    assert "TEMPORAL_ERROR" in compute_impact("m", AFTER, BASE, "u")["flags"]
    assert "TOO_FEW_SAMPLES" in compute_impact("m", BASE[:3], AFTER, "u")["flags"]


def test_low_quality_sources_quarantined():
    r = compute_impact("m", BASE, rows([80, 81, 79, 80, 82, 78], 2, "manual_entry"), "u")
    assert r["status"] == "QUARANTINE" and "LOW_DQI" in r["flags"]


def test_garbage_rows_rejected_not_crashing():
    bad = AFTER + [{"timestamp": "x", "value": "nan", "source_type": "??"}]
    r = compute_impact("m", BASE, bad, "u")
    assert r["rejected_rows"] == 1


def test_worsening_is_not_counted_as_valid(tmp_path):
    r = compute_impact("m", AFTER, rows([100, 101, 99, 100, 102, 98], 3), "u")
    assert r["status"] == "NO_IMPROVEMENT"


def test_only_valid_counts_in_summary(tmp_path):
    path = str(tmp_path / "l.jsonl")
    ledger = HashChainLedger(path)
    record_impact(ledger, compute_impact("a", BASE, AFTER, "u", 0.5, co2_source="t"))
    record_impact(ledger, compute_impact("b", BASE, BASE[:2] and rows([100] * 6, 2), "u", 0.5, co2_source="t"))
    assert verify_chain(path)["chain_valid"]
    s = verified_summary(path)
    assert s["impacts_total"] == 2 and s["impacts_valid"] == 1
    assert s["verified_co2_saved_kg_per_sample"] == 10.0
