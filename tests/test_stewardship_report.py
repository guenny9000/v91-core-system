#!/usr/bin/env python3
"""Tests for stewardship ledger summary output."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from enforcement import StewardshipGate  # noqa: E402
from stewardship_report import summarize  # noqa: E402


def test_summary_counts_and_percentages(tmp_path):
    path = str(tmp_path / "s.jsonl")
    gate = StewardshipGate(path)
    gate.evaluate(
        "t1", {"resource_util": 0.9, "entropy": 0.9, "environment": 0.9, "human_impact": 0.1}
    )
    gate.evaluate(
        "t2", {"resource_util": 0.2, "entropy": 0.2, "environment": 0.2, "human_impact": 0.1}
    )
    gate.evaluate(
        "t3", {"resource_util": 0.8, "entropy": 0.8, "environment": 0.8, "human_impact": 0.7}
    )

    report = summarize(path)
    assert report["chain_valid"] is True
    assert report["total_entries"] == 3
    assert report["decision_counts"]["APPROVED_ADVISORY"] == 1
    assert report["decision_counts"]["IDLE"] == 1
    assert report["decision_counts"]["REJECTED_HUMAN_IMPACT"] == 1
    assert report["decision_percent"]["APPROVED_ADVISORY"] == 33.33
    assert report["decision_percent"]["IDLE"] == 33.33
    assert report["decision_percent"]["REJECTED_HUMAN_IMPACT"] == 33.33
    assert report["human_impact_veto_count"] == 1
    assert report["executed_true_count"] == 0


def test_summary_returns_chain_error_for_tampered_file(tmp_path):
    path = tmp_path / "s.jsonl"
    path.write_text("bad json\n", encoding="utf-8")
    report = summarize(str(path))
    assert report["chain_valid"] is False
    assert report["total_entries"] == 1
    assert report["decision_counts"] == {}
