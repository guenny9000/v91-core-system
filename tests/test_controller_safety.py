#!/usr/bin/env python3
"""Safety regression tests for the V91 simulation-only controller."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from controller import ControlPlane


def test_controller_labels_metrics_as_simulation():
    controller = ControlPlane()
    controller.ingest_metric(latency=100, errors=0, events=20)

    assert controller.metrics_mode == "SIMULATION"
    assert controller.metrics_history[-1]["source"] == "SIMULATION"


def test_action_is_proposal_not_execution(capsys):
    controller = ControlPlane()

    result = controller.execute_action("scale_up_workers")

    assert result is False
    assert controller.last_action == "scale_up_workers"
    assert controller.last_action_status == "SIMULATED_NOT_EXECUTED"
    assert "not executed" in capsys.readouterr().out


def test_unknown_action_is_rejected(capsys):
    controller = ControlPlane()

    result = controller.execute_action("delete_everything")

    assert result is False
    assert controller.last_action is None
    assert controller.last_action_status == "REJECTED_UNKNOWN_ACTION"
    assert "rejected" in capsys.readouterr().out
