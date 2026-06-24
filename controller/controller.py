#!/usr/bin/env python3
"""
v91-core-system Controller – Autonomous Control Plane

Main service that:
1. Ingests metrics
2. Detects anomalies (z-score based)
3. Evaluates rules
4. Triggers control actions
5. Maintains feedback loop
"""

import json
import time
import os
from collections import deque
from statistics import mean, stdev

from anomaly import AnomalyDetector
from metrics import MetricsFeed
from feedback import FeedbackLoop

class ControlPlane:
    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.metrics_feed = MetricsFeed()
        self.feedback_loop = FeedbackLoop()
        self.metrics_history = deque(maxlen=100)
        self.last_action = None

    def ingest_metric(self, latency, errors, events):
        """Ingest a metric snapshot."""
        metric = {
            "timestamp": time.time(),
            "latency": latency,
            "errors": errors,
            "events": events
        }
        self.metrics_history.append(metric)
        self.metrics_feed.record_event(latency, error=(errors > 0))

    def evaluate_rules(self):
        """Evaluate control rules based on metrics."""
        if len(self.metrics_history) < 5:
            return None

        recent = list(self.metrics_history)[-5:]
        avg_latency = mean([m["latency"] for m in recent])
        avg_errors = mean([m["errors"] for m in recent])
        avg_events = mean([m["events"] for m in recent])

        # Z-score anomaly detection
        latency_anomaly = self.anomaly_detector.detect("latency", avg_latency)
        error_anomaly = self.anomaly_detector.detect("errors", avg_errors)

        # Rule evaluation
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
        """Execute a control action."""
        if action == "scale_up_workers":
            print("[CONTROL] Scaling up workers...")
            os.system("docker compose up --scale worker=3 -d 2>/dev/null || true")
        elif action == "scale_down_workers":
            print("[CONTROL] Scaling down workers...")
            os.system("docker compose up --scale worker=1 -d 2>/dev/null || true")
        elif action == "activate_chaos_mode":
            print("[CONTROL] Activating chaos mode...")
            os.system("docker compose restart worker 2>/dev/null || true")
        elif action == "conserve_resources":
            print("[CONTROL] System healthy, conserving resources.")

        self.last_action = action
        self.feedback_loop.record_action(action)

    def run(self):
        """Main control loop."""
        print("[CONTROLLER] Starting v91 Control Plane...")
        iteration = 0

        while True:
            iteration += 1

            # Simulate metric generation
            import random
            latency = random.uniform(50, 300)
            errors = random.randint(0, 10)
            events = random.randint(5, 100)

            self.ingest_metric(latency, errors, events)

            # Evaluate and execute
            action = self.evaluate_rules()
            if action:
                self.execute_action(action)

            # Feedback loop adjustment
            strategy = self.feedback_loop.adjust_strategy({
                "errors": errors,
                "latency": latency,
                "events": events
            })

            # Log state
            if iteration % 10 == 0:
                print(
                    f"[ITER {iteration}] Latency: {latency:.1f}ms, "
                    f"Errors: {errors}, Events: {events}, "
                    f"Strategy: {strategy}, Last Action: {self.last_action}"
                )

            time.sleep(5)

if __name__ == "__main__":
    controller = ControlPlane()
    controller.run()
