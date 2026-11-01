#!/usr/bin/env python3
"""
Unit Tests – Anomaly Detector
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'controller'))

from anomaly import AnomalyDetector

def test_anomaly_detection_normal():
    """Test that normal values are not flagged as anomalies."""
    detector = AnomalyDetector()
    for i in range(10):
        result = detector.detect("latency", 100)  # Consistent value
    assert result == False, "Normal values should not be anomalies"
    print("✓ test_anomaly_detection_normal passed")

def test_anomaly_detection_spike():
    """Test that spikes are detected as anomalies."""
    detector = AnomalyDetector(z_threshold=2.0)
    # Create baseline
    for i in range(10):
        detector.detect("latency", 100)
    # Inject spike
    result = detector.detect("latency", 500)
    assert result == True, "Spike should be detected as anomaly"
    print("✓ test_anomaly_detection_spike passed")

def test_anomaly_stats():
    """Test anomaly statistics."""
    detector = AnomalyDetector()
    for i in range(10):
        detector.detect("latency", 100 + i * 5)
    stats = detector.get_stats("latency")
    assert stats["count"] == 10, "Should have 10 data points"
    assert stats["mean"] > 100, "Mean should be > 100"
    print("✓ test_anomaly_stats passed")

if __name__ == "__main__":
    test_anomaly_detection_normal()
    test_anomaly_detection_spike()
    test_anomaly_stats()
    print("\n✓ All anomaly tests passed")
