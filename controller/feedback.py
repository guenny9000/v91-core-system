#!/usr/bin/env python3
"""
Feedback Loop – Self-Optimization based on system state
"""

import time

class FeedbackLoop:
    def __init__(self):
        self.strategy = "stable"
        self.strategy_history = []
        self.action_count = 0
        self.last_strategy_change = time.time()

    def record_action(self, action):
        """Record an executed action."""
        self.action_count += 1

    def adjust_strategy(self, metrics):
        """
        Adjust system strategy based on metrics.
        Returns new strategy.
        """
        errors = metrics.get("errors", 0)
        latency = metrics.get("latency", 0)
        events = metrics.get("events", 0)

        # Strategy decision logic
        if errors > 10:
            new_strategy = "reduce_load"
        elif latency > 300:
            new_strategy = "scale_up"
        elif events < 5:
            new_strategy = "conserve_resources"
        else:
            new_strategy = "stable"

        # Record change
        if new_strategy != self.strategy:
            self.strategy = new_strategy
            self.last_strategy_change = time.time()
            self.strategy_history.append({
                "timestamp": time.time(),
                "strategy": new_strategy
            })

        return self.strategy

    def get_optimization_score(self):
        """Calculate optimization effectiveness."""
        if self.action_count == 0:
            return 0.0
        return min(1.0, (100 - len(self.strategy_history)) / 100.0)

    def get_strategy_history(self):
        """Get strategy change history."""
        return self.strategy_history
