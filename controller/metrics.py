#!/usr/bin/env python3
"""In-memory application metrics with explicit missing-data semantics.

This module does not collect host telemetry. Call record_event() only when the
application has an actual event and a measured latency value.
"""
from __future__ import annotations

import math
import time
from collections import deque
from typing import Any


class MetricsFeed:
    def __init__(self, max_history: int = 1000) -> None:
        if isinstance(max_history, bool) or not isinstance(max_history, int) or max_history < 1:
            raise ValueError("max_history must be a positive integer")
        self.events = 0
        self.errors = 0
        self.latency: float | None = None
        self.history: deque[dict[str, Any]] = deque(maxlen=max_history)
        self.start_time = time.time()

    def record_event(self, latency: float, error: bool = False) -> None:
        if isinstance(latency, bool) or not isinstance(latency, (int, float)):
            raise ValueError("latency must be a finite non-negative number")
        value = float(latency)
        if not math.isfinite(value) or value < 0:
            raise ValueError("latency must be a finite non-negative number")
        if not isinstance(error, bool):
            raise ValueError("error must be a boolean")

        now = time.time()
        self.events += 1
        self.latency = value
        if error:
            self.errors += 1
        self.history.append({"timestamp": now, "latency": value, "error": error})

    def snapshot(self) -> dict[str, Any]:
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
        """Return None until at least one real application event is recorded."""
        if self.events == 0:
            return None
        return self.errors / self.events

    def get_recent_average_latency(self, window: int = 10) -> float | None:
        """Return None when no latency samples exist; reject invalid windows."""
        if isinstance(window, bool) or not isinstance(window, int) or window < 1:
            raise ValueError("window must be a positive integer")
        if not self.history:
            return None
        recent = list(self.history)[-window:]
        return sum(item["latency"] for item in recent) / len(recent)
