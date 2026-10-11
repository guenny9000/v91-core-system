#!/usr/bin/env python3
"""
Anomaly Detector – sliding-window z-score detection.

A candidate is compared with the prior baseline, then added to the window.
Invalid or non-finite values are ignored and do not contaminate the baseline.
"""

from collections import deque
from math import isfinite
from statistics import mean, stdev


class AnomalyDetector:
    def __init__(self, window_size=20, z_threshold=2.5):
        if window_size < 5:
            raise ValueError("window_size must be at least 5")
        if z_threshold <= 0:
            raise ValueError("z_threshold must be positive")

        self.window_size = window_size
        self.z_threshold = z_threshold
        self.windows = {
            "latency": deque(maxlen=window_size),
            "errors": deque(maxlen=window_size),
            "events": deque(maxlen=window_size),
        }

    def detect(self, metric_type, value):
        """Return True when value is anomalous relative to prior observations."""
        if metric_type not in self.windows:
            return False

        try:
            candidate = float(value)
        except (TypeError, ValueError):
            return False
        if not isfinite(candidate):
            return False

        window = self.windows[metric_type]
        is_anomaly = False

        # Compare against historical values before adding the candidate.
        if len(window) >= 5:
            values = list(window)
            baseline_mean = mean(values)
            baseline_stdev = stdev(values)
            if baseline_stdev == 0:
                is_anomaly = candidate != baseline_mean
            else:
                z_score = (candidate - baseline_mean) / baseline_stdev
                is_anomaly = abs(z_score) > self.z_threshold

        window.append(candidate)
        return is_anomaly

    def get_stats(self, metric_type):
        """Get current statistics for a metric type."""
        if metric_type not in self.windows:
            return None

        values = list(self.windows[metric_type])
        if not values:
            return {"count": 0, "mean": 0, "stdev": 0, "min": None, "max": None}

        return {
            "count": len(values),
            "mean": mean(values),
            "stdev": stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
        }
