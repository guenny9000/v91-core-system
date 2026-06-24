#!/usr/bin/env python3
"""
Metrics Feed – Aggregates and tracks system metrics
"""

import time
from collections import deque

class MetricsFeed:
    def __init__(self, max_history=1000):
        self.events = 0
        self.errors = 0
        self.latency = 0
        self.history = deque(maxlen=max_history)
        self.start_time = time.time()

    def record_event(self, latency, error=False):
        """Record a single event."""
        self.events += 1
        self.latency = latency
        if error:
            self.errors += 1

        self.history.append({
            "timestamp": time.time(),
            "latency": latency,
            "error": error
        })

    def snapshot(self):
        """Get current state snapshot."""
        return {
            "events": self.events,
            "errors": self.errors,
            "latency": self.latency,
            "uptime_sec": int(time.time() - self.start_time)
        }

    def get_error_rate(self):
        """Calculate current error rate."""
        if self.events == 0:
            return 0.0
        return self.errors / self.events

    def get_recent_average_latency(self, window=10):
        """Get average latency over recent window."""
        if len(self.history) == 0:
            return 0
        recent = list(self.history)[-window:]
        return sum(h["latency"] for h in recent) / len(recent)
