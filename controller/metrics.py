#!/usr/bin/env python3
"""
Metrics Feed – Aggregates and tracks system metrics.
Missing-data semantics: no events → error_rate is None, latency is None.
"""

import math
import time
from collections import deque
from typing import Any


class MetricsFeed:
    def __init__(self, max_history: int = 1000) -> None:
        if not isinstance(max_history, int) or isinstance(max_history, bool) or max_history < 1:
            raise ValueError("max_history must be a positive integer")
        self.events: int = 0
        self.errors: int = 0
        self.latency: float | None = None
        self.history: deque = deque(maxlen=max_history)
        self.start_time: float = time.time()

    def record_event(self, latency: float, error: bool = False) -> None:
        """Record a single event with a measured latency."""
        if isinstance(latency, bool) or not isinstance(latency, (int, float)):
            raise ValueError("latency must be a finite non-negative number")
        value = float(latency)
        if not math.isfinite(value) or value < 0:
            raise ValueError("latency must be a finite non-negative number")
        if not isinstance(error, bool):
            raise ValueError("error must be a boolean")

        self.events += 1
        self.latency = value
        if error:
            self.errors += 1
        self.history.append({
            "timestamp": time.time(),
            "latency": value,
            "error": error,
        })

    def snapshot(self) -> dict[str, Any]:
        """Return current state snapshot with explicit status fields."""
        return {
            "events": self.events,
            "errors": self.errors,
            "latency": self.latency,
            "latency_status": "DATA_AVAILABLE" if self.latency is not None else "UNKNOWN",
            "error_rate": self.get_error_rate(),
            "error_rate_status": "DATA_AVAILABLE" if self.events else "UNKNOWN",
            "uptime_sec": max(0, int(time.time() - self.start_time)),
        }

    def get_error_rate(self) -> float | None:
        """Error rate = errors / events. Returns None when no events have been recorded."""
        if self.events == 0:
            return None
        return self.errors / self.events

    def get_recent_average_latency(self, window: int = 10) -> float | None:
        """Average latency over the last *window* events. Returns None when no history exists."""
        if not isinstance(window, int) or isinstance(window, bool) or window < 1:
            raise ValueError("window must be a positive integer")
        if not self.history:
            return None
        recent = list(self.history)[-window:]
        return sum(item["latency"] for item in recent) / len(recent)
