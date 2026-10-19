"""Fail-closed efficiency measurements for isolated self-study experiments.

This module only calculates a result from values explicitly supplied by a caller.
It does not collect telemetry, run workloads, or establish production impact.
"""

from __future__ import annotations

from math import isfinite
from typing import Any


def evaluate_efficiency(
    baseline_seconds: float | None,
    candidate_seconds: float | None,
    sample_count: int,
) -> dict[str, Any]:
    """Return a labeled comparison, or UNKNOWN when the inputs are inadequate."""
    if (
        isinstance(baseline_seconds, bool)
        or isinstance(candidate_seconds, bool)
        or not isinstance(baseline_seconds, (int, float))
        or not isinstance(candidate_seconds, (int, float))
        or not isinstance(sample_count, int)
        or sample_count < 1
        or not isfinite(float(baseline_seconds))
        or not isfinite(float(candidate_seconds))
        or baseline_seconds <= 0
        or candidate_seconds < 0
    ):
        return {
            "measurement_status": "UNKNOWN",
            "reason": "Missing or invalid isolated timing inputs.",
            "production_status": "UNKNOWN",
        }

    change_percent = ((baseline_seconds - candidate_seconds) / baseline_seconds) * 100
    return {
        "measurement_status": "MEASURED_NOT_VERIFIED",
        "baseline_seconds": float(baseline_seconds),
        "candidate_seconds": float(candidate_seconds),
        "sample_count": sample_count,
        "efficiency_gain_percent": round(change_percent, 2),
        "production_status": "UNKNOWN",
        "reason": (
            "Caller-supplied isolated timings only; this result does not prove "
            "causation, generalization, or production impact."
        ),
    }
