"""CLI regression tests for the operator-facing two-node status demo."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "two_node_status_demo.py"


def test_two_node_demo_waits_for_each_bidirectional_cycle() -> None:
    result = subprocess.run(
        [sys.executable, str(DEMO), "--cycles", "2"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "node-alpha -> VERIFIED_RECORDED" in result.stdout
    assert "node-beta -> VERIFIED_RECORDED" in result.stdout
    assert "verified_observations = 2" in result.stdout
    assert "global status     = REFUSED: no complete, time-consistent evidence base" in result.stdout
    assert "demo finished cleanly" in result.stdout


def test_two_node_demo_rejects_zero_cycles() -> None:
    result = subprocess.run(
        [sys.executable, str(DEMO), "--cycles", "0"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert "--cycles must be at least 1" in result.stderr
