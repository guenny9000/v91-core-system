#!/usr/bin/env python3
"""Tests - parameterizable impact thresholds (protocol section 4).

The module defaults (MIN_SAMPLES=5, DQI_MIN=0.85, NOISE_FACTOR=2.0) are
documented defaults, never universal validity criteria. Callers set
per-use-case thresholds; invalid threshold inputs raise instead of
falling back silently (fail-closed), and every result records the
effective thresholds so a VALID claim stays auditable.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

import pytest  # noqa: E402

from impact import compute_impact, MIN_SAMPLES, DQI_MIN, NOISE_FACTOR  # noqa: E402


def rows(values, day, source="direct_sensor"):
    return [
        {"timestamp": f"2026-11-{day:02d}T00:{i:02d}:00+00:00", "value": v, "source_type": source}
        for i, v in enumerate(values)
    ]


BASE = rows([100, 101, 99, 100, 102, 98], 1)
AFTER = rows([80, 81, 79, 80, 82, 78], 2)


def test_defaults_are_recorded_in_result():
    r = compute_impact("m", BASE, AFTER, "u")
    assert r["thresholds"] == {
        "min_samples": MIN_SAMPLES,
        "dqi_min": DQI_MIN,
        "noise_factor": NOISE_FACTOR,
    }
    assert r["thresholds"]["min_samples"] == 5
    assert r["thresholds"]["dqi_min"] == 0.85
    assert r["thresholds"]["noise_factor"] == 2.0


def test_default_call_unchanged_legacy_behavior():
    r = compute_impact("kwh", BASE, AFTER, "kWh", co2_factor_kg_per_unit=0.4, co2_source="t")
    assert r["status"] == "VALID" and r["saved_per_sample"] == 20.0


def test_lower_min_samples_allows_small_samples():
    r = compute_impact("m", BASE[:3], AFTER[:3], "u", min_samples=3)
    assert "TOO_FEW_SAMPLES" not in r["flags"]
    assert r["thresholds"]["min_samples"] == 3


def test_higher_min_samples_rejects_default_valid_input():
    r = compute_impact("m", BASE, AFTER, "u", min_samples=10)
    assert r["status"] == "QUARANTINE" and "TOO_FEW_SAMPLES" in r["flags"]


def test_boundary_dqi_min_one_passes_clean_direct_sensor_data():
    # All direct_sensor rows without rejects give dqi == 1.0, so the
    # strictest allowed boundary (dqi_min == 1.0) still passes here.
    r = compute_impact("m", BASE, AFTER, "u", dqi_min=1.0)
    assert "LOW_DQI" not in r["flags"]
    assert r["thresholds"]["dqi_min"] == 1.0


def test_low_dqi_against_raised_threshold():
    mixed = rows([80, 81, 79, 80, 82, 78], 2, "manual_entry")
    r = compute_impact("m", BASE, mixed, "u", dqi_min=1.0)
    assert r["status"] == "QUARANTINE" and "LOW_DQI" in r["flags"]


def test_small_noise_factor_marks_noise_as_significant():
    # Slightly-lower but noisy after-period: NOT_SIGNIFICANT under the
    # default gate (diff must exceed 2x stderr), accepted when the caller
    # loosens the significance band (0.4x stderr). This demonstrates
    # exactly why thresholds must be caller-justified, never default-trusted.
    noisy = rows([97, 100, 99, 101, 102, 98], 2)  # mean 99.5 vs baseline 100
    strict = compute_impact("m", BASE, noisy, "u")
    assert "NOT_SIGNIFICANT" in strict["flags"]
    loose = compute_impact("m", BASE, noisy, "u", noise_factor=0.4)
    assert "NOT_SIGNIFICANT" not in loose["flags"]
    assert loose["status"] == "VALID"
    assert loose["thresholds"]["noise_factor"] == 0.4


def test_invalid_min_samples_raises():
    for bad in (1, 0, -5, 2.5, "5", True, [5]):
        with pytest.raises(ValueError):
            compute_impact("m", BASE, AFTER, "u", min_samples=bad)


def test_invalid_dqi_min_raises():
    for bad in (0.0, -0.1, 1.5, math.nan, math.inf, "0.9", True):
        with pytest.raises(ValueError):
            compute_impact("m", BASE, AFTER, "u", dqi_min=bad)


def test_invalid_noise_factor_raises():
    for bad in (0.0, -2.0, math.nan, math.inf, "2", True, [2.0]):
        with pytest.raises(ValueError):
            compute_impact("m", BASE, AFTER, "u", noise_factor=bad)
