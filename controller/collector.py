#!/usr/bin/env python3
"""Real local measurements (stdlib only): memory in use (MB) of this machine."""

import csv
import ctypes
import os
import sys
import time
from datetime import UTC, datetime


def memory_used_mb() -> float:
    if sys.platform == "win32":
        class MemStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        status = MemStatus()
        status.dwLength = ctypes.sizeof(MemStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return (status.ullTotalPhys - status.ullAvailPhys) / 1024 / 1024
    info = {}
    with open("/proc/meminfo", encoding="utf-8") as fh:
        for line in fh:
            key, value = line.split(":", 1)
            info[key] = float(value.split()[0])
    return (info["MemTotal"] - info["MemAvailable"]) / 1024


def collect(path: str, samples: int, interval: float) -> None:
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if new:
            writer.writerow(["timestamp", "value", "source_type"])
        for i in range(samples):
            writer.writerow(
                [datetime.now(UTC).isoformat(), round(memory_used_mb(), 2), "direct_sensor"]
            )
            if i < samples - 1:
                time.sleep(interval)
