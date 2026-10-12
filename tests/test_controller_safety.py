import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))
from controller import ControlPlane

def test_invalid_metrics_are_rejected():
    plane = ControlPlane()
    for args in [(-1, 0, 1), (float("nan"), 0, 1), (100, 2, 1), (100, True, 1), ("100", 0, 1)]:
        try:
            plane.ingest_metric(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid metrics accepted: {args}")
    assert len(plane.metrics_history) == 0

def test_recommendations_have_no_external_side_effects():
    result = ControlPlane().execute_action("review_capacity")
    assert result == {"status": "RECOMMENDATION_ONLY", "action": "review_capacity", "side_effects": False}

def test_unknown_action_is_blocked():
    result = ControlPlane().execute_action("restart_everything")
    assert result["status"] == "BLOCKED_UNKNOWN_ACTION"
    assert result["side_effects"] is False

def test_insufficient_metrics_are_unknown():
    plane = ControlPlane()
    assert plane.evaluate_rules() is None
    assert plane.last_decision_status == "NO_DATA_AVAILABLE"

def test_live_mode_fails_closed_until_adapter_exists(monkeypatch):
    monkeypatch.setenv("V91_MODE", "live")
    try:
        ControlPlane().run()
    except RuntimeError as exc:
        assert "no real metrics adapter" in str(exc).lower()
    else:
        raise AssertionError("live mode did not fail closed")
