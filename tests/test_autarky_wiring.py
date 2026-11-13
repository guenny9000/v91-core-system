"""Tests: main.py autarky wiring (Issue #83 Phase 2)."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as main_module
from controller.measurement_core import append_snapshot, metric


def make_snapshot(solar, grid):
    return {
        "schema": "v91.measurement.v1",
        "event_id": "wiring-test",
        "measured_at_utc": "2026-11-13T12:00:00.000Z",
        "collection_mode": "READ_ONLY",
        "host_measurements": {
            "solar_w": metric(solar, "W", "test_meter"),
            "grid_w": metric(grid, "W", "test_meter"),
        },
    }


class MainAutarkyWiringTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.tmp.name) / "config"
        self.config_dir.mkdir()
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"
        self._orig_registry = main_module.build_registry_from_config
        self._orig_run_once = main_module.run_once
        main_module.build_registry_from_config = lambda cfg_dir: object()
        main_module.run_once = lambda registry, max_cycles, interval_seconds: {"aggregate": "OK"}

    def tearDown(self):
        main_module.build_registry_from_config = self._orig_registry
        main_module.run_once = self._orig_run_once
        self.tmp.cleanup()

    def test_report_attached_after_cycle(self):
        append_snapshot(self.ledger, make_snapshot(300, 100))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main_module.main(["--config-dir", str(self.config_dir),
                                     "--autarky-ledger", str(self.ledger)])
        self.assertEqual(code, 0)
        result = json.loads(buffer.getvalue())
        self.assertEqual(result["autarky"]["energy_autarky"]["status"], "MEASURED")
        self.assertEqual(result["autarky"]["energy_autarky"]["self_sufficiency_share"], 0.75)

    def test_no_flag_no_report(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main_module.main(["--config-dir", str(self.config_dir)])
        self.assertEqual(code, 0)
        self.assertNotIn("autarky", json.loads(buffer.getvalue()))

    def test_broken_ledger_is_visible_not_fatal(self):
        self.ledger.write_text("garbage\n", encoding="utf-8")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main_module.main(["--config-dir", str(self.config_dir),
                                     "--autarky-ledger", str(self.ledger)])
        self.assertEqual(code, 0)
        result = json.loads(buffer.getvalue())
        self.assertEqual(result["autarky"]["status"], "ERROR")
        self.assertIn("error", result["autarky"])

    def test_stop_flag_still_wins_before_report(self):
        flag = Path(self.tmp.name) / "stop.flag"
        flag.write_text("{}", encoding="utf-8")
        append_snapshot(self.ledger, make_snapshot(1, 1))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main_module.main(["--config-dir", str(self.config_dir),
                                     "--stop-flag", str(flag),
                                     "--autarky-ledger", str(self.ledger)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(buffer.getvalue())["status"], "EMERGENCY_STOPPED")


if __name__ == "__main__":
    unittest.main()
