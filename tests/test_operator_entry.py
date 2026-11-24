#!/usr/bin/env python3
"""Tests for controller/operator_entry.py (Issue #101 zero-code entry +
foreign import through the shared ingest/store chain). Stdlib only."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from controller.measurement_store import MeasurementStore, MeasurementStoreError
from controller.operator_entry import (
    DEFAULT_SOURCE,
    OperatorEntryError,
    import_foreign_file,
    record_measurement,
)

KEY = b"unit-test-store-key-0123456789abcdef"


class OperatorEntryTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.store = MeasurementStore(self.dir / "measurements.jsonl", key=KEY)

    def tearDown(self) -> None:
        for handle in self.dir.iterdir():
            handle.unlink()
        self.dir.rmdir()

    def record(self, **overrides):
        kwargs = dict(
            store=self.store,
            sensor_id="VB-Alsfeld-01",
            metric="grundlast",
            value=142.5,
            unit="watt",
            minimum=0.0,
            maximum=100000.0,
        )
        kwargs.update(overrides)
        return record_measurement(**kwargs)

    def entries(self):
        text = (self.dir / "measurements.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line]

    def write_foreign(self, payload) -> Path:
        path = self.dir / "fremd.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path


class RecordTests(OperatorEntryTestBase):
    def test_record_valid_measurement(self) -> None:
        result = self.record(timestamp="2026-11-18T19:00:00+01:00")
        self.assertEqual(result["status"], "RECORDED")
        self.assertEqual(
            result["warnings"],
            ["calibration reference missing; measurement validity does not establish calibration"],
        )
        self.assertTrue(self.store.verify_chain())
        self.assertEqual(self.store.count(), 1)
        entry = self.entries()[0]
        self.assertEqual(entry["record_type"], "MEASUREMENT_VALID")
        self.assertEqual(entry["sensor_id"], "VB-Alsfeld-01")
        self.assertEqual(entry["normalized_value"], 142.5)
        self.assertEqual(entry["source"], DEFAULT_SOURCE)
        # tz-aware input normalisiert auf UTC-Z
        self.assertTrue(entry["source_time_utc"].endswith("Z"))

    def test_record_defaults_to_receive_time(self) -> None:
        result = self.record()
        self.assertEqual(result["status"], "RECORDED")
        self.assertTrue(result["source_time_utc"].endswith("Z"))

    def test_record_honors_declared_timestamp(self) -> None:
        result = self.record(timestamp="2026-11-18T18:30:00+00:00")
        self.assertEqual(result["source_time_utc"], "2026-11-18T18:30:00Z")

    def test_record_refuses_boolean_value(self) -> None:
        result = self.record(value=True)
        self.assertEqual(result["status"], "QUARANTINED")
        self.assertIn("booleans and strings", result["reason"])

    def test_record_refuses_string_value(self) -> None:
        result = self.record(value="142,5")
        self.assertEqual(result["status"], "QUARANTINED")
        self.assertIn("numeric", result["reason"])

    def test_record_refuses_nan(self) -> None:
        result = self.record(value=float("nan"))
        self.assertEqual(result["status"], "QUARANTINED")
        self.assertIn("not finite", result["reason"])

    def test_record_refuses_out_of_range(self) -> None:
        result = self.record(value=200000.0)
        self.assertEqual(result["status"], "QUARANTINED")
        self.assertIn("outside", result["reason"])

    def test_record_refuses_naive_timestamp(self) -> None:
        result = self.record(timestamp="2026-11-18T19:00:00")
        self.assertEqual(result["status"], "QUARANTINED")
        self.assertIn("timezone-naive", result["reason"])

    def test_record_refuses_empty_sensor_id(self) -> None:
        result = self.record(sensor_id="   ")
        self.assertEqual(result["status"], "QUARANTINED")
        self.assertIn("sensor_id", result["reason"])

    def test_quarantine_preserves_raw_verbatim(self) -> None:
        result = self.record(value=-999, timestamp="2026-11-18T19:00:00+01:00")
        self.assertEqual(result["status"], "QUARANTINED")
        self.assertIn("sentinel", result["reason"])
        entry = self.entries()[0]
        self.assertEqual(entry["record_type"], "MEASUREMENT_QUARANTINE")
        self.assertEqual(entry["disposition"], "OPEN")
        self.assertEqual(entry["raw_payload"]["value"], -999)
        self.assertEqual(entry["claimed_source_time"], "2026-11-18T19:00:00+01:00")
        self.assertTrue(self.store.verify_chain())

    def test_record_custom_source_recorded(self) -> None:
        self.record(source="zaehlerfoto-20261118")
        self.assertEqual(self.entries()[0]["source"], "zaehlerfoto-20261118")

    def test_invalid_spec_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.record(minimum=10.0, maximum=1.0)

    def test_corrupt_chain_refuses_append(self) -> None:
        self.record()
        path = self.dir / "measurements.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["normalized_value"] = 1.0
        lines[0] = json.dumps(tampered, sort_keys=True, ensure_ascii=False)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaises(MeasurementStoreError):
            self.record()


class ImportTests(OperatorEntryTestBase):
    def test_import_valid_entries(self) -> None:
        path = self.write_foreign([
            {"sensor_id": "VB-Lauterbach-02", "value": 98.1,
             "timestamp": "2026-11-18T10:00:00+00:00"},
            {"sensor_id": "VB-Schotten-03", "value": 150.9,
             "timestamp": "2026-11-18T11:00:00+00:00"},
        ])
        summary = import_foreign_file(
            store=self.store, path=path, metric="grundlast", unit="watt",
            minimum=0.0, maximum=100000.0, source_tag="lauterbach-2026-11-18")
        self.assertEqual(summary["status"], "IMPORT_COMPLETE")
        self.assertEqual(summary["recorded"], 2)
        self.assertEqual(summary["quarantined"], 0)
        sources = {entry["source"] for entry in self.entries()}
        self.assertEqual(sources, {"import:lauterbach-2026-11-18"})
        self.assertTrue(self.store.verify_chain())

    def test_import_quarantines_bad_entries_without_discarding(self) -> None:
        path = self.write_foreign([
            {"sensor_id": "VB-A-01", "value": 50.0,
             "timestamp": "2026-11-18T10:00:00+00:00"},
            {"sensor_id": "VB-B-02", "value": 999.9,
             "timestamp": "2026-11-18T10:00:00+00:00"},
            {"sensor_id": "", "value": 10.0,
             "timestamp": "2026-11-18T10:00:00+00:00"},
            "not-an-object",
        ])
        summary = import_foreign_file(
            store=self.store, path=path, metric="grundlast", unit="watt",
            minimum=0.0, maximum=100000.0, source_tag="mixed")
        self.assertEqual(summary["recorded"], 1)
        self.assertEqual(summary["quarantined"], 3)
        self.assertEqual(self.store.count(), 4)
        reasons = [entry.get("reason", "") for entry in self.entries()]
        self.assertTrue(any("sentinel" in r or "numeric" in r for r in reasons))
        self.assertTrue(any("not a JSON object" in r for r in reasons))
        self.assertTrue(self.store.verify_chain())

    def test_import_missing_file_refused(self) -> None:
        with self.assertRaises(OperatorEntryError):
            import_foreign_file(
                store=self.store, path=self.dir / "gibt-es-nicht.json",
                metric="grundlast", unit="watt",
                minimum=0.0, maximum=100000.0, source_tag="x")

    def test_import_corrupt_json_refused(self) -> None:
        path = self.dir / "kaputt.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(OperatorEntryError):
            import_foreign_file(
                store=self.store, path=path, metric="grundlast", unit="watt",
                minimum=0.0, maximum=100000.0, source_tag="x")

    def test_import_non_list_refused(self) -> None:
        path = self.write_foreign({"sensor_id": "VB-X", "value": 1.0})
        with self.assertRaises(OperatorEntryError):
            import_foreign_file(
                store=self.store, path=path, metric="grundlast", unit="watt",
                minimum=0.0, maximum=100000.0, source_tag="x")

    def test_import_empty_tag_refused(self) -> None:
        path = self.write_foreign([])
        with self.assertRaises(OperatorEntryError):
            import_foreign_file(
                store=self.store, path=path, metric="grundlast", unit="watt",
                minimum=0.0, maximum=100000.0, source_tag="  ")


if __name__ == "__main__":
    unittest.main()
