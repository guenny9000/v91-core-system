#!/usr/bin/env python3
"""Regression: totals stay calculation-valid; independent verification is never self-assigned."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from impact import compute_impact, record_impact, verified_summary  # noqa: E402
from ledger import HashChainLedger, verify_chain  # noqa: E402


def tz_rows(values, day, source="direct_sensor"):
    return [
        {
            "timestamp": f"2026-11-{day:02d}T00:{i:02d}:00+00:00",
            "value": v,
            "source_type": source,
        }
        for i, v in enumerate(values)
    ]


BASE = tz_rows([100, 101, 99, 100, 102, 98], 1)
AFTER = tz_rows([80, 81, 79, 80, 82, 78], 2)


def test_summary_separates_calculation_valid_from_review(tmp_path):
    path = str(tmp_path / "l.jsonl")
    ledger = HashChainLedger(path)
    record_impact(
        ledger, compute_impact("kwh", BASE, AFTER, "kWh", 0.5, co2_source="t")
    )
    flat = tz_rows([100] * 6, 3)
    record_impact(
        ledger, compute_impact("kwh", BASE, flat, "kWh", 0.5, co2_source="t")
    )
    assert verify_chain(path)["chain_valid"]
    summary = verified_summary(path)
    assert summary["impacts_total"] == 2
    assert summary["impacts_valid"] == 1
    # Legacy key is kept for compatibility, new explicit key carries the same value.
    assert summary["valid_impacts_co2_saved_kg_per_sample"] == summary["verified_co2_saved_kg_per_sample"]
    # INDEPENDENTLY_VERIFIED can never be produced by the calculator itself.
    assert summary["review_status"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert summary["verified_impacts_count_independently_reviewed"] == 0
