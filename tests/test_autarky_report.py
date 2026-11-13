"""Tests: autarky report wiring (Issue #83 Phase 2)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.autarky_metrics import AutarkyMetricError
from controller.autarky_report import build_report, load_measurement_records, main
from controller.measurement_core import (
    MeasurementError,
    append_snapshot,
    metric,
)


def make_snapshot(solar=None, grid=None):
    return {
        "schema": "v91.measurement.v1",
        "event_id": "test-event",
        "measured_at_utc": "2026-11-13T12:00:00.000Z",
        "collection_mode": "READ_ONLY",
        "host_measurements": {
            "solar_w": metric(solar, "W", "test_meter") if solar is not None else metric(None, "W", "test_meter", "not connected"),
            "grid_w": metric(grid, "W", "test_meter") if grid is not None else metric(None, "W", "test_meter", "not connected"),
        },
    }


class LoadMeasurementRecordsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_ledger_is_unknown_not_error(self):
        records, state = load_measurement_records(self.ledger)
        self.assertEqual(records, [])
        self.assertEqual(state["status"], "EMPTY_LEDGER")

    def test_measured_values_are_extracted(self):
        append_snapshot(self.ledger, make_snapshot(solar=300, grid=100))
        records, state = load_measurement_records(self.ledger)
        self.assertEqual(state["status"], "CHAIN_VALID")
        self.assertEqual(records, [{"solar_w": 300.0, "grid_w": 100.0}])

    def test_unknown_values_stay_unknown(self):
        append_snapshot(self.ledger, make_snapshot())
        records, _ = load_measurement_records(self.ledger)
        self.assertEqual(records, [{}])

    def test_corrupt_ledger_fails_closed(self):
        append_snapshot(self.ledger, make_snapshot(solar=1, grid=1))
        with self.ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"sequence": 99, "previous_hash": "x", "event_hash": "y"}) + "\n")
        with self.assertRaises(MeasurementError):
            load_measurement_records(self.ledger)


class BuildReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_report_from_measured_intervals(self):
        append_snapshot(self.ledger, make_snapshot(solar=300, grid=100))
        append_snapshot(self.ledger, make_snapshot(solar=100, grid=100))
        report = build_report(self.ledger)
        self.assertEqual(report["ledger"]["status"], "CHAIN_VALID")
        energy = report["energy_autarky"]
        self.assertEqual(energy["status"], "MEASURED")
        self.assertEqual(energy["self_sufficiency_share"], round(400 / 600, 6))
        self.assertEqual(energy["measured_intervals"], 2)

    def test_empty_ledger_reports_unknown(self):
        report = build_report(self.ledger)
        self.assertEqual(report["energy_autarky"]["status"], "UNKNOWN")
        self.assertIsNone(report["energy_autarky"]["self_sufficiency_share"])

    def test_regional_config_measured(self):
        config = Path(self.tmp.name) / "regional.json"
        config.write_text(json.dumps({"local_produced": 50, "local_consumed": 100}), encoding="utf-8")
        report = build_report(self.ledger, regional_config_path=config)
        self.assertEqual(report["regional_loop"]["status"], "MEASURED")
        self.assertEqual(report["regional_loop"]["local_loop_share"], 0.5)

    def test_regional_config_invalid_is_unknown(self):
        config = Path(self.tmp.name) / "regional.json"
        config.write_text(json.dumps({"local_produced": "much"}), encoding="utf-8")
        report = build_report(self.ledger, regional_config_path=config)
        self.assertEqual(report["regional_loop"]["status"], "UNKNOWN")

    def test_biodiversity_chain_verified(self):
        bio = Path(self.tmp.name) / "bio.jsonl"
        bio.parent.mkdir(parents=True, exist_ok=True)
        report = build_report(self.ledger, biodiversity_log_path=bio)
        self.assertTrue(report["biodiversity"]["chain_valid"])
        self.assertEqual(report["biodiversity"]["observations"], 0)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_cli_success_exit_zero(self):
        append_snapshot(self.ledger, make_snapshot(solar=10, grid=10))
        self.assertEqual(main(["--ledger", str(self.ledger)]), 0)

    def test_cli_corrupt_ledger_exit_two(self):
        self.ledger.write_text("not json\n", encoding="utf-8")
        self.assertEqual(main(["--ledger", str(self.ledger)]), 2)


if __name__ == "__main__":
    unittest.main()
