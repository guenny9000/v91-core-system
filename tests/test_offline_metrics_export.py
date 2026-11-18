"""Tests for controller/offline_metrics_export.py (Issue #94).

Honest-status contract: UNKNOWN != MEASURED, zero is never fabricated,
chain claims only from real verification, HTML escaped in context.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from offline_metrics_export import (
    DEFAULT_BIND_ADDRESS,
    MetricsExportError,
    build_export,
    chain_integrity,
    read_ledger_entries,
    render_html_report,
    render_prometheus,
    resolve_kpis,
    validate_bind_address,
)
from measurement_store import MeasurementStore

KEY = b"x" * 32
NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)


def _entry(sensor: str, metric: str, value, minutes_ago: float = 0, **extra) -> dict:
    record = {
        "record_type": "MEASUREMENT_VALID",
        "sensor_id": sensor,
        "metric": metric,
        "normalized_value": value,
        "unit": "W",
        "source_time_utc": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
        "source": "test",
    }
    record.update(extra)
    return record


class BindAddressTests(unittest.TestCase):
    def test_default_is_loopback(self) -> None:
        self.assertEqual(validate_bind_address(), DEFAULT_BIND_ADDRESS)
        self.assertEqual(validate_bind_address(None), "127.0.0.1")

    def test_wildcard_refused_without_opt_in(self) -> None:
        with self.assertRaises(MetricsExportError):
            validate_bind_address("0.0.0.0")
        with self.assertRaises(MetricsExportError):
            validate_bind_address("192.168.1.10")
        self.assertEqual(validate_bind_address("0.0.0.0", allow_non_loopback=True), "0.0.0.0")

    def test_garbage_refused(self) -> None:
        for bad in ("", "not-an-ip", "localhost"):
            with self.assertRaises(MetricsExportError):
                validate_bind_address(bad)


class ResolveKpiTests(unittest.TestCase):
    def test_measured_value(self) -> None:
        kpis = resolve_kpis([_entry("s1", "load", 123.5)], now_utc=NOW)
        self.assertEqual(kpis["s1.load"]["status"], "MEASURED")
        self.assertEqual(kpis["s1.load"]["value"], 123.5)

    def test_missing_value_is_unknown_not_zero(self) -> None:
        kpis = resolve_kpis([_entry("s1", "load", None)], now_utc=NOW)
        self.assertEqual(kpis["s1.load"]["status"], "UNKNOWN")
        self.assertIsNone(kpis["s1.load"]["value"])

    def test_non_finite_and_bool_are_unknown(self) -> None:
        for bad in (float("nan"), float("inf"), True, "123"):
            kpis = resolve_kpis([_entry("s1", "load", bad)], now_utc=NOW)
            self.assertEqual(kpis["s1.load"]["status"], "UNKNOWN", msg=f"bad={bad!r}")

    def test_stale_is_unknown(self) -> None:
        kpis = resolve_kpis([_entry("s1", "load", 5.0, minutes_ago=30)], now_utc=NOW, staleness_seconds=900)
        self.assertEqual(kpis["s1.load"]["status"], "UNKNOWN")
        self.assertIn("stale", kpis["s1.load"]["reason"])

    def test_future_timestamp_is_unknown(self) -> None:
        future = _entry("s1", "load", 5.0, minutes_ago=-60)
        kpis = resolve_kpis([future], now_utc=NOW)
        self.assertEqual(kpis["s1.load"]["status"], "UNKNOWN")

    def test_quarantine_never_contributes(self) -> None:
        q = {"record_type": "MEASUREMENT_QUARANTINE", "sensor_id": "s1", "metric": "load",
             "normalized_value": 99.0, "source_time_utc": NOW.isoformat()}
        self.assertEqual(resolve_kpis([q], now_utc=NOW), {})

    def test_latest_wins(self) -> None:
        kpis = resolve_kpis([_entry("s1", "load", 1.0, minutes_ago=10), _entry("s1", "load", 2.0, minutes_ago=5)], now_utc=NOW)
        self.assertEqual(kpis["s1.load"]["value"], 2.0)


class LedgerReadingTests(unittest.TestCase):
    def test_unparseable_lines_counted_not_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            path.write_text('{"a": 1}\n{{{ not json\n[1,2,3]\n', encoding="utf-8")
            entries, skipped = read_ledger_entries(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(skipped, 2)

    def test_chain_unknown_without_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            store = MeasurementStore(path, key=KEY)
            store.record_valid(sensor_id="s1", metric="load", normalized_value=5.0,
                               unit="W", timestamp_utc=NOW.isoformat())
            old = os.environ.pop("V91_MEASUREMENT_STORE_KEY", None)
            try:
                result = chain_integrity(path)
                self.assertIsNone(result["chain_verified"])
                self.assertIn("UNKNOWN", result["reason"])
            finally:
                if old is not None:
                    os.environ["V91_MEASUREMENT_STORE_KEY"] = old
            result = chain_integrity(path)
            # With an explicit key via env we can also verify positively.
            os.environ["V91_MEASUREMENT_STORE_KEY"] = KEY.decode()
            try:
                result = chain_integrity(path)
                self.assertTrue(result["chain_verified"])
            finally:
                os.environ.pop("V91_MEASUREMENT_STORE_KEY", None)
                if old is not None:
                    os.environ["V91_MEASUREMENT_STORE_KEY"] = old

    def test_chain_failed_on_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            store = MeasurementStore(path, key=KEY)
            store.record_valid(sensor_id="s1", metric="load", normalized_value=5.0,
                               unit="W", timestamp_utc=NOW.isoformat())
            lines = path.read_text(encoding="utf-8").splitlines()
            record = json.loads(lines[0])
            record["normalized_value"] = 999.0
            lines[0] = json.dumps(record, sort_keys=True, ensure_ascii=False)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = chain_integrity(path)
            self.assertFalse(result["chain_verified"])


class RenderTests(unittest.TestCase):
    def test_prometheus_never_emits_fake_values(self) -> None:
        text = render_prometheus({
            "s1.load": {"status": "MEASURED", "value": 42.0},
            "s2.solar": {"status": "UNKNOWN", "value": None},
        })
        self.assertIn('v91_kpi_value{kpi="s1.load"} 42.0', text)
        self.assertIn('v91_kpi_unknown{kpi="s2.solar"} 1', text)
        self.assertNotIn("s2.solar} 0", text.replace("v91_kpi_unknown{kpi=", ""))
        self.assertIn("v91_kpi_unknown_total 1", text)

    def test_html_escapes_values(self) -> None:
        report = render_html_report(
            title="<script>alert(1)</script>",
            kpis={"s1.<b>load</b>": {"status": "MEASURED", "value": 1.0, "unit": "<u>"}},
            chain={"chain_verified": None, "entries": 0},
        )
        self.assertNotIn("<script>alert(1)", report)
        self.assertNotIn("<b>load</b>", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertIn("UNKNOWN", report)

    def test_html_shows_skipped_and_no_claims(self) -> None:
        report = render_html_report(
            title="Report",
            kpis={},
            chain={"chain_verified": None, "entries": 3},
            skipped_lines=2,
        )
        self.assertIn("Unlesbare Zeilen: 2", report)
        self.assertNotIn("physischer Test nachgewiesen", report)
        self.assertNotIn("bestanden", report)
        self.assertIn("UNKNOWN", report)

    def test_empty_title_refused(self) -> None:
        with self.assertRaises(MetricsExportError):
            render_html_report(title="  ", kpis={}, chain={})


class BuildExportTests(unittest.TestCase):
    def test_end_to_end_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            store = MeasurementStore(path, key=KEY)
            store.record_valid(sensor_id="s1", metric="load", normalized_value=300.0,
                               unit="W", timestamp_utc=NOW.isoformat())
            snapshot = build_export(path, now_utc=NOW)
            self.assertEqual(snapshot["kpis"]["s1.load"]["status"], "MEASURED")
            self.assertEqual(snapshot["skipped_lines"], 0)
            self.assertIn("v91_kpi_value", snapshot["prometheus"])


if __name__ == "__main__":
    unittest.main()
