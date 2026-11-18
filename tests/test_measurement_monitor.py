#!/usr/bin/env python3
"""Tests for the measurement ledger monitor (Issue #100 monitoring)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from controller.measurement_monitor import MeasurementMonitor, MeasurementMonitorError
from controller.measurement_store import MeasurementStore

KEY = b"0123456789abcdef0123456789abcdef"  # 32 bytes, test-only


class MeasurementMonitorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "store.jsonl"
        self.store = MeasurementStore(self.path, key=KEY)
        self.monitor = MeasurementMonitor(self.path)

    def report(self, **kwargs):
        base = dict(now_utc="2026-11-18T20:00:00Z", staleness_seconds=900,
                    expected_interval_seconds=900)
        base.update(kwargs)
        return self.monitor.evaluate(**base)

    def test_fresh_sensor(self) -> None:
        self.store.record_valid(sensor_id="s1", metric="water_temp", normalized_value=12.0,
                               unit="celsius", timestamp_utc="2026-11-18T19:50:00Z")
        report = self.report()
        self.assertEqual(report.sensors["s1"].staleness, "FRESH")
        self.assertEqual(report.sensors["s1"].valid_count, 1)
        self.assertEqual(report.sensors["s1"].gap_count, 0)

    def test_stale_sensor(self) -> None:
        self.store.record_valid(sensor_id="s1", metric="water_temp", normalized_value=12.0,
                               unit="celsius", timestamp_utc="2026-11-18T10:00:00Z")
        self.assertEqual(self.report().sensors["s1"].staleness, "STALE")

    def test_sensor_without_valid_records_is_unknown_not_stale(self) -> None:
        self.store.quarantine({"sensor_id": "s9", "value": "abc"}, reason="REJECTED: non-numeric")
        report = self.report()
        self.assertEqual(report.sensors["s9"].staleness, "UNKNOWN")
        self.assertEqual(report.sensors["s9"].quarantine_count, 1)
        self.assertEqual(report.sensors["s9"].valid_count, 0)

    def test_gap_detection_against_explicit_interval(self) -> None:
        self.store.record_valid(sensor_id="s1", metric="water_temp", normalized_value=1.0,
                               unit="celsius", timestamp_utc="2026-11-18T18:00:00Z")
        self.store.record_valid(sensor_id="s1", metric="water_temp", normalized_value=2.0,
                               unit="celsius", timestamp_utc="2026-11-18T19:00:00Z")
        report = self.report()  # expected interval 900 s, actual 3600 s -> 1 gap
        self.assertEqual(report.sensors["s1"].gap_count, 1)

    def test_unusable_timestamp_is_counted_not_silently_ignored(self) -> None:
        record = self.store.record_valid(sensor_id="s2", metric="m", normalized_value=1.0,
                                         unit="u", timestamp_utc="2026-11-18T19:00:00Z")
        record["source_time_utc"] = "not-a-timestamp"
        # Rewrite the ledger line directly to simulate a broken timestamp;
        # HMAC no longer matches, but the monitor must still count it.
        lines = self.path.read_text(encoding="utf-8").splitlines()
        broken = json.loads(lines[0])
        broken["source_time_utc"] = "not-a-timestamp"
        lines[0] = json.dumps(broken, sort_keys=True, ensure_ascii=False)
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = self.report()
        self.assertEqual(report.sensors["s2"].unusable_timestamp_records, 1)
        self.assertEqual(report.sensors["s2"].valid_count, 0)

    def test_chain_status_unknown_without_key(self) -> None:
        self.store.record_valid(sensor_id="s1", metric="m", normalized_value=1.0,
                               unit="u", timestamp_utc="2026-11-18T19:00:00Z")
        self.assertEqual(self.report().chain_verified, "UNKNOWN")

    def test_chain_status_verified_with_key(self) -> None:
        self.store.record_valid(sensor_id="s1", metric="m", normalized_value=1.0,
                               unit="u", timestamp_utc="2026-11-18T19:00:00Z")
        report = self.report(key=KEY)
        self.assertEqual(report.chain_verified, "VERIFIED")

    def test_unparseable_line_raises_alert_count(self) -> None:
        self.store.record_valid(sensor_id="s1", metric="m", normalized_value=1.0,
                               unit="u", timestamp_utc="2026-11-18T19:00:00Z")
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write("{corrupt\n")
        report = self.report()
        self.assertEqual(report.unparseable_lines, 1)
        self.assertTrue(report.integrity_alerts)

    def test_missing_ledger_is_empty_not_an_error(self) -> None:
        report = self.report()
        self.assertEqual(report.total_records, 0)
        self.assertEqual(report.sensors, {})

    def test_fail_closed_on_bad_arguments(self) -> None:
        with self.assertRaises(MeasurementMonitorError):
            self.report(now_utc="18.11.2026")
        with self.assertRaises(MeasurementMonitorError):
            self.report(staleness_seconds=0)
        with self.assertRaises(MeasurementMonitorError):
            self.report(expected_interval_seconds=True)


if __name__ == "__main__":
    unittest.main()
