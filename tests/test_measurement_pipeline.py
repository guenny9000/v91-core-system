#!/usr/bin/env python3
"""Tests for the canonical measurement pipeline (consolidation, Issue #100)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from controller.measurement_ingest import MeasurementStatus, RawMeasurement, SensorSpec
from controller.measurement_pipeline import MeasurementPipeline, MeasurementPipelineError
from controller.measurement_store import MeasurementStore, MeasurementStoreError

KEY = b"0123456789abcdef0123456789abcdef"  # 32 bytes, test-only


def spec() -> SensorSpec:
    return SensorSpec(metric="water_temp", unit="celsius", minimum=-10.0, maximum=60.0,
                      max_change_per_hour=30.0, max_gap_seconds=900.0)


def valid_measurement() -> RawMeasurement:
    return RawMeasurement(sensor_id="sensor-1", metric="water_temp", value=12.5,
                          unit="celsius", timestamp="2026-11-18T18:00:00Z", source="test")


class MeasurementPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "store.jsonl"
        self.store = MeasurementStore(self.path, key=KEY)
        self.pipeline = MeasurementPipeline(self.store)

    def entries(self) -> list[dict]:
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def test_valid_measurement_stored_once_and_chain_holds(self) -> None:
        result = self.pipeline.process(valid_measurement(), {"water_temp": spec()})
        self.assertIs(result.status, MeasurementStatus.VALID)
        entries = self.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["record_type"], "MEASUREMENT_VALID")
        self.assertEqual(entries[0]["normalized_value"], 12.5)
        self.assertIsNone(entries[0]["calibration_ref"])
        self.assertEqual(entries[0]["calibration_status"], "MISSING_REFERENCE")
        self.assertTrue(self.pipeline.verify_ledger())

    def test_quarantine_verdict_preserves_raw_payload_and_errors(self) -> None:
        bad = RawMeasurement(sensor_id="sensor-1", metric="water_temp", value=999.9,
                             unit="celsius", timestamp="2026-11-18T18:00:00Z")
        result = self.pipeline.process(bad, {"water_temp": spec()})
        self.assertIs(result.status, MeasurementStatus.QUARANTINE)
        entries = self.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["record_type"], "MEASUREMENT_QUARANTINE")
        self.assertEqual(entries[0]["raw_payload"]["value"], 999.9)
        self.assertIn("sentinel", entries[0]["reason"])
        self.assertTrue(self.pipeline.verify_ledger())

    def test_rejected_bool_value_is_also_persisted_not_dropped(self) -> None:
        ugly = RawMeasurement(sensor_id="sensor-1", metric="water_temp", value=True,
                              unit="celsius", timestamp="2026-11-18T18:00:00Z")
        result = self.pipeline.process(ugly, {"water_temp": spec()})
        self.assertIs(result.status, MeasurementStatus.REJECTED)
        entries = self.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["record_type"], "MEASUREMENT_QUARANTINE")
        self.assertIs(entries[0]["raw_payload"]["value"], True)
        self.assertTrue(self.pipeline.verify_ledger())

    def test_exactly_one_ledger_entry_per_measurement(self) -> None:
        self.pipeline.process(valid_measurement(), {"water_temp": spec()})
        self.pipeline.process(valid_measurement(), {"water_temp": spec()})
        bad = RawMeasurement(sensor_id="sensor-2", metric="water_temp", value=999.9,
                             unit="celsius", timestamp="2026-11-18T18:05:00Z")
        self.pipeline.process(bad, {"water_temp": spec()})
        self.assertEqual(len(self.entries()), 3)

    def test_warnings_do_not_block_valid_storage(self) -> None:
        from controller.measurement_ingest import PreviousMeasurement
        measurement = valid_measurement()
        prev = PreviousMeasurement(value=12.5, timestamp="2026-11-18T15:00:00Z")  # > 900 s gap
        result = self.pipeline.process(measurement, {"water_temp": spec()}, previous=prev)
        self.assertIs(result.status, MeasurementStatus.VALID)
        self.assertTrue(result.warnings)
        self.assertEqual(self.entries()[0]["record_type"], "MEASUREMENT_VALID")

    def test_store_is_required(self) -> None:
        with self.assertRaises(MeasurementPipelineError):
            MeasurementPipeline("not-a-store")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()


    def test_present_calibration_reference_is_preserved_as_unverified(self) -> None:
        measurement = RawMeasurement(
            sensor_id="sensor-1",
            metric="water_temp",
            value=12.5,
            unit="celsius",
            timestamp="2026-11-18T18:00:00Z",
            source="test",
            calibration_ref="evidence://sensor-1/calibration/2026-01",
        )
        result = self.pipeline.process(measurement, {"water_temp": spec()})
        self.assertIs(result.status, MeasurementStatus.VALID)
        entry = self.entries()[0]
        self.assertEqual(entry["calibration_ref"], measurement.calibration_ref)
        self.assertEqual(entry["calibration_status"], "REFERENCE_PRESENT_NOT_VERIFIED")
        self.assertTrue(self.pipeline.verify_ledger())

    def test_store_rejects_inconsistent_calibration_metadata(self) -> None:
        with self.assertRaisesRegex(MeasurementStoreError, "claims a reference that is absent"):
            self.store.record_valid(
                sensor_id="s1", metric="m", normalized_value=1.0, unit="u",
                timestamp_utc="2026-11-17T08:00:00Z",
                calibration_ref=None,
                calibration_status="REFERENCE_PRESENT_NOT_VERIFIED",
            )
        with self.assertRaisesRegex(MeasurementStoreError, "claims a missing reference that is present"):
            self.store.record_valid(
                sensor_id="s1", metric="m", normalized_value=1.0, unit="u",
                timestamp_utc="2026-11-17T08:00:00Z",
                calibration_ref="evidence://calibration/1",
                calibration_status="MISSING_REFERENCE",
            )
