#!/usr/bin/env python3
"""Regression: timezone-naive timestamps must be rejected, never imputed."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from impact import compute_impact  # noqa: E402


def tz_rows(values, day, source="direct_sensor"):
    return [
        {
            "timestamp": f"2026-11-{day:02d}T00:{i:02d}:00+00:00",
            "value": v,
            "source_type": source,
        }
        for i, v in enumerate(values)
    ]


def naive_rows(values, day, source="direct_sensor"):
    return [
        {"timestamp": f"2026-11-{day:02d}T00:{i:02d}:00", "value": v, "source_type": source}
        for i, v in enumerate(values)
    ]


def test_naive_timestamp_rows_are_rejected_and_counted():
    base = tz_rows([100, 101, 99, 100, 102, 98], 1)
    after_all_naive = naive_rows([80, 81, 79, 80, 82, 78], 2)
    result = compute_impact("kwh", base, after_all_naive, "kWh")
    assert result["rejected_rows"] == 6
    assert result["n_after"] == 0
    assert "TOO_FEW_SAMPLES" in result["flags"]
    assert result["status"] == "QUARANTINE"


def test_mixed_rows_reject_only_naive_part():
    base = tz_rows([100, 101, 99, 100, 102, 98], 1)
    after = tz_rows([80, 81, 79], 2) + naive_rows([77, 78, 90], 4)
    result = compute_impact("kwh", base, after, "kWh")
    assert result["rejected_rows"] == 3
    assert result["n_after"] == 3
    assert "TOO_FEW_SAMPLES" in result["flags"]
    assert result["status"] == "QUARANTINE"


def test_naive_timestamps_never_produce_valid_result():
    base = naive_rows([100, 101, 99, 100, 102, 98], 1)
    after = naive_rows([80, 81, 79, 80, 82, 78], 2)
    result = compute_impact("kwh", base, after, "kWh")
    assert result["status"] == "QUARANTINE"
    assert result["rejected_rows"] == 12
