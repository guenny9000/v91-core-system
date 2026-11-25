"""Tests fuer controller/schwellen_registry.py (unittest, stdlib-only)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller.schwellen_registry import (
    BINDUNG,
    EXPIRED,
    REVIEW_REQUIRED,
    UNKNOWN,
    SchwellenRegistryError,
    bind_registry,
    bind_use_case,
    main,
)

NOW = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)


def cal_entry(**kw):
    base = {
        "sensor_id": "power_meter_1",
        "evidence": "ledger::cal-001",
        "calibrated_at": "2026-11-01T10:00:00+00:00",
    }
    base.update(kw)
    return base


def reg_entry(**kw):
    base = {
        "use_case": "solar_impact",
        "sensor_id": "power_meter_1",
        "thresholds": {"min_samples": 5, "dqi_min": 0.85, "noise_factor": 2.0},
    }
    base.update(kw)
    return base


class BindUseCaseTest(unittest.TestCase):
    def test_calibrated_sensor_binds_thresholds(self):
        out = bind_use_case(reg_entry(), cal_entry(), NOW)
        self.assertEqual(out["binding_status"], BINDUNG)
        self.assertEqual(out["thresholds"], {"min_samples": 5, "dqi_min": 0.85, "noise_factor": 2.0})
        self.assertEqual(out["sensor_state"], "CALIBRATED")

    def test_expired_sensor_gives_no_thresholds(self):
        cal = cal_entry(valid_until="2026-11-02T00:00:00+00:00")
        out = bind_use_case(reg_entry(), cal, NOW)
        self.assertEqual(out["sensor_state"], EXPIRED)
        self.assertEqual(out["binding_status"], "NICHT_GEBUNDEN")
        self.assertIsNone(out["thresholds"])

    def test_review_required_sensor_gives_no_thresholds(self):
        out = bind_use_case(reg_entry(), cal_entry(evidence=None), NOW)
        self.assertEqual(out["sensor_state"], REVIEW_REQUIRED)
        self.assertIsNone(out["thresholds"])
        self.assertIn("reason", out)

    def test_unknown_sensor_is_impossible_via_binding_api(self):
        # bind_use_case verlangt einen Calibration-Eintrag; fuer UNKNOWN-Sensoren
        # verweigert bind_registry den Eintrag komplett (fail-closed).
        with self.assertRaises(SchwellenRegistryError):
            bind_registry([reg_entry()], [], NOW)

    def test_none_thresholds_rejected_explicitly(self):
        reg = reg_entry(thresholds={"min_samples": None, "dqi_min": 0.85, "noise_factor": 2.0})
        with self.assertRaises(SchwellenRegistryError):
            bind_use_case(reg, cal_entry(), NOW)

    def test_partial_thresholds_rejected(self):
        reg = reg_entry(thresholds={"min_samples": 5})
        with self.assertRaises(SchwellenRegistryError):
            bind_use_case(reg, cal_entry(), NOW)

    def test_invalid_threshold_value_reuses_impact_validation(self):
        reg = reg_entry(thresholds={"min_samples": 5, "dqi_min": 1.5, "noise_factor": 2.0})
        with self.assertRaises(SchwellenRegistryError):
            bind_use_case(reg, cal_entry(), NOW)

    def test_empty_use_case_rejected(self):
        with self.assertRaises(SchwellenRegistryError):
            bind_use_case(reg_entry(use_case="  "), cal_entry(), NOW)

    def test_non_dict_entry_rejected(self):
        with self.assertRaises(SchwellenRegistryError):
            bind_use_case([reg_entry()], cal_entry(), NOW)

    def test_naive_now_rejected(self):
        with self.assertRaises(SchwellenRegistryError):
            bind_registry([reg_entry()], [cal_entry()], datetime(2026, 11, 25, 12, 0, 0))


class BindRegistryTest(unittest.TestCase):
    def test_registry_summary_counts(self):
        out = bind_registry(
            [reg_entry(), reg_entry(use_case="second", sensor_id="meter_2")],
            [cal_entry(), cal_entry(sensor_id="meter_2")],
            NOW,
        )
        self.assertEqual(out["bound_use_cases"], 2)
        self.assertEqual(out["total_use_cases"], 2)
        self.assertEqual(out["schema"], "v91.schwellen_registry.v1")

    def test_duplicate_use_case_rejected(self):
        with self.assertRaises(SchwellenRegistryError):
            bind_registry([reg_entry(), reg_entry()], [cal_entry()], NOW)

    def test_duplicate_calibration_entry_rejected(self):
        with self.assertRaises(SchwellenRegistryError):
            bind_registry([reg_entry()], [cal_entry(), cal_entry()], NOW)

    def test_empty_registry_rejected(self):
        with self.assertRaises(SchwellenRegistryError):
            bind_registry([], [cal_entry()], NOW)

    def test_requested_use_case_missing_rejected(self):
        with self.assertRaises(SchwellenRegistryError):
            bind_registry([reg_entry()], [cal_entry()], NOW, use_cases=["andere"])

    def test_honest_limits_present(self):
        out = bind_registry([reg_entry()], [cal_entry()], NOW)
        self.assertTrue(any("BINDUNG != MESSTECHNIK" in h for h in out["honest_limits"]))
        self.assertTrue(any("CALIBRATED != ACCURATE" in h for h in out["honest_limits"]))


class CliTest(unittest.TestCase):
    def test_self_check_exit_0_and_synthetic_marker(self):
        proc = subprocess.run(
            [sys.executable, "controller/schwellen_registry.py", "--self-check"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn('"reale_messreihe": "NICHT_GEPRUEFT"', proc.stdout)

    def test_cli_binds_from_files(self):
        with tempfile.TemporaryDirectory() as td:
            reg_path = os.path.join(td, "reg.json")
            cal_path = os.path.join(td, "cal.json")
            with open(reg_path, "w", encoding="utf-8") as fh:
                json.dump([reg_entry()], fh)
            with open(cal_path, "w", encoding="utf-8") as fh:
                json.dump([cal_entry()], fh)
            proc = subprocess.run(
                [sys.executable, "controller/schwellen_registry.py",
                 "--registry", reg_path, "--calibration", cal_path,
                 "--now", "2026-11-25T12:00:00+00:00"],
                capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn(BINDUNG, proc.stdout)

    def test_cli_naive_now_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            reg_path = os.path.join(td, "reg.json")
            cal_path = os.path.join(td, "cal.json")
            with open(reg_path, "w", encoding="utf-8") as fh:
                json.dump([reg_entry()], fh)
            with open(cal_path, "w", encoding="utf-8") as fh:
                json.dump([cal_entry()], fh)
            proc = subprocess.run(
                [sys.executable, "controller/schwellen_registry.py",
                 "--registry", reg_path, "--calibration", cal_path, "--now", "2026-11-25T12:00:00"],
                capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            self.assertEqual(proc.returncode, 2)

    def test_cli_missing_args_exit_2(self):
        proc = subprocess.run(
            [sys.executable, "controller/schwellen_registry.py"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
