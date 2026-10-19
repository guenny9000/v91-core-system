"""Tests for fail-closed isolated efficiency calculation."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from self_study_metrics import evaluate_efficiency


def test_evaluate_efficiency_labels_isolated_measurement_without_production_claim():
    result = evaluate_efficiency(100.0, 80.0, 5)

    assert result["measurement_status"] == "MEASURED_NOT_VERIFIED"
    assert result["efficiency_gain_percent"] == 20.0
    assert result["production_status"] == "UNKNOWN"


def test_evaluate_efficiency_fails_closed_for_missing_or_invalid_inputs():
    for baseline, candidate, samples in [
        (None, 80.0, 1),
        (0.0, 80.0, 1),
        (100.0, -1.0, 1),
        (100.0, float("nan"), 1),
        (100.0, 80.0, 0),
        (100.0, 80.0, True),
        (100.0, 80.0, 1.0),
    ]:
        result = evaluate_efficiency(baseline, candidate, samples)
        assert result["measurement_status"] == "UNKNOWN"
        assert result["production_status"] == "UNKNOWN"
