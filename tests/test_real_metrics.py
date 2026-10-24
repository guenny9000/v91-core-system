"""Tests for the optional, read-only host telemetry adapter."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))
from real_metrics import collect_host_metrics


class FakePsutil:
    @staticmethod
    def cpu_percent(interval=0.1):
        return 17.5

    @staticmethod
    def virtual_memory():
        return SimpleNamespace(total=1000, available=400, percent=60.0)


def test_valid_snapshot_has_source_and_timestamp():
    result = collect_host_metrics(FakePsutil)
    assert result["status"] == "DATA_AVAILABLE"
    assert result["source"] == "psutil.host"
    assert result["timestamp_utc"]
    assert result["cpu_percent"] == 17.5
    assert result["memory_total_bytes"] == 1000


def test_invalid_cpu_fails_closed():
    class BadCpu(FakePsutil):
        @staticmethod
        def cpu_percent(interval=0.1):
            return float("nan")
    result = collect_host_metrics(BadCpu)
    assert result["status"] == "NO_DATA_AVAILABLE"
    assert "cpu_percent" not in result


def test_read_error_fails_closed_without_leaking_exception():
    class Broken:
        @staticmethod
        def cpu_percent(interval=0.1):
            raise OSError("host-specific details")
    result = collect_host_metrics(Broken)
    assert result["status"] == "NO_DATA_AVAILABLE"
    assert "host-specific details" not in str(result)


def test_impossible_memory_values_fail_closed():
    class BadMemory(FakePsutil):
        @staticmethod
        def virtual_memory():
            return SimpleNamespace(total=100, available=101, percent=0.0)
    result = collect_host_metrics(BadMemory)
    assert result["status"] == "NO_DATA_AVAILABLE"


def test_missing_psutil_fails_closed(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def import_without_psutil(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("psutil not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_psutil)
    result = collect_host_metrics()
    assert result["status"] == "NO_DATA_AVAILABLE"
    assert result["reason"] == "psutil_not_installed"
