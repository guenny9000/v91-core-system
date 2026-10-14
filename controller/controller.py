#!/usr/bin/env python3
"""
V91 Control Plane.

Current operating mode: SIMULATION ONLY.
Metrics are generated locally with random values; they are not live telemetry.
Actions are proposals for observation and are never applied to Docker or the host.
A real metrics adapter and a separately reviewed actuator are required before
real-world control actions can be enabled.
"""

import random
import time
from collections import deque
from statistics import mean

from anomaly import AnomalyDetector
from metrics import MetricsFeed
from feedback import FeedbackLoop


class ControlPlane:
    """Observe synthetic metrics and report proposed actions without side effects."""

    ALLOWED_ACTIONS = {
        "scale_up_workers",
        "scale_down_workers",
        "activate_chaos_mode",
        "conserve_resources",
    }

    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.metrics_feed = MetricsFeed()
        self.feedback_loop = FeedbackLoop()
        self.metrics_history = deque(maxlen=100)
        self.last_action = None
        self.last_action_status = "NO_ACTION"
        self.metrics_mode = "SIMULATION"

    def ingest_metric(self, latency, errors, events):
        """Record one metric snapshot; callers must label its source correctly."""
        metric = {
            "timestamp": time.time(),
            "latency": latency,
            "errors": errors,
            "events": events,
            "source": self.metrics_mode,
        }
        self.metrics_history.append(metric)
        self.metrics_feed.record_event(latency, error=(errors > 0))

    def evaluate_rules(self):
        """Evaluate synthetic metric history and return a proposed action."""
        if len(self.metrics_history) < 5:
            return None

        recent = list(self.metrics_history)[-5:]
        avg_latency = mean([m["latency"] for m in recent])
        avg_errors = mean([m["errors"] for m in recent])
        avg_events = mean([m["events"] for m in recent])

        latency_anomaly = self.anomaly_detector.detect("latency", avg_latency)
        error_anomaly = self.anomaly_detector.detect("errors", avg_errors)

        if latency_anomaly and avg_latency > 200:
            return "scale_up_workers"
        if avg_events < 10 and not error_anomaly:
            return "scale_down_workers"
        if error_anomaly and avg_errors > 5:
            return "activate_chaos_mode"
        if avg_latency < 50 and avg_errors == 0:
            return "conserve_resources"
        return None

    def execute_action(self, action):
        """
        Backward-compatible method name: currently records a proposal only.
        It deliberately does not execute shell commands or change the host.
        """
        if action not in self.ALLOWED_ACTIONS:
            self.last_action = None
            self.last_action_status = "REJECTED_UNKNOWN_ACTION"
            print(f"[SAFETY] Unknown action rejected: {action!r}")
            return False

        self.last_action = action
        self.last_action_status = "SIMULATED_NOT_EXECUTED"
        print(
            f"[SIMULATION] Proposed action: {action}; "
            "not executed (synthetic metrics / no live actuator)."
        )
        return False

    def run(self):
        """Run the simulation loop; no host or Docker actions are performed."""
        print(
            "[CONTROLLER] V91 simulation started. "
            "Metrics source: RANDOM/SIMULATION; control actions disabled."
        )
        iteration = 0

        while True:
            iteration += 1
            latency = random.uniform(50, 300)
            errors = random.randint(0, 10)
            events = random.randint(5, 100)

            self.ingest_metric(latency, errors, events)
            action = self.evaluate_rules()
            if action:
                self.execute_action(action)

            strategy = self.feedback_loop.adjust_strategy({
                "errors": errors,
                "latency": latency,
                "events": events,
            })

            if iteration % 10 == 0:
                print(
                    f"[SIMULATION ITER {iteration}] Latency: {latency:.1f}ms, "
                    f"Errors: {errors}, Events: {events}, Strategy: {strategy}, "
                    f"Proposed action: {self.last_action}, "
                    f"Action status: {self.last_action_status}"
                )

            time.sleep(5)


if __name__ == "__main__":
    ControlPlane().run()
