#!/usr/bin/env python3
"""
Unit Tests – Rule Engine
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'controller'))

from metrics import MetricsFeed

def test_error_rate_calculation():
    """Test error rate calculation."""
    feed = MetricsFeed()
    for i in range(10):
        feed.record_event(latency=100, error=(i % 2 == 0))
    error_rate = feed.get_error_rate()
    assert error_rate == 0.5, f"Error rate should be 0.5, got {error_rate}"
    print("✓ test_error_rate_calculation passed")

def test_latency_tracking():
    """Test latency tracking."""
    feed = MetricsFeed()
    latencies = [100, 150, 120, 110, 130]
    for lat in latencies:
        feed.record_event(latency=lat, error=False)
    avg = feed.get_recent_average_latency(window=5)
    expected = sum(latencies) / len(latencies)
    assert abs(avg - expected) < 1, f"Average latency mismatch: {avg} vs {expected}"
    print("✓ test_latency_tracking passed")

def test_snapshot():
    """Test metrics snapshot."""
    feed = MetricsFeed()
    feed.record_event(latency=100, error=False)
    feed.record_event(latency=200, error=True)
    snapshot = feed.snapshot()
    assert snapshot["events"] == 2, "Should have 2 events"
    assert snapshot["errors"] == 1, "Should have 1 error"
    print("✓ test_snapshot passed")

if __name__ == "__main__":
    test_error_rate_calculation()
    test_latency_tracking()
    test_snapshot()
    print("\n✓ All rule tests passed")
