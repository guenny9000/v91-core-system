"""Tests for the fail-closed read-only host metrics adapter."""
import unittest
from types import SimpleNamespace

from controller.real_metrics import collect_host_metrics


class FakePsutil:
    @staticmethod
    def cpu_percent(interval=0.1):
        return 17.5

    @staticmethod
    def virtual_memory():
        return SimpleNamespace(total=1000, available=400, percent=60.0)


class TestRealMetrics(unittest.TestCase):
    def test_valid_snapshot_has_source_and_timestamp(self):
        result = collect_host_metrics(FakePsutil)
        self.assertEqual(result["status"], "DOCUMENTED")
        self.assertEqual(result["source"], "psutil.host")
        self.assertTrue(result["timestamp_utc"])
        self.assertEqual(result["cpu_percent"], 17.5)
        self.assertEqual(result["memory_total_bytes"], 1000)

    def test_invalid_cpu_fails_closed(self):
        class BadCpu(FakePsutil):
            @staticmethod
            def cpu_percent(interval=0.1):
                return float("nan")
        result = collect_host_metrics(BadCpu)
        self.assertEqual(result["status"], "NO_DATA_AVAILABLE")
        self.assertNotIn("cpu_percent", result)

    def test_read_error_fails_closed(self):
        class Broken:
            @staticmethod
            def cpu_percent(interval=0.1):
                raise OSError("host-specific details")
        result = collect_host_metrics(Broken)
        self.assertEqual(result["status"], "NO_DATA_AVAILABLE")
        self.assertNotIn("host-specific details", str(result))

    def test_impossible_memory_values_fail_closed(self):
        class BadMemory(FakePsutil):
            @staticmethod
            def virtual_memory():
                return SimpleNamespace(total=100, available=101, percent=0.0)
        result = collect_host_metrics(BadMemory)
        self.assertEqual(result["status"], "NO_DATA_AVAILABLE")


if __name__ == "__main__":
    unittest.main()
