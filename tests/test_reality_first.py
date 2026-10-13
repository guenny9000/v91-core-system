"""Regression tests for V91 reality-first safety properties."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))
from controller import ControlPlane


def test_invalid_metrics_are_rejected():
    cp = ControlPlane()
    for values in [
        (True, 0, 10),
        (-1, 0, 10),
        (float("nan"), 0, 10),
        (float("inf"), 0, 10),
        (100, 11, 10),
        (100, 1.5, 10),
    ]:
        try:
            cp.ingest_metric(*values)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid metrics accepted: {values}")
    assert len(cp.metrics_history) == 0


def test_unknown_action_is_blocked_without_side_effects():
    cp = ControlPlane()
    before_action = cp.last_action
    result = cp.execute_action("run_arbitrary_shell_command")
    assert result == {
        "status": "BLOCKED_UNKNOWN_ACTION",
        "action": "run_arbitrary_shell_command",
        "side_effects": False,
    }
    assert cp.last_action == before_action


def test_known_action_is_recommendation_only():
    cp = ControlPlane()
    result = cp.execute_action("reduce_load")
    assert result["status"] == "RECOMMENDATION_ONLY"
    assert result["side_effects"] is False
    assert cp.last_action == "reduce_load"


def test_no_action_has_no_side_effects():
    cp = ControlPlane()
    result = cp.execute_action(None)
    assert result["status"] == "NO_ACTION"
    assert result["side_effects"] is False
    assert cp.last_action is None


def test_valid_metrics_are_recorded_and_returned():
    cp = ControlPlane()
    metric = cp.ingest_metric(125.5, 2, 20)
    assert metric["latency"] == 125.5
    assert metric["errors"] == 2.0
    assert metric["events"] == 20.0
    assert len(cp.metrics_history) == 1
