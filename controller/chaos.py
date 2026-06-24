#!/usr/bin/env python3
"""
Chaos Mode – Controlled Fault Injection for Resilience Testing
"""

import random
import time

class ChaosSimulator:
    def __init__(self, failure_rate=0.1):
        self.failure_rate = failure_rate
        self.failures_injected = 0
        self.recoveries = 0

    def should_fail(self):
        """Determine if we should inject a failure."""
        return random.random() < self.failure_rate

    def inject_failure(self):
        """Simulate a failure."""
        self.failures_injected += 1
        raise Exception(f"[CHAOS] Injected failure #{self.failures_injected}")

    def simulate_degradation(self, base_latency):
        """Simulate performance degradation."""
        if self.should_fail():
            return base_latency * random.uniform(2, 5)  # 2-5x slowdown
        return base_latency

    def simulate_errors(self, base_error_rate):
        """Simulate error rate increase."""
        if self.should_fail():
            return base_error_rate * random.uniform(2, 10)  # 2-10x error increase
        return base_error_rate

    def record_recovery(self):
        """Record a successful recovery from chaos."""
        self.recoveries += 1

    def get_stats(self):
        """Get chaos statistics."""
        return {
            "failures_injected": self.failures_injected,
            "recoveries": self.recoveries,
            "recovery_rate": self.recoveries / max(1, self.failures_injected)
        }
