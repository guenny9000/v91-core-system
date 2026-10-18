#!/usr/bin/env python3
"""
V91 Hardware Telemetry Adapter (v91_hardware_adapter.py)
Status: ACTIVE / READ-ONLY / AUDIT-VERIFIED
Zweck: Passiver, rein lesender Hardware-Adapter zur Erhebung echter,
physikalisch verifizierter Telemetriewerte (CPU, RAM, GPU, OS) ohne Root-Rechte
und ohne externe Drittanbieter-Bibliotheken (reine Standard-Bibliothek).
"""

import os
import sys
import time
import json
import platform
import subprocess

def get_platform_telemetry():
    """Liest passive Betriebssystem- und Hardware-Werte ohne externe Abhaengigkeiten."""
    telemetry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "os_type": sys.platform,
        "platform_release": platform.release(),
        "cpu_model": "UNKNOWN",
        "cpu_cores_physical": "UNKNOWN",
        "cpu_cores_logical": "UNKNOWN",
        "cpu_load_percent": "UNKNOWN",
        "ram_total_mb": "UNKNOWN",
        "ram_available_mb": "UNKNOWN",
        "ram_load_percent": "UNKNOWN",
        "gpu_devices": [],
        "source": "OS_API_PASSIVE"
    }

    # 1. CPU & RAM auf Linux (Solar-Desktop / Pi / Edge-Node)
    if sys.platform.startswith("linux"):
        if hasattr(os, "getloadavg"):
            try:
                telemetry["cpu_load_percent"] = round(os.getloadavg()[0] * 100 / (os.cpu_count() or 1), 2)
            except Exception:
                pass
        try:
            telemetry["cpu_cores_logical"] = os.cpu_count()
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        telemetry["cpu_model"] = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass

        try:
            with open("/proc/meminfo", "r") as f:
                mem_total = 0
                mem_avail = 0
                for line in f:
                    if "MemTotal" in line:
                        mem_total = int(line.split()[1])
                    elif "MemAvailable" in line:
                        mem_avail = int(line.split()[1])
                if mem_total > 0:
                    telemetry["ram_total_mb"] = round(mem_total / 1024, 2)
                    telemetry["ram_available_mb"] = round(mem_avail / 1024, 2)
                    telemetry["ram_load_percent"] = round((1 - mem_avail / mem_total) * 100, 2)
        except Exception:
            pass

    # 2. CPU & RAM auf Windows (win32)
    elif sys.platform == "win32":
        telemetry["cpu_cores_logical"] = os.cpu_count()
        # CPU-Modell via Registry oder Umgebung
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            cpu_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            telemetry["cpu_model"] = cpu_name.strip()
            winreg.CloseKey(key)
        except Exception:
            pass

        # CPU-Auslastung passiv ueber GetSystemTimes (100ms Delta)
        try:
            import ctypes
            class FILETIME(ctypes.Structure):
                _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

            def ft_val(ft):
                return (ft.dwHighDateTime << 32) + ft.dwLowDateTime

            def read_times():
                idle = FILETIME()
                kernel = FILETIME()
                user = FILETIME()
                if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                    return ft_val(idle), ft_val(kernel), ft_val(user)
                return None

            t1 = read_times()
            if t1:
                time.sleep(0.12)
                t2 = read_times()
                if t2:
                    idle_delta = t2[0] - t1[0]
                    kernel_delta = t2[1] - t1[1]
                    user_delta = t2[2] - t1[2]
                    total_delta = kernel_delta + user_delta
                    if total_delta > 0:
                        telemetry["cpu_load_percent"] = round((total_delta - idle_delta) * 100.0 / total_delta, 2)
        except Exception:
            pass

        # RAM via GlobalMemoryStatusEx
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                telemetry["ram_available_mb"] = round(stat.ullAvailPhys / (1024 * 1024), 2)
                telemetry["ram_total_mb"] = round(stat.ullTotalPhys / (1024 * 1024), 2)
                telemetry["ram_load_percent"] = stat.dwMemoryLoad
        except Exception:
            pass

    # 3. GPU Telemetrie (NVIDIA SMI oder System-Abfrage mit Driver-Overhead Beruecksichtigung)
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used,memory.reserved,utilization.gpu,temperature.gpu,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if proc.returncode == 0:
            for line in proc.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 8:
                    telemetry["gpu_devices"].append({
                        "name": parts[0],
                        "vram_total_mb": float(parts[1]),
                        "vram_free_mb": float(parts[2]),
                        "vram_used_mb": float(parts[3]),
                        "vram_reserved_mb": float(parts[4]),
                        "vram_sum_check_mb": round(float(parts[2]) + float(parts[3]) + float(parts[4]), 2),
                        "gpu_utilization_percent": float(parts[5]),
                        "temperature_celsius": float(parts[6]),
                        "driver_version": parts[7]
                    })
    except Exception:
        pass

    return telemetry

if __name__ == "__main__":
    data = get_platform_telemetry()
    print(json.dumps(data, indent=2))
