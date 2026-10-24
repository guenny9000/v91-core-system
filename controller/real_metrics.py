"""Read-only host telemetry with explicit source and fail-closed behavior.

This adapter reports host CPU and memory only. It does not infer application
latency, request/error counts, GPU metrics, or production health.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import time
from typing import Any


def collect_host_metrics(psutil_module: Any = None) -> dict[str, Any]:
    """Collect one host snapshot; missing or invalid telemetry is never zero."""
    if psutil_module is None:
        try:
            import psutil as psutil_module  # type: ignore[no-redef]
        except ImportError:
            return {
                "status": "NO_DATA_AVAILABLE",
                "reason": "psutil_not_installed",
                "source": None,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }

    try:
        cpu = psutil_module.cpu_percent(interval=0.1)
        memory = psutil_module.virtual_memory()
        total = memory.total
        available = memory.available
        used_percent = memory.percent
        values = (cpu, total, available, used_percent)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
            raise ValueError("telemetry values must be numeric")
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("telemetry values must be finite")
        if not (0 <= cpu <= 100 and total > 0 and 0 <= available <= total and 0 <= used_percent <= 100):
            raise ValueError("telemetry values outside valid bounds")
        return {
            "status": "DOCUMENTED",
            "source": "psutil.host",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "monotonic_sample_seconds": time.monotonic(),
            "cpu_percent": float(cpu),
            "memory_total_bytes": int(total),
            "memory_available_bytes": int(available),
            "memory_used_percent": float(used_percent),
        }
    except Exception:
        # Avoid exposing host-specific exception text in status reports.
        return {
            "status": "NO_DATA_AVAILABLE",
            "reason": "telemetry_read_failed",
            "source": "psutil.host",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
