#!/usr/bin/env python3
"""Reality-first V91 control-plane prototype.

This module is deliberately safe by default:
- no fabricated metrics are treated as real observations;
- simulation must be explicitly requested;
- control actions never invoke Docker, a shell, or external services;
- missing/invalid measurements fail closed.

A production metrics adapter and an independently reviewed action adapter are
not implemented here. Do not describe this prototype as production-ready.
"""
from __future__ import annotations

import math
import os
import random
import time
from collections import deque
from statistics import mean
from typing import Any

from anomaly import AnomalyDetector
from feedback import FeedbackLoop
from metrics import MetricsFeed


class ControlPlane:
    def __init__(self, history_size: int = 100):
        if history_size < 5:
            raise ValueError("history_size must be at least 5")
        self.anomaly_detector = AnomalyDetector()
        self.metrics_feed = MetricsFeed()
        self.feedback_loop = FeedbackLoop()
        self.metrics_history: deque[dict[str, float]] = deque(maxlen=history_size)
        self.last_action: str | None = None
        self.last_decision_status = "NO_DATA_AVAILABLE"

    @staticmethod
    def _validate_metric(latency: Any, errors: Any, events: Any) -> tuple[float, float, float]:
        values = (latency, errors, events)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
            raise ValueError("metrics must be numeric values, not booleans or strings")
        latency_f, errors_f, events_f = map(float, values)
        if not all(math.isfinite(value) for value in (latency_f, errors_f, events_f)):
            raise ValueError("metrics must be finite")
        if latency_f < 0 or errors_f < 0 or events_f < 0:
            raise ValueError("metrics must not be negative")
        if not errors_f.is_integer() or not events_f.is_integer():
            raise ValueError("errors and events must be whole numbers")
        if errors_f > events_f:
            raise ValueError("errors cannot exceed events")
        return latency_f, errors_f, events_f

    def ingest_metric(self, latency: float, errors: int, events: int) -> dict[str, float]:
        """Accept one validated observation; caller is responsible for its provenance."""
        latency_f, errors_f, events_f = self._validate_metric(latency, errors, events)
        metric = {
            "timestamp": time.time(),
            "latency": latency_f,
            "errors": errors_f,
            "events": events_f,
        }
        self.metrics_history.append(metric)
        self.metrics_feed.record_event(latency_f, error=(errors_f > 0))
        self.last_decision_status = "DOCUMENTED_INPUT"
        return metric.copy()

    def evaluate_rules(self) -> str | None:
        """Return a recommendation only after enough valid observations exist."""
        if len(self.metrics_history) < 5:
            self.last_decision_status = "NO_DATA_AVAILABLE"
            return None

        recent = list(self.metrics_history)[-5:]
        avg_latency = mean(m["latency"] for m in recent)
        avg_errors = mean(m["errors"] for m in recent)
        avg_events = mean(m["events"] for m in recent)

        latency_anomaly = self.anomaly_detector.detect("latency", avg_latency)
        error_anomaly = self.anomaly_detector.detect("errors", avg_errors)

        # Recommendations only: no infrastructure changes are performed here.
        if error_anomaly and avg_errors > 5:
            decision = "reduce_load"
        elif latency_anomaly and avg_latency > 200:
            decision = "review_capacity"
        elif avg_events < 10 and not error_anomaly:
            decision = "review_low_traffic"
        elif avg_latency < 50 and avg_errors == 0:
            decision = "review_resource_saving"
        else:
            decision = None

        self.last_decision_status = "DECISION_RECORDED"
        return decision

    def execute_action(self, action: str | None) -> dict[str, Any]:
        """Record a recommendation without executing external side effects."""
        allowed_recommendations = {
            "reduce_load",
            "review_capacity",
            "review_low_traffic",
            "review_resource_saving",
        }
        if action is None:
            return {"status": "NO_ACTION", "action": None, "side_effects": False}
        if action not in allowed_recommendations:
            return {
                "status": "BLOCKED_UNKNOWN_ACTION",
                "action": action,
                "side_effects": False,
            }
        self.last_action = action
        self.feedback_loop.record_action(action)
        return {
            "status": "RECOMMENDATION_ONLY",
            "action": action,
            "side_effects": False,
        }

    def run_simulation(self, iterations: int = 10, interval_seconds: float = 0.0) -> None:
        """Run a finite, explicitly requested demo using clearly labelled synthetic data."""
        if iterations < 1 or iterations > 1000:
            raise ValueError("iterations must be between 1 and 1000")
        if interval_seconds < 0 or not math.isfinite(interval_seconds):
            raise ValueError("interval_seconds must be finite and non-negative")

        print("[V91] MODE=SIMULATION; synthetic metrics are not real system measurements.")
        for index in range(1, iterations + 1):
            latency = random.uniform(50, 300)
            events = random.randint(5, 100)
            errors = random.randint(0, min(10, events))
            self.ingest_metric(latency, errors, events)
            recommendation = self.evaluate_rules()
            result = self.execute_action(recommendation)
            print(
                f"[SIM {index}/{iterations}] latency_ms={latency:.1f} "
                f"errors={errors} events={events} "
                f"decision={result['status']} recommendation={recommendation}"
            )
            if interval_seconds:
                time.sleep(interval_seconds)

    def run(self) -> None:
        """Fail closed: a real metrics adapter is not included in this repository."""
        mode = os.getenv("V91_MODE", "safe").strip().lower()
        if mode != "simulation":
            raise RuntimeError(
                "V91 stopped safely: no real metrics adapter is configured. "
                "For a finite demo only, set V91_MODE=simulation."
            )
        iterations = int(os.getenv("V91_SIMULATION_ITERATIONS", "10"))
        interval = float(os.getenv("V91_SIMULATION_INTERVAL_SECONDS", "0"))
        self.run_simulation(iterations=iterations, interval_seconds=interval)


if __name__ == "__main__":
    ControlPlane().run()
