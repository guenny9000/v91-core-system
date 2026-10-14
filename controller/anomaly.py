#!/usr/bin/env python3
"""Sliding-window anomaly detector using a prior-observation baseline."""
from __future__ import annotations

import math
from collections import deque
from statistics import mean, stdev


class AnomalyDetector:
    def __init__(self, window_size: int = 20, z_threshold: float = 2.5, min_samples: int = 5):
        if window_size < 2:
            raise ValueError("window_size must be at least 2")
        if not math.isfinite(z_threshold) or z_threshold <= 0:
            raise ValueError("z_threshold must be finite and positive")
        if min_samples < 2 or min_samples > window_size:
            raise ValueError("min_samples must be between 2 and window_size")
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.min_samples = min_samples
        self.windows = {
            "latency": deque(maxlen=window_size),
            "errors": deque(maxlen=window_size),
            "events": deque(maxlen=window_size),
        }

    def detect(self, metric_type: str, value: float) -> bool | None:
        """Compare against prior samples, then append the new sample.

        Returns None when there is insufficient baseline data or the metric
        name/value is invalid. None is not equivalent to 'no anomaly'.
        """
        if metric_type not in self.windows:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        value = float(value)
        if not math.isfinite(value):
            return None

        window = self.windows[metric_type]
        anomalous: bool | None = None
        if len(window) >= self.min_samples:
            baseline = list(window)
            center = mean(baseline)
            spread = stdev(baseline)
            if spread == 0:
                anomalous = value != center
            else:
                anomalous = abs((value - center) / spread) > self.z_threshold

        window.append(value)
        return anomalous

    def get_stats(self, metric_type: str) -> dict[str, float | int] | None:
        if metric_type not in self.windows:
            return None
        values = list(self.windows[metric_type])
        if not values:
            return {"count": 0, "mean": 0.0, "stdev": 0.0, "min": 0.0, "max": 0.0}
        return {
            "count": len(values),
            "mean": mean(values),
            "stdev": stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }
