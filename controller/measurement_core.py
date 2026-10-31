#!/usr/bin/env python3
"""V91 read-only measurement core.

Collects only measurements for which a real source is available. Missing
sources remain UNKNOWN; ecological values are deliberately not estimated.
The JSONL ledger is hash-chained for tamper detection, not WORM storage.
No network, shell, Docker control, or system configuration changes are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENESIS = "0" * 64
SCHEMA_VERSION = "v91.measurement.v1"


class MeasurementError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def metric(value: float | int | None, unit: str, source: str, reason: str | None = None) -> dict[str, Any]:
    if value is None:
        return {"value": None, "unit": unit, "status": "UNKNOWN", "source": source, "reason": reason or "No verified source available"}
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MeasurementError("Metric value must be numeric or None")
    if isinstance(value, int):
        if value < 0:
            raise MeasurementError("Metric value must be finite and non-negative")
        number: int | float = value
    else:
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise MeasurementError("Metric value must be finite and non-negative")
    if unit == "%" and number > 100:
        raise MeasurementError("Percentage metrics must be between 0 and 100")
    return {"value": number, "unit": unit, "status": "DATA_AVAILABLE", "source": source}


def collect_snapshot(root: Path | None = None) -> dict[str, Any]:
    """Collect read-only host measurements; optional psutil enables CPU/RAM/I/O."""
    root = (root or Path.cwd()).resolve()
    measured_at = utc_now()
    measurements: dict[str, Any] = {}

    try:
        import psutil  # type: ignore
        cpu = psutil.cpu_percent(interval=0.2)
        memory = psutil.virtual_memory().percent
        measurements["cpu_percent"] = metric(cpu, "%", "psutil.cpu_percent(interval=0.2)")
        measurements["memory_percent"] = metric(memory, "%", "psutil.virtual_memory")
        try:
            disk_io = psutil.disk_io_counters()
            if disk_io is None:
                raise RuntimeError("disk I/O counters unavailable")
            measurements["disk_read_bytes"] = metric(disk_io.read_bytes, "bytes", "psutil.disk_io_counters")
            measurements["disk_write_bytes"] = metric(disk_io.write_bytes, "bytes", "psutil.disk_io_counters")
        except Exception as exc:
            measurements["disk_read_bytes"] = metric(None, "bytes", "psutil", type(exc).__name__)
            measurements["disk_write_bytes"] = metric(None, "bytes", "psutil", type(exc).__name__)
    except ImportError:
        for key, unit in (("cpu_percent", "%"), ("memory_percent", "%"), ("disk_read_bytes", "bytes"), ("disk_write_bytes", "bytes")):
            measurements[key] = metric(None, unit, "psutil_optional_dependency", "psutil is not installed")
    except Exception as exc:
        for key, unit in (("cpu_percent", "%"), ("memory_percent", "%"), ("disk_read_bytes", "bytes"), ("disk_write_bytes", "bytes")):
            measurements[key] = metric(None, unit, "psutil", type(exc).__name__)

    try:
        usage = shutil.disk_usage(root)
        used_percent = ((usage.total - usage.free) / usage.total * 100.0) if usage.total else None
        measurements["disk_used_percent"] = metric(used_percent, "%", f"shutil.disk_usage:{root}")
        measurements["disk_total_bytes"] = metric(usage.total, "bytes", f"shutil.disk_usage:{root}")
        measurements["disk_free_bytes"] = metric(usage.free, "bytes", f"shutil.disk_usage:{root}")
    except Exception as exc:
        for key, unit in (("disk_used_percent", "%"), ("disk_total_bytes", "bytes"), ("disk_free_bytes", "bytes")):
            measurements[key] = metric(None, unit, "shutil.disk_usage", type(exc).__name__)

    # These require physical meters or trusted external accounting. Never infer them.
    measurements["energy_wh"] = metric(None, "Wh", "physical_energy_meter", "No physical energy meter connected")
    measurements["water_litres"] = metric(None, "L", "physical_water_meter", "No physical water meter connected")
    measurements["co2e_grams"] = metric(None, "gCO2e", "verified_emissions_factor_and_activity_data", "No verified activity data or emissions factor connected")
    measurements["material_grams"] = metric(None, "g", "weighed_material_input", "No weighing source connected")

    return {
        "schema": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "measured_at_utc": measured_at,
        "collection_mode": "READ_ONLY",
        "host_measurements": measurements,
        "ecological_measurements": {
            key: measurements[key] for key in ("energy_wh", "water_litres", "co2e_grams", "material_grams")
        },
    }


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def event_hash(previous_hash: str, payload: dict[str, Any]) -> str:
    digest_input = previous_hash.encode("ascii") + b"\n" + canonical_json(payload).encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()


def verify_ledger(path: Path) -> dict[str, Any]:
    previous = GENESIS
    expected_sequence = 1
    if not path.exists():
        return {"status": "EMPTY_LEDGER", "events": 0, "last_hash": GENESIS}
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    raise MeasurementError(f"Blank ledger line at {line_number}")
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise MeasurementError(f"Invalid record at line {line_number}")
                supplied_hash = record.pop("event_hash", None)
                if record.get("sequence") != expected_sequence:
                    raise MeasurementError(f"Sequence mismatch at line {line_number}")
                if record.get("previous_hash") != previous:
                    raise MeasurementError(f"Previous hash mismatch at line {line_number}")
                calculated = event_hash(previous, record)
                if supplied_hash != calculated:
                    raise MeasurementError(f"Event hash mismatch at line {line_number}")
                previous = calculated
                expected_sequence += 1
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementError(f"Ledger cannot be read or parsed: {type(exc).__name__}") from exc
    return {"status": "CHAIN_VALID", "events": expected_sequence - 1, "last_hash": previous}


def append_snapshot(path: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Verify history, acquire an exclusive process lock, append, and fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        lock_fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise MeasurementError("Ledger lock exists; inspect it manually before retrying") from exc
    try:
        os.write(lock_fd, f"pid={os.getpid()} time={utc_now()}\n".encode("utf-8"))
        os.fsync(lock_fd)
        state = verify_ledger(path)
        payload = {
            "sequence": state["events"] + 1,
            "previous_hash": state["last_hash"],
            "recorded_at_utc": utc_now(),
            "snapshot": snapshot,
        }
        digest = event_hash(state["last_hash"], payload)
        record = dict(payload)
        record["event_hash"] = digest
        with path.open("a", encoding="utf-8") as stream:
            stream.write(canonical_json(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return {"status": "APPENDED_HASH_CHAINED", "sequence": payload["sequence"], "event_hash": digest}
    finally:
        os.close(lock_fd)
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", default="runtime/v91-measurements.jsonl")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    ledger = Path(args.ledger).expanduser().resolve()
    try:
        if args.verify_only:
            result = verify_ledger(ledger)
        else:
            snapshot = collect_snapshot(Path(args.root))
            result = {"measurement": snapshot, "ledger": append_snapshot(ledger, snapshot)}
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    except (MeasurementError, OSError) as exc:
        print(json.dumps({"status": "FAILED_CLOSED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
