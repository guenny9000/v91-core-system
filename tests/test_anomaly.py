#!/usr/bin/env python3
"""Unit tests for the V91 anomaly detector."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from anomaly import AnomalyDetector


def test_anomaly_detection_normal():
    detector = AnomalyDetector()
    results = [detector.detect("latency", 100) for _ in range(10)]
    assert not any(results)


def test_anomaly_detection_spike_uses_prior_baseline():
    detector = AnomalyDetector(z_threshold=2.0)
    for _ in range(10):
        assert detector.detect("latency", 100) is False
    assert detector.detect("latency", 500) is True


def test_anomaly_candidate_is_still_recorded():
    detector = AnomalyDetector(z_threshold=2.0)
    for _ in range(5):
        detector.detect("latency", 100)
    detector.detect("latency", 500)
    stats = detector.get_stats("latency")
    assert stats["count"] == 6
    assert stats["max"] == 500


def test_zero_variance_baseline_detects_different_value():
    detector = AnomalyDetector()
    for _ in range(5):
        detector.detect("errors", 0)
    assert detector.detect("errors", 1) is True


def test_unknown_or_invalid_values_do_not_poison_baseline():
    detector = AnomalyDetector()
    for _ in range(5):
        detector.detect("events", 10)
    assert detector.detect("unknown_metric", 999) is False
    assert detector.detect("events", float("nan")) is False
    assert detector.get_stats("events")["count"] == 5


def test_anomaly_stats():
    detector = AnomalyDetector()
    for value in range(100, 150, 5):
        detector.detect("latency", value)
    stats = detector.get_stats("latency")
    assert stats["count"] == 10
    assert stats["mean"] > 100
