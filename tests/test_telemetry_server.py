"""Tests for controller.telemetry_server (stdlib-only, read-only)."""

from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request

from controller.telemetry_server import (
    DEGRADED,
    FAILED,
    OK,
    UNKNOWN,
    build_healthz,
    build_metrics,
    serve,
)


class TestBuildHealthz(unittest.TestCase):
    def test_all_checks_pass(self):
        result = build_healthz({"checks": {"ledger": True, "clock": True}})
        self.assertEqual(result["status"], OK)
        self.assertEqual(result["checks"]["ledger"], OK)

    def test_one_check_failed_degrades(self):
        result = build_healthz({"checks": {"ledger": True, "clock": False}})
        self.assertEqual(result["status"], DEGRADED)
        self.assertEqual(result["checks"]["clock"], FAILED)

    def test_unknown_never_healthy(self):
        result = build_healthz({"checks": {"ledger": True, "clock": None}})
        self.assertEqual(result["status"], UNKNOWN)
        self.assertEqual(result["checks"]["clock"], UNKNOWN)

    def test_no_checks_is_unknown(self):
        result = build_healthz({})
        self.assertEqual(result["status"], UNKNOWN)
        self.assertEqual(result["reason"], "no_checks_provided")

    def test_gauges_pass_through_numbers_only(self):
        result = build_healthz({"checks": {"a": True}, "gauges": {"load": 0.5, "bogus": "x"}})
        self.assertEqual(result["gauges"]["load"], 0.5)
        self.assertEqual(result["gauges"]["bogus"], UNKNOWN)


class TestBuildMetrics(unittest.TestCase):
    def test_gauge_and_check_lines(self):
        text = build_metrics({"gauges": {"load": 0.25}, "checks": {"ledger": True, "clock": None}})
        self.assertIn("v91_gauge_load 0.25", text)
        self.assertIn('v91_check{name="ledger"} 1', text)
        self.assertIn('v91_check{name="clock"} -1', text)

    def test_non_numeric_gauge_marked_unknown(self):
        text = build_metrics({"gauges": {"x": "nope"}})
        self.assertIn("# v91_gauge_x unknown", text)

    def test_metric_name_sanitized(self):
        text = build_metrics({"gauges": {"bad name!": 1}})
        self.assertIn("v91_gauge_bad_name_ 1", text)

    def test_empty_snapshot_yields_empty_exposition(self):
        self.assertEqual(build_metrics({}), "
")


class TestLiveServer(unittest.TestCase):
    def test_healthz_metrics_and_read_only(self):
        server = serve(lambda: {"checks": {"ledger": True}, "gauges": {"load": 0.5}})
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:%d" % server.server_address[1]
        try:
            with urllib.request.urlopen(base + "/healthz", timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(resp.status, 200)
            self.assertEqual(data["status"], OK)

            with urllib.request.urlopen(base + "/metrics", timeout=5) as resp:
                text = resp.read().decode("utf-8")
                self.assertIn("v91_gauge_load 0.5", text)

            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(base + "/does-not-exist", timeout=5)
            self.assertEqual(ctx.exception.code, 404)

            req = urllib.request.Request(base + "/healthz", method="POST")
            with self.assertRaises(urllib.error.HTTPError) as ctx2:
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(ctx2.exception.code, 405)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
