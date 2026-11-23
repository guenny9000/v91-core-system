#!/usr/bin/env python3
"""Regression: evidence references with raw-artifact digests (protocol section 3)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

import pytest  # noqa: E402

from impact import compute_impact  # noqa: E402


GOOD = "a" * 64


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


def test_valid_evidence_refs_are_carried_into_result():
    refs = [
        {"raw_artifact_ref": "evidence://baseline/2026-11.csv", "raw_artifact_sha256": GOOD},
        {"raw_artifact_ref": "evidence://after/2026-11.csv", "raw_artifact_sha256": "b" * 64},
    ]
    result = compute_impact("kwh", BASE, AFTER, "kWh", evidence_refs=refs)
    assert result["evidence_refs"] == refs


def test_no_evidence_refs_keeps_backward_compatible_no_key():
    result = compute_impact("kwh", BASE, AFTER, "kWh")
    assert "evidence_refs" not in result


def test_malformed_hash_is_rejected_fail_closed():
    with pytest.raises(ValueError, match="raw_artifact_sha256"):
        compute_impact(
            "kwh", BASE, AFTER, "kWh",
            evidence_refs=[{"raw_artifact_ref": "evidence://x", "raw_artifact_sha256": "abc"}],
        )


def test_uppercase_or_nonstring_refs_rejected():
    with pytest.raises(ValueError):
        compute_impact(
            "kwh", BASE, AFTER, "kWh",
            evidence_refs=[{"raw_artifact_ref": "evidence://x", "raw_artifact_sha256": GOOD.upper()}],
        )
    with pytest.raises(ValueError):
        compute_impact(
            "kwh", BASE, AFTER, "kWh", evidence_refs=[{"raw_artifact_sha256": GOOD}]
        )
    with pytest.raises(ValueError):
        compute_impact("kwh", BASE, AFTER, "kWh", evidence_refs=["just-a-string"])
