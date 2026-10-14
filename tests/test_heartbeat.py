"""Tests for one-shot heartbeat fail-closed behavior."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import heartbeat
import ledger


class TestHeartbeatCycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = ledger.LEDGER_FILE
        ledger.LEDGER_FILE = Path(self.tmp.name) / "heartbeat.jsonl"

    def tearDown(self):
        ledger.LEDGER_FILE = self.original_path
        self.tmp.cleanup()

    def test_documented_host_metrics_are_audited_but_app_metrics_stay_unknown(self):
        fake = {
            "status": "DOCUMENTED",
            "source": "test.fake_host",
            "timestamp_utc": "2026-01-01T00:00:00+00:00",
            "cpu_percent": 12.0,
            "memory_used_percent": 30.0,
        }
        with patch.object(heartbeat, "collect_host_metrics", return_value=fake):
            result = heartbeat.run_heartbeat_cycle()
        self.assertEqual(result["status"], "HOST_TELEMETRY_DOCUMENTED")
        self.assertTrue(result["ledger_entry_written"])
        self.assertEqual(result["application_metrics"], "NO_DATA_AVAILABLE")
        entry = ledger.LEDGER_FILE.read_text(encoding="utf-8")
        self.assertIn('"application_metrics":"NO_DATA_AVAILABLE"', entry)
        self.assertTrue(ledger.verify_ledger_chain()["valid"])

    def test_missing_metrics_are_not_converted_to_zero_or_healthy(self):
        with patch.object(
            heartbeat, "collect_host_metrics",
            return_value={"status": "NO_DATA_AVAILABLE", "reason": "test_missing"},
        ):
            result = heartbeat.run_heartbeat_cycle()
        self.assertEqual(result["status"], "NO_DATA_AVAILABLE")
        self.assertTrue(result["ledger_entry_written"])
        self.assertEqual(result["application_metrics"], "NO_DATA_AVAILABLE")

    def test_high_cpu_only_warns_and_never_executes_actions(self):
        fake = {
            "status": "DOCUMENTED", "source": "test.fake_host",
            "timestamp_utc": "2026-01-01T00:00:00+00:00",
            "cpu_percent": 95.0, "memory_used_percent": 50.0,
        }
        with patch.object(heartbeat, "collect_host_metrics", return_value=fake):
            result = heartbeat.run_heartbeat_cycle()
        self.assertEqual(result["status"], "WARNING_HIGH_HOST_CPU")
        raw = ledger.LEDGER_FILE.read_text(encoding="utf-8")
        self.assertIn('"infrastructure_actions_executed":false', raw)

    def test_corrupt_ledger_fails_closed_without_claiming_a_new_entry(self):
        ledger.LEDGER_FILE.write_text("not-json\n", encoding="utf-8")
        with patch.object(heartbeat, "collect_host_metrics") as metrics:
            result = heartbeat.run_heartbeat_cycle()
        metrics.assert_not_called()
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertFalse(result["ledger_entry_written"])
        self.assertEqual(ledger.LEDGER_FILE.read_text(encoding="utf-8"), "not-json\n")


if __name__ == "__main__":
    unittest.main()
