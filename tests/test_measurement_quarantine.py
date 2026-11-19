"""Tests for the durable measurement quarantine (issue #100, stdlib only)."""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from controller.measurement_quarantine import (
    LOCK_SUFFIX,
    MeasurementQuarantine,
    QuarantineError,
)

RAW = {"sensor_id": "s1", "metric": "soil_moisture", "value": None}


class QuarantineTest(unittest.TestCase):
    def _q(self, tmp: Path) -> MeasurementQuarantine:
        return MeasurementQuarantine(tmp / "quarantine.jsonl")

    def test_quarantine_preserves_raw_data_and_context(self):
        with TemporaryDirectory() as d:
            with self._q(Path(d)) as q:
                record = q.quarantine(RAW, reason="value is None", sender="sensor-01", source_id="s1")
            self.assertEqual(record["status"], "OPEN")
            self.assertEqual(record["raw_data"], RAW)
            self.assertEqual(record["sender"], "sensor-01")
            self.assertTrue(q.verify_chain())

    def test_resolution_is_a_new_entry_original_untouched(self):
        with TemporaryDirectory() as d:
            with self._q(Path(d)) as q:
                record = q.quarantine(RAW, reason="out of range")
                res = q.resolve(record["seq"], resolution="confirmed sensor fault", resolved_by="operator")
            self.assertEqual(res["original_seq"], record["seq"])
            self.assertEqual(res["status"], "RESOLVED")
            self.assertEqual(q.list_open(), [])
            self.assertTrue(q.verify_chain())
            lines = (Path(d) / "quarantine.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["status"], "OPEN")

    def test_tampered_entry_breaks_chain_and_blocks_append(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "quarantine.jsonl"
            with self._q(path.parent) as q:
                q.quarantine(RAW, reason="ok")
            entry = json.loads(path.read_text(encoding="utf-8"))
            entry["reason"] = "FORGED"
            path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
            with self._q(path.parent) as q2:
                with self.assertRaises(QuarantineError):
                    q2.quarantine(RAW, reason="again")
                self.assertFalse(q2.verify_chain())

    def test_corrupt_line_fails_closed(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "quarantine.jsonl"
            path.write_text("not json\n", encoding="utf-8")
            with self._q(path.parent) as q:
                with self.assertRaises(QuarantineError):
                    q.verify_chain()

    def test_empty_reason_rejected(self):
        with TemporaryDirectory() as d:
            with self._q(Path(d)) as q:
                with self.assertRaises(QuarantineError):
                    q.quarantine(RAW, reason="   ")

    def test_resolve_unknown_seq_rejected(self):
        with TemporaryDirectory() as d:
            with self._q(Path(d)) as q:
                with self.assertRaises(QuarantineError):
                    q.resolve(99, resolution="x", resolved_by="y")

    def test_lock_prevents_concurrent_writer(self):
        with TemporaryDirectory() as d:
            q1 = self._q(Path(d))
            try:
                with self.assertRaises(QuarantineError):
                    self._q(Path(d))
            finally:
                q1.close()
            # lock released: second writer can now open
            q2 = self._q(Path(d))
            q2.close()

    def test_lock_file_removed_after_close(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "quarantine.jsonl"
            with self._q(path.parent):
                self.assertTrue(Path(str(path) + LOCK_SUFFIX).exists())
            self.assertFalse(Path(str(path) + LOCK_SUFFIX).exists())

    def test_write_after_close_is_rejected(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "quarantine.jsonl"
            q = self._q(path.parent)
            q.close()
            with self.assertRaisesRegex(QuarantineError, "quarantine is closed"):
                q.quarantine(RAW, reason="must not write after close")
            self.assertFalse(path.exists())

    def test_duplicate_resolution_is_rejected(self):
        with TemporaryDirectory() as d:
            with self._q(Path(d)) as q:
                record = q.quarantine(RAW, reason="needs review")
                q.resolve(record["seq"], resolution="confirmed", resolved_by="operator")
                with self.assertRaisesRegex(QuarantineError, "already resolved"):
                    q.resolve(record["seq"], resolution="conflicting second result",
                              resolved_by="operator")
                self.assertEqual(q.list_open(), [])
                self.assertTrue(q.verify_chain())

    def test_fsync_used_for_durability(self):
        import controller.measurement_quarantine as mq
        with TemporaryDirectory() as d:
            called = []
            original = mq.os.fsync
            mq.os.fsync = lambda fd: called.append(fd) or original(fd)
            try:
                with self._q(Path(d)) as q:
                    q.quarantine(RAW, reason="x")
            finally:
                mq.os.fsync = original
            self.assertTrue(called)


if __name__ == "__main__":
    unittest.main()
