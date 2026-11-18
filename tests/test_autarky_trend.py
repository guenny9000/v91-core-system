"""Tests: honest autarky trend comparison (Issue #83 Phase 3)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.autarky_metrics import AutarkyMetricError, AutarkyTrend
from controller.autarky_report import build_report, main as report_main
from controller.measurement_core import append_snapshot, metric


def make_snapshot(solar=None, grid=None):
    return {
        "schema": "v91.measurement.v1",
        "event_id": "test-event",
        "measured_at_utc": "2026-11-18T12:00:00.000Z",
        "collection_mode": "READ_ONLY",
        "host_measurements": {
            "solar_w": metric(solar, "W", "test_meter") if solar is not None else metric(None, "W", "test_meter", "not connected"),
            "grid_w": metric(grid, "W", "test_meter") if grid is not None else metric(None, "W", "test_meter", "not connected"),
        },
    }


class AutarkyTrendMetricTests(unittest.TestCase):
    def test_improved_trend_from_two_measured_windows(self):
        baseline = [{"solar_w": 300.0, "grid_w": 100.0}]
        comparison = [{"solar_w": 450.0, "grid_w": 50.0}]
        result = AutarkyTrend(baseline, comparison).compute()
        self.assertEqual(result["status"], "MEASURED")
        self.assertEqual(result["trend"], "IMPROVED")
        self.assertEqual(result["baseline_share"], 0.75)
        self.assertEqual(result["comparison_share"], 0.9)
        self.assertEqual(result["delta_share"], 0.15)

    def test_degraded_trend_is_not_hidden(self):
        baseline = [{"solar_w": 450.0, "grid_w": 50.0}]
        comparison = [{"solar_w": 300.0, "grid_w": 100.0}]
        result = AutarkyTrend(baseline, comparison).compute()
        self.assertEqual(result["status"], "MEASURED")
        self.assertEqual(result["trend"], "DEGRADED")
        self.assertEqual(result["delta_share"], -0.15)

    def test_small_delta_within_tolerance_is_stable(self):
        baseline = [{"solar_w": 100.0, "grid_w": 100.0}]
        comparison = [{"solar_w": 105.0, "grid_w": 100.0}]
        result = AutarkyTrend(baseline, comparison).compute()
        self.assertEqual(result["status"], "MEASURED")
        self.assertEqual(result["trend"], "STABLE")
        self.assertLessEqual(abs(result["delta_share"]), result["tolerance"])

    def test_unmeasured_baseline_window_is_unknown(self):
        baseline = [{}]  # sensor not connected
        comparison = [{"solar_w": 450.0, "grid_w": 50.0}]
        result = AutarkyTrend(baseline, comparison).compute()
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["trend"])

    def test_unmeasured_comparison_window_is_unknown(self):
        baseline = [{"solar_w": 450.0, "grid_w": 50.0}]
        comparison = []
        result = AutarkyTrend(baseline, comparison).compute()
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["trend"])

    def test_zero_power_windows_are_unknown_not_stable(self):
        # total == 0 in both windows means no energy flowed: not evidence
        result = AutarkyTrend([{"solar_w": 0.0, "grid_w": 0.0}], [{"solar_w": 0.0, "grid_w": 0.0}]).compute()
        self.assertEqual(result["status"], "UNKNOWN")

    def test_invalid_arguments_fail_closed(self):
        with self.assertRaises(AutarkyMetricError):
            AutarkyTrend("not-a-list", []).compute()
        with self.assertRaises(AutarkyMetricError):
            AutarkyTrend([], "not-a-list").compute()
        with self.assertRaises(AutarkyMetricError):
            AutarkyTrend([], [], interval_hours=0)
        with self.assertRaises(AutarkyMetricError):
            AutarkyTrend([], [], tolerance=-0.01)
        with self.assertRaises(AutarkyMetricError):
            AutarkyTrend([], [], tolerance="wide")


class AutarkyTrendWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"
        self.baseline = Path(self.tmp.name) / "baseline.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_report_trend_improved_between_two_ledgers(self):
        append_snapshot(self.baseline, make_snapshot(solar=300, grid=100))
        append_snapshot(self.ledger, make_snapshot(solar=450, grid=50))
        report = build_report(self.ledger, trend_baseline_ledger=self.baseline)
        trend = report["autarky_trend"]
        self.assertEqual(trend["status"], "MEASURED")
        self.assertEqual(trend["trend"], "IMPROVED")
        self.assertEqual(trend["baseline_ledger_status"], "CHAIN_VALID")

    def test_report_trend_unknown_with_empty_baseline(self):
        append_snapshot(self.ledger, make_snapshot(solar=450, grid=50))
        report = build_report(self.ledger, trend_baseline_ledger=self.baseline)
        trend = report["autarky_trend"]
        self.assertEqual(trend["status"], "UNKNOWN")
        self.assertEqual(trend["baseline_ledger_status"], "EMPTY_LEDGER")

    def test_no_trend_key_without_baseline(self):
        append_snapshot(self.ledger, make_snapshot(solar=450, grid=50))
        report = build_report(self.ledger)
        self.assertNotIn("autarky_trend", report)

    def test_cli_trend_baseline_exit_zero(self):
        append_snapshot(self.baseline, make_snapshot(solar=300, grid=100))
        append_snapshot(self.ledger, make_snapshot(solar=450, grid=50))
        self.assertEqual(
            report_main(["--ledger", str(self.ledger), "--trend-baseline-ledger", str(self.baseline)]),
            0,
        )

    def test_cli_corrupt_baseline_fails_closed_exit_two(self):
        self.baseline.write_text("not json\n", encoding="utf-8")
        append_snapshot(self.ledger, make_snapshot(solar=450, grid=50))
        self.assertEqual(
            report_main(["--ledger", str(self.ledger), "--trend-baseline-ledger", str(self.baseline)]),
            2,
        )


if __name__ == "__main__":
    unittest.main()