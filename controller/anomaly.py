#!/usr/bin/env python3
"""Sliding-window anomaly detection using only prior observations as baseline."""

import math
from collections import deque
from statistics import mean, stdev


class AnomalyDetector:
    def __init__(self, window_size=20, z_threshold=2.5):
        if isinstance(window_size, bool) or not isinstance(window_size, int) or window_size < 2:
            raise ValueError("window_size must be an integer >= 2")
        if isinstance(z_threshold, bool) or not isinstance(z_threshold, (int, float)) or not math.isfinite(z_threshold) or z_threshold <= 0:
            raise ValueError("z_threshold must be a finite positive number")
        self.window_size = window_size
        self.z_threshold = float(z_threshold)
        self.windows = {
            "latency": deque(maxlen=window_size),
            "errors": deque(maxlen=window_size),
            "events": deque(maxlen=window_size),
        }

    def detect(self, metric_type, value):
        """Return True for an outlier relative to the prior window; reject invalid input."""
        if metric_type not in self.windows:
            return False
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("metric value must be a finite number")

        window = self.windows[metric_type]
        anomalous = False
        if len(window) >= 5:
            values = list(window)
            center = mean(values)
            spread = stdev(values)
            if spread == 0:
                anomalous = value != center
            else:
                anomalous = abs((value - center) / spread) > self.z_threshold

        # Add the new observation only after scoring it against the previous baseline.
        window.append(value)
        return anomalous

    def get_stats(self, metric_type):
        """Return statistics for the stored window, or None for an unknown metric."""
        if metric_type not in self.windows:
            return None
        window = self.windows[metric_type]
        if not window:
            return {"count": 0, "mean": 0, "stdev": 0, "min": None, "max": None}
        values = list(window)
        return {
            "count": len(values),
            "mean": mean(values),
            "stdev": stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
        }
