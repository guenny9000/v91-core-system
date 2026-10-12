#!/usr/bin/env python3
"""Safety regression tests for the V91 control-plane prototype."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))
from controller import ControlPlane


def test_controller_rejects_missing_or_invalid_metrics():
    plane = ControlPlane()
    for args in [
        (-1, 0, 1),
        (float("nan"), 0, 1),
        (100, 2, 1),
        (100, True, 1),
        ("100", 0, 1),
    ]:
        try:
            plane.ingest_metric(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid metrics accepted: {args}")
    assert len(plane.metrics_history) == 0


def test_control_action_is_recommendation_only():
    plane = ControlPlane()
    result = plane.execute_action("review_capacity")
    assert result == {
        "status": "RECOMMENDATION_ONLY",
        "action": "review_capacity",
        "side_effects": False,
    }


def test_unknown_action_is_blocked():
    plane = ControlPlane()
    result = plane.execute_action("restart_everything")
    assert result["status"] == "BLOCKED_UNKNOWN_ACTION"
    assert result["side_effects"] is False


def test_rules_require_minimum_observations():
    plane = ControlPlane()
    assert plane.evaluate_rules() is None
    assert plane.last_decision_status == "NO_DATA_AVAILABLE"


def test_run_refuses_to_claim_live_mode(monkeypatch):
    monkeypatch.delenv("V91_MODE", raising=False)
    try:
        ControlPlane().run()
    except RuntimeError as exc:
        assert "no real metrics adapter" in str(exc)
    else:
        raise AssertionError("controller did not fail closed")
