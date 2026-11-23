"""Sustained-flow detector tests (protocol, deterministic, fail-closed).

Every fail-closed rule is pinned: naive timestamps, duplicate
timestamps, non-finite values, bool, invalid parameters are rejected;
input order never changes the result or the report hash.
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.sustained_flow import (SustainedFlowError,
                                       detect_sustained_flow)


def ts(hour):
    return datetime(2026, 11, 23, hour, 0, 0, tzinfo=timezone.utc)


HIGH_SERIES = [
    (ts(0), 0.5),
    (ts(1), 3.0),
    (ts(2), 5.0),
    (ts(3), 4.0),
    (ts(4), 0.8),
    (ts(5), 3.5),
    (ts(6), 0.2),
]


class SustainedFlowTest(unittest.TestCase):
    def test_detects_sustained_window(self):
        result = detect_sustained_flow(HIGH_SERIES, 2.0, 3)
        self.assertEqual(result["event_count"], 1)
        event = result["events"][0]
        self.assertEqual(event["start_utc"], ts(1).isoformat())
        self.assertEqual(event["end_utc"], ts(3).isoformat())
        self.assertEqual(event["window_count"], 3)
        self.assertEqual(event["peak_value"], 5.0)
        self.assertAlmostEqual(event["average_value"], 4.0, places=6)
        self.assertEqual(result["review_status"], "DETECTION_ONLY")

    def test_short_streak_not_reported(self):
        result = detect_sustained_flow(HIGH_SERIES, 2.0, 4)
        self.assertEqual(result["event_count"], 0)
        self.assertEqual(result["events"], [])

    def test_trailing_streak_closed(self):
        series = [(ts(0), 0.5), (ts(1), 3.0), (ts(2), 3.0)]
        result = detect_sustained_flow(series, 2.0, 2)
        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["events"][0]["end_utc"], ts(2).isoformat())

    def test_two_separate_windows(self):
        series = [
            (ts(0), 0.1), (ts(1), 3.0), (ts(2), 3.0),
            (ts(3), 0.1), (ts(4), 3.0), (ts(5), 3.0),
        ]
        result = detect_sustained_flow(series, 2.0, 2)
        self.assertEqual(result["event_count"], 2)

    def test_input_order_irrelevant(self):
        first = detect_sustained_flow(HIGH_SERIES, 2.0, 3)
        second = detect_sustained_flow(list(reversed(HIGH_SERIES)), 2.0, 3)
        self.assertEqual(first["report_sha256"], second["report_sha256"])
        self.assertEqual(first["events"], second["events"])

    def test_exact_threshold_not_counted(self):
        series = [(ts(0), 2.0), (ts(1), 2.0), (ts(2), 2.0)]
        result = detect_sustained_flow(series, 2.0, 2)
        self.assertEqual(result["event_count"], 0)

    def test_empty_series(self):
        result = detect_sustained_flow([], 1.0, 1)
        self.assertEqual(result["event_count"], 0)

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(SustainedFlowError):
            detect_sustained_flow(
                [(datetime(2026, 11, 23, 0, 0, 0), 3.0)], 2.0, 1)

    def test_duplicate_timestamp_rejected(self):
        series = [(ts(0), 3.0), (ts(0), 4.0)]
        with self.assertRaises(SustainedFlowError):
            detect_sustained_flow(series, 2.0, 1)

    def test_bool_value_rejected(self):
        with self.assertRaises(SustainedFlowError):
            detect_sustained_flow([(ts(0), True)], 2.0, 1)

    def test_non_finite_value_rejected(self):
        with self.assertRaises(SustainedFlowError):
            detect_sustained_flow([(ts(0), float("inf"))], 2.0, 1)

    def test_invalid_min_consecutive_rejected(self):
        with self.assertRaises(SustainedFlowError):
            detect_sustained_flow(HIGH_SERIES, 2.0, 0)

    def test_invalid_threshold_rejected(self):
        with self.assertRaises(SustainedFlowError):
            detect_sustained_flow(HIGH_SERIES, True, 1)
        with self.assertRaises(SustainedFlowError):
            detect_sustained_flow(HIGH_SERIES, float("nan"), 1)

    def test_deterministic_report_hash(self):
        first = detect_sustained_flow(HIGH_SERIES, 2.0, 3)
        second = detect_sustained_flow(HIGH_SERIES, 2.0, 3)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
