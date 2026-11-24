"""Tests fuer controller/calibration_status.py (unittest, stdlib-only)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller.calibration_status import (
    CALIBRATED,
    CalibrationStatusError,
    EXPIRED,
    REVIEW_REQUIRED,
    UNKNOWN,
    evaluate_calibration_registry,
    evaluate_sensor,
    main,
)

NOW = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)


def entry(**kw):
    base = {"sensor_id": "power_meter_1", "evidence": "ledger::cal-001", "calibrated_at": "2026-11-01T10:00:00+00:00"}
    base.update(kw)
    return base


class SensorTests(unittest.TestCase):
    def test_calibrated_with_evidence(self):
        self.assertEqual(evaluate_sensor(entry(), NOW)["state"], CALIBRATED)

    def test_missing_evidence_review_required(self):
        self.assertEqual(evaluate_sensor({"sensor_id": "s", "calibrated_at": "2026-11-01T10:00:00+00:00"}, NOW)["state"], REVIEW_REQUIRED)

    def test_invalid_evidence_review_required(self):
        self.assertEqual(evaluate_sensor(entry(evidence="freitext ohne referenzstruktur "), NOW)["state"], REVIEW_REQUIRED)

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(CalibrationStatusError):
            evaluate_sensor(entry(calibrated_at="2026-11-01T10:00:00"), NOW)

    def test_missing_timestamp_rejected(self):
        with self.assertRaises(CalibrationStatusError):
            evaluate_sensor(entry(calibrated_at=""), NOW)

    def test_expired_window(self):
        r = evaluate_sensor(entry(valid_until="2026-11-15T00:00:00+00:00"), NOW)
        self.assertEqual(r["state"], EXPIRED)

    def test_valid_window_future(self):
        r = evaluate_sensor(entry(valid_until="2027-01-01T00:00:00+00:00"), NOW)
        self.assertEqual(r["state"], CALIBRATED)

    def test_window_before_calibration_rejected(self):
        with self.assertRaises(CalibrationStatusError):
            evaluate_sensor(entry(valid_until="2026-10-01T00:00:00+00:00"), NOW)

    def test_non_dict_entry_raises(self):
        with self.assertRaises(CalibrationStatusError):
            evaluate_sensor("kein objekt", NOW)

    def test_empty_sensor_id_raises(self):
        with self.assertRaises(CalibrationStatusError):
            evaluate_sensor({"sensor_id": "  "}, NOW)


class RegistryTests(unittest.TestCase):
    def test_counts_and_coverage(self):
        report = evaluate_calibration_registry(
            [entry(), entry(sensor_id="s2", evidence="x", calibrated_at="2026-11-01T10:00:00+00:00")],
            "2026-11-24T12:00:00+00:00",
            sensor_ids=["power_meter_1", "s2", "s3"],
        )
        self.assertEqual(report["state_counts"][CALIBRATED], 1)
        self.assertEqual(report["state_counts"][REVIEW_REQUIRED], 1)
        self.assertEqual(report["state_counts"][UNKNOWN], 1)
        self.assertEqual(report["calibration_coverage"], 0.3333)
        self.assertEqual(report["coverage_status"], "CALCULATED_ONLY")

    def test_missing_registered_sensor_unknown(self):
        report = evaluate_calibration_registry([entry()], NOW.isoformat(), sensor_ids=["power_meter_1", "unseen"])
        self.assertEqual(any(s["state"] == UNKNOWN for s in report["sensors"]), True)

    def test_duplicate_sensor_rejected(self):
        with self.assertRaises(CalibrationStatusError):
            evaluate_calibration_registry([entry(), entry()], NOW)

    def test_naive_now_rejected(self):
        with self.assertRaises(CalibrationStatusError):
            evaluate_calibration_registry([entry()], "2026-11-24T12:00:00")

    def test_empty_everything_rejected(self):
        with self.assertRaises(CalibrationStatusError):
            evaluate_calibration_registry([], NOW)

    def test_entries_not_list_rejected(self):
        with self.assertRaises(CalibrationStatusError):
            evaluate_calibration_registry("nope", NOW)

    def test_sensor_ids_validation(self):
        with self.assertRaises(CalibrationStatusError):
            evaluate_calibration_registry([entry()], NOW, sensor_ids=["ok", ""])
        with self.assertRaises(CalibrationStatusError):
            evaluate_calibration_registry([entry()], NOW, sensor_ids="power_meter_1")

    def test_datetime_now_accepted_and_explicit(self):
        report = evaluate_calibration_registry([entry()], datetime.now(timezone.utc))
        self.assertEqual(report["review_status"], "CALIBRATION_REVIEW_ONLY")


class CliTests(unittest.TestCase):
    def _run(self, payload):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ, PYTHONPATH=root)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(payload, fh)
            name = fh.name
        try:
            return subprocess.run([sys.executable, os.path.join(root, "controller", "calibration_status.py"), name],
                                  capture_output=True, text=True, env=env)
        finally:
            os.unlink(name)

    def test_exit_0_all_calibrated(self):
        proc = self._run({"entries": [entry()], "now": "2026-11-24T12:00:00+00:00"})
        self.assertEqual(proc.returncode, 0)
        self.assertIn(CALIBRATED, proc.stdout)

    def test_exit_1_with_unknown(self):
        proc = self._run({"entries": [entry()], "now": "2026-11-24T12:00:00+00:00", "sensor_ids": ["ghost"]})
        self.assertEqual(proc.returncode, 1)
        self.assertIn(UNKNOWN, proc.stdout)

    def test_exit_2_on_naive_now(self):
        proc = self._run({"entries": [entry()], "now": "2026-11-24T12:00:00"})
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error", proc.stdout)


if __name__ == "__main__":
    unittest.main()
