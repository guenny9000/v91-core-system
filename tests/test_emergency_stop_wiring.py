"""Tests for the emergency-stop runtime wiring (Issue #70, requirement 1).

Proves the controlled end of runtime loops when the stop flag is active:
no crash, no silent exit, fail-closed on unreadable/invalid flags.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import controller
import worker
from emergency_stop import EmergencyStopFlagReader


class FakeStopReader:
    """Deterministic stop-flag reader for tests."""

    def __init__(self, stopped: bool, reason: str) -> None:
        self.flag_path = Path("fake-flag-path")
        self._stopped = stopped
        self._reason = reason

    def is_stopped(self):
        return self._stopped, self._reason


class ControlPlaneWiringTests(unittest.TestCase):
    def test_stopped_flag_ends_loop_controlled(self) -> None:
        plane = controller.ControlPlane(
            stop_reader=FakeStopReader(True, "STOPPED_FLAG_PRESENT")
        )
        result = plane.run(max_iterations=5)
        self.assertEqual(result, "EMERGENCY_STOP")
        # The loop must end BEFORE any further iteration, not after max_iterations.
        self.assertEqual(len(plane.metrics_history), 0)

    def test_running_flag_keeps_loop_until_bound(self) -> None:
        plane = controller.ControlPlane(
            stop_reader=FakeStopReader(False, "RUNNING_NO_FLAG")
        )
        with mock.patch.object(controller.time, "sleep", lambda _s: None):
            result = plane.run(max_iterations=6)
        self.assertEqual(result, "MAX_ITERATIONS")
        self.assertEqual(len(plane.metrics_history), 6)

    def test_unreadable_flag_counts_as_stopped(self) -> None:
        plane = controller.ControlPlane(
            stop_reader=FakeStopReader(True, "STOPPED_FLAG_UNREADABLE_FAIL_CLOSED")
        )
        result = plane.run(max_iterations=5)
        self.assertEqual(result, "EMERGENCY_STOP")

    def test_default_reader_uses_env_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            flag = Path(tmp) / "stop.flag"
            with mock.patch.dict(os.environ, {"V91_EMERGENCY_STOP_FLAG": str(flag)}):
                plane = controller.ControlPlane()
            self.assertEqual(plane.stop_reader.flag_path, flag.resolve())


class WorkerWiringTests(unittest.TestCase):
    def test_emergency_stop_reason_none_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            flag = Path(tmp) / "stop.flag"
            self.assertIsNone(worker.emergency_stop_reason(flag))

    def test_emergency_stop_reason_present_with_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            flag = Path(tmp) / "stop.flag"
            flag.write_text("test stop", encoding="utf-8")
            self.assertEqual(worker.emergency_stop_reason(flag), "STOPPED_FLAG_PRESENT")

    def test_symlink_flag_is_stopped_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.txt"
            target.write_text("x", encoding="utf-8")
            link = Path(tmp) / "stop.flag"
            link.symlink_to(target)
            self.assertEqual(
                worker.emergency_stop_reason(link), "STOPPED_FLAG_INVALID_FAIL_CLOSED"
            )

    def test_worker_main_exits_controlled_with_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flag = root / "stop.flag"
            flag.write_text("test stop", encoding="utf-8")
            with (
                mock.patch.object(worker, "EMERGENCY_STOP_FLAG", flag),
                mock.patch.object(worker, "QUEUE_ROOT", root / "queue"),
                mock.patch.object(worker, "RUNTIME_ROOT", root / "runtime"),
                mock.patch.object(worker, "WORKSPACE_ROOT", root / "workspace"),
            ):
                code = worker.main()
            self.assertEqual(code, 0)
            audit_path = root / "runtime" / "v91-actions.jsonl"
            self.assertTrue(audit_path.exists())
            entries = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            stop_entries = [e for e in entries if e.get("phase") == "EMERGENCY_STOP"]
            self.assertEqual(len(stop_entries), 1)
            self.assertEqual(stop_entries[0]["status"], "CONTROLLED_SHUTDOWN")
            self.assertEqual(stop_entries[0]["stop_reason"], "STOPPED_FLAG_PRESENT")

    def test_reader_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            flag = Path(tmp) / "stop.flag"
            reader = EmergencyStopFlagReader(flag)
            self.assertEqual(reader.is_stopped(), (False, "RUNNING_NO_FLAG"))
            self.assertFalse(flag.exists())


if __name__ == "__main__":
    unittest.main()
