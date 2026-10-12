#!/usr/bin/env python3
"""V91 Reality-First control plane.

Safe mode stays running while waiting for real metrics. Simulation is continuous
and explicitly synthetic. No infrastructure actions are triggered by this prototype.
"""
from __future__ import annotations
import math, os, random, time
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
        self.metrics_history = deque(maxlen=history_size)
        self.last_action = None
        self.last_decision_status = "NO_DATA_AVAILABLE"
        self.iteration = 0

    @staticmethod
    def _validate_metric(latency: Any, errors: Any, events: Any):
        values = (latency, errors, events)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
            raise ValueError("metrics must be numeric, not booleans or strings")
        latency, errors, events = map(float, values)
        if not all(math.isfinite(v) and v >= 0 for v in (latency, errors, events)):
            raise ValueError("metrics must be finite and non-negative")
        if not errors.is_integer() or not events.is_integer() or errors > events:
            raise ValueError("errors/events must be whole numbers and errors cannot exceed events")
        return latency, errors, events

    def ingest_metric(self, latency, errors, events):
        latency, errors, events = self._validate_metric(latency, errors, events)
        metric = {"timestamp": time.time(), "latency": latency, "errors": errors, "events": events}
        self.metrics_history.append(metric)
        self.metrics_feed.record_event(latency, error=(errors > 0))
        self.last_decision_status = "DOCUMENTED_INPUT"
        return metric.copy()

    def evaluate_rules(self):
        if len(self.metrics_history) < 5:
            self.last_decision_status = "NO_DATA_AVAILABLE"
            return None
        recent = list(self.metrics_history)[-5:]
        latency = mean(m["latency"] for m in recent)
        errors = mean(m["errors"] for m in recent)
        events = mean(m["events"] for m in recent)
        latency_anomaly = self.anomaly_detector.detect("latency", latency)
        error_anomaly = self.anomaly_detector.detect("errors", errors)
        if error_anomaly is True and errors > 5:
            decision = "reduce_load"
        elif latency_anomaly is True and latency > 200:
            decision = "review_capacity"
        elif events < 10 and error_anomaly is False:
            decision = "review_low_traffic"
        elif latency < 50 and errors == 0 and latency_anomaly is False:
            decision = "review_resource_saving"
        else:
            decision = None
        self.last_decision_status = "DECISION_RECORDED"
        return decision

    def execute_action(self, action):
        """Record a recommendation only; no shell, Docker, or service side effects."""
        allowed = {"reduce_load", "review_capacity", "review_low_traffic", "review_resource_saving"}
        if action is None:
            return {"status": "NO_ACTION", "action": None, "side_effects": False}
        if action not in allowed:
            return {"status": "BLOCKED_UNKNOWN_ACTION", "action": action, "side_effects": False}
        self.last_action = action
        self.feedback_loop.record_action(action)
        return {"status": "RECOMMENDATION_ONLY", "action": action, "side_effects": False}

    def run(self):
        mode = os.getenv("V91_MODE", "safe").strip().lower()
        if mode not in {"safe", "simulation", "live"}:
            raise ValueError("V91_MODE must be safe, simulation, or live")
        if mode == "live":
            raise RuntimeError("Live mode unavailable: no real metrics adapter is implemented.")
        print(f"[V91] SERVICE_STARTED mode={mode}", flush=True)
        if mode == "simulation":
            print("[V91] Synthetic metrics only; not evidence of live hardware.", flush=True)
        while True:
            self.iteration += 1
            if mode == "simulation":
                latency = random.uniform(50, 300)
                events = random.randint(5, 100)
                errors = random.randint(0, min(10, events))
                self.ingest_metric(latency, errors, events)
                action = self.evaluate_rules()
                result = self.execute_action(action)
                strategy = self.feedback_loop.adjust_strategy({"errors": errors, "latency": latency, "events": events})
                if self.iteration % 10 == 0:
                    print(f"[SIM {self.iteration}] synthetic_only=true latency_ms={latency:.1f} errors={errors} events={events} strategy={strategy} status={result['status']} recommendation={action}", flush=True)
            elif self.iteration % 12 == 0:
                self.last_decision_status = "NO_DATA_AVAILABLE"
                print("[V91] STATUS=NO_DATA_AVAILABLE; service remains active; waiting for verified real metrics adapter.", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    ControlPlane().run()
