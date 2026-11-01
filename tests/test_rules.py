#!/usr/bin/env python3
"""Unit Tests – MetricsFeed (UNKNOWN-safe semantics)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from metrics import MetricsFeed  # noqa: E402

# ---------------------------------------------------------------------------
# Existing tests (updated for None-returning API)
# ---------------------------------------------------------------------------

def test_error_rate_calculation():
    feed = MetricsFeed()
    for i in range(10):
        feed.record_event(latency=100, error=(i % 2 == 0))
    assert feed.get_error_rate() == 0.5


def test_latency_tracking():
    feed = MetricsFeed()
    latencies = [100, 150, 120, 110, 130]
    for lat in latencies:
        feed.record_event(latency=lat, error=False)
    avg = feed.get_recent_average_latency(window=5)
    expected = sum(latencies) / len(latencies)
    assert avg is not None
    assert abs(avg - expected) < 1


def test_snapshot():
    feed = MetricsFeed()
    feed.record_event(latency=100, error=False)
    feed.record_event(latency=200, error=True)
    snap = feed.snapshot()
    assert snap["events"] == 2
    assert snap["errors"] == 1


# ---------------------------------------------------------------------------
# New UNKNOWN-safe tests
# ---------------------------------------------------------------------------

def test_empty_error_rate_is_none():
    """No events recorded → error_rate must be None, not 0.0."""
    feed = MetricsFeed()
    assert feed.get_error_rate() is None


def test_empty_latency_is_none():
    """No events recorded → average latency must be None, not 0."""
    feed = MetricsFeed()
    assert feed.get_recent_average_latency() is None


def test_empty_snapshot_status_is_unknown():
    """Snapshot fields must carry UNKNOWN status when no events exist."""
    feed = MetricsFeed()
    snap = feed.snapshot()
    assert snap["error_rate"] is None
    assert snap["error_rate_status"] == "UNKNOWN"
    assert snap["latency"] is None
    assert snap["latency_status"] == "UNKNOWN"


def test_invalid_latency_rejected():
    """Invalid latency values must raise ValueError."""
    import pytest
    feed = MetricsFeed()
    for bad in (-1, float("nan"), float("inf"), True):
        with pytest.raises(ValueError):
            feed.record_event(latency=bad)


# ---------------------------------------------------------------------------
# Manual runner (no pytest needed)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_error_rate_calculation()
    test_latency_tracking()
    test_snapshot()
    test_empty_error_rate_is_none()
    test_empty_latency_is_none()
    test_empty_snapshot_status_is_unknown()
    print("\nAll rule tests passed")
