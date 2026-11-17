"""Tests for the durable measurement store (Issue #100, stdlib only)."""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from controller.measurement_store import (
    STORE_KEY_ENV,
    MeasurementStore,
    MeasurementStoreError,
    resolve_key,
)

KEY = b"m" * 32


class KeyTest(unittest.TestCase):
    def test_missing_key_fails_closed(self):
        old = os.environ.pop(STORE_KEY_ENV, None)
        try:
            with self.assertRaises(MeasurementStoreError):
                resolve_key()
        finally:
            if old is not None:
                os.environ[STORE_KEY_ENV] = old

    def test_short_key_fails_closed(self):
        old = os.environ.get(STORE_KEY_ENV)
        os.environ[STORE_KEY_ENV] = "short"
        try:
            with self.assertRaises(MeasurementStoreError):
                resolve_key()
        finally:
            if old is not None:
                os.environ[STORE_KEY_ENV] = old
            else:
                os.environ.pop(STORE_KEY_ENV, None)


class StoreTest(unittest.TestCase):
    def _store(self, tmp: Path) -> MeasurementStore:
        return MeasurementStore(tmp / "store.jsonl", key=KEY)

    def test_valid_record_roundtrip_and_chain(self):
        with TemporaryDirectory() as d:
            store = self._store(Path(d))
            store.record_valid(sensor_id="s1", metric="soil_moisture", normalized_value=42.3,
                               unit="%", timestamp_utc="2026-11-17T08:00:00Z")
            store.record_valid(sensor_id="s1", metric="soil_moisture", normalized_value=43.1,
                               unit="%", timestamp_utc="2026-11-17T08:15:00Z")
            self.assertTrue(store.verify_chain())
            self.assertEqual(store.count(), 2)

    def test_quarantine_preserves_raw_payload(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "store.jsonl"
            store = MeasurementStore(path, key=KEY)
            raw = {"sensor_id": "s2", "value": None, "timestamp": "2026-11-17T08:00:00"}
            record = store.quarantine(raw, reason="value is None", claimed_source_time=raw["timestamp"])
            self.assertEqual(record["record_type"], "MEASUREMENT_QUARANTINE")
            self.assertEqual(record["raw_payload"], raw)
            self.assertEqual(record["disposition"], "OPEN")
            stored = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(stored["raw_payload"], raw)

    def test_tampered_chain_refuses_append(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "store.jsonl"
            store = MeasurementStore(path, key=KEY)
            store.record_valid(sensor_id="s1", metric="m", normalized_value=1.0, unit="u",
                               timestamp_utc="2026-11-17T08:00:00Z")
            entry = json.loads(path.read_text(encoding="utf-8"))
            entry["normalized_value"] = 999.0
            path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
            self.assertFalse(store.verify_chain())
            with self.assertRaises(MeasurementStoreError):
                store.record_valid(sensor_id="s1", metric="m", normalized_value=2.0, unit="u",
                                   timestamp_utc="2026-11-17T08:15:00Z")

    def test_corrupt_line_fails_closed(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "store.jsonl"
            path.write_text("not json\n", encoding="utf-8")
            store = MeasurementStore(path, key=KEY)
            with self.assertRaises(MeasurementStoreError):
                store.verify_chain()

    def test_forged_record_detected(self):
        with TemporaryDirectory() as d:
            store = self._store(Path(d))
            record = store.record_valid(sensor_id="s1", metric="m", normalized_value=1.0, unit="u",
                                        timestamp_utc="2026-11-17T08:00:00Z")
            self.assertTrue(store.verify_record(record))
            forged = dict(record, normalized_value=5.0)
            self.assertFalse(store.verify_record(forged))

    def test_invalid_inputs_rejected(self):
        with TemporaryDirectory() as d:
            store = self._store(Path(d))
            with self.assertRaises(MeasurementStoreError):
                store.record_valid(sensor_id="", metric="m", normalized_value=1.0, unit="u",
                                   timestamp_utc="2026-11-17T08:00:00Z")
            with self.assertRaises(MeasurementStoreError):
                store.record_valid(sensor_id="s", metric="m", normalized_value=True, unit="u",
                                   timestamp_utc="2026-11-17T08:00:00Z")
            with self.assertRaises(MeasurementStoreError):
                store.quarantine(["not", "a", "dict"], reason="x")
            with self.assertRaises(MeasurementStoreError):
                store.quarantine({"a": 1}, reason="  ")

    def test_short_constructor_key_fails_closed(self):
        with self.assertRaises(MeasurementStoreError):
            MeasurementStore(Path("x.jsonl"), key=b"short")

    def test_lock_released_after_append(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "store.jsonl"
            store = MeasurementStore(path, key=KEY)
            store.record_valid(sensor_id="s1", metric="m", normalized_value=1.0, unit="u",
                               timestamp_utc="2026-11-17T08:00:00Z")
            self.assertFalse(path.with_suffix(".jsonl.lock").exists())


if __name__ == "__main__":
    unittest.main()
