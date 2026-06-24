#!/usr/bin/env python3
"""
Anomaly Detector – Sliding Window + Z-Score based detection
"""

from collections import deque
from statistics import mean, stdev

class AnomalyDetector:
    def __init__(self, window_size=20, z_threshold=2.5):
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.windows = {
            "latency": deque(maxlen=window_size),
            "errors": deque(maxlen=window_size),
            "events": deque(maxlen=window_size)
        }

    def detect(self, metric_type, value):
        """
        Detect if a value is anomalous using z-score.
        Returns True if anomaly detected, False otherwise.
        """
        if metric_type not in self.windows:
            return False

        window = self.windows[metric_type]
        window.append(value)

        if len(window) < 5:
            return False

        values = list(window)
        m = mean(values)
        s = stdev(values) if len(values) > 1 else 1e-9

        z_score = (value - m) / (s + 1e-9)

        return abs(z_score) > self.z_threshold

    def get_stats(self, metric_type):
        """Get current statistics for a metric type."""
        if metric_type not in self.windows:
            return None

        window = self.windows[metric_type]
        if len(window) == 0:
            return {"count": 0, "mean": 0, "stdev": 0}

        values = list(window)
        return {
            "count": len(values),
            "mean": mean(values),
            "stdev": stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values)
        }
