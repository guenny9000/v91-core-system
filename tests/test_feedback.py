#!/usr/bin/env python3
"""
Unit Tests – Feedback Loop
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'controller'))

from feedback import FeedbackLoop

def test_strategy_adjustment_high_errors():
    """Test strategy adjustment with high errors."""
    loop = FeedbackLoop()
    strategy = loop.adjust_strategy({
        "errors": 15,
        "latency": 100,
        "events": 50
    })
    assert strategy == "reduce_load", f"Expected 'reduce_load', got '{strategy}'"
    print("✓ test_strategy_adjustment_high_errors passed")

def test_strategy_adjustment_high_latency():
    """Test strategy adjustment with high latency."""
    loop = FeedbackLoop()
    strategy = loop.adjust_strategy({
        "errors": 2,
        "latency": 400,
        "events": 50
    })
    assert strategy == "scale_up", f"Expected 'scale_up', got '{strategy}'"
    print("✓ test_strategy_adjustment_high_latency passed")

def test_strategy_adjustment_stable():
    """Test strategy adjustment in stable state."""
    loop = FeedbackLoop()
    strategy = loop.adjust_strategy({
        "errors": 1,
        "latency": 100,
        "events": 50
    })
    assert strategy == "stable", f"Expected 'stable', got '{strategy}'"
    print("✓ test_strategy_adjustment_stable passed")

def test_strategy_history():
    """Test strategy change history tracking."""
    loop = FeedbackLoop()
    loop.adjust_strategy({"errors": 15, "latency": 100, "events": 50})
    loop.adjust_strategy({"errors": 1, "latency": 100, "events": 50})
    history = loop.get_strategy_history()
    assert len(history) >= 1, "Should have strategy history"
    print("✓ test_strategy_history passed")

if __name__ == "__main__":
    test_strategy_adjustment_high_errors()
    test_strategy_adjustment_high_latency()
    test_strategy_adjustment_stable()
    test_strategy_history()
    print("\n✓ All feedback tests passed")
