#!/usr/bin/env python3
"""Read-only V91 local dashboard.

This command reads the observer snapshot and filesystem state. It does not start,
stop, scale, repair, or deploy services. Missing evidence stays UNKNOWN.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME = ROOT / "runtime"
DEFAULT_QUEUE = ROOT / "queue"


def read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except FileNotFoundError:
        return None, "file not found"
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"unreadable or invalid JSON ({type(exc).__name__})"
    if not isinstance(value, dict):
        return None, "JSON root is not an object"
    return value, None


def read_observer(runtime_dir: Path) -> dict[str, Any]:
    path = runtime_dir / "v91-observer.json"
    data, error = read_json(path)
    if error:
        return {"status": "UNKNOWN", "reason": error, "source": str(path)}
    assert data is not None
    counts = data.get("queue_counts")
    audit = data.get("audit")
    if not isinstance(counts, dict) or not isinstance(audit, dict):
        return {"status": "UNKNOWN", "reason": "required observer fields are missing", "source": str(path)}
    expected = ("pending", "processing", "done", "failed")
    if any(not isinstance(counts.get(key), int) or isinstance(counts.get(key), bool) or counts[key] < 0 for key in expected):
        return {"status": "UNKNOWN", "reason": "queue counts are missing or invalid", "source": str(path)}
    if not isinstance(audit.get("parse_errors"), int) or audit["parse_errors"] < 0:
        return {"status": "UNKNOWN", "reason": "audit parse-error count is missing or invalid", "source": str(path)}
    status = "OBSERVED" if data.get("status") == "OBSERVED" and audit["parse_errors"] == 0 else "PENDING_WITNESS"
    return {
        "status": status,
        "timestamp_utc": data.get("timestamp_utc"),
        "source": data.get("source", "UNKNOWN"),
        "queue_counts": {key: counts[key] for key in expected},
        "audit": {
            "events": audit.get("events") if isinstance(audit.get("events"), int) else None,
            "parse_errors": audit["parse_errors"],
            "last_event": audit.get("last_event") if isinstance(audit.get("last_event"), dict) else None,
        },
        "note": "Local queue/log state only; not proof of model correctness, API availability, backup recovery, or production health.",
    }


def build_report(runtime_dir: Path = DEFAULT_RUNTIME, queue_dir: Path = DEFAULT_QUEUE, disk_path: Path = ROOT) -> dict[str, Any]:
    observer = read_observer(runtime_dir)
    try:
        usage = shutil.disk_usage(disk_path)
        disk = {
            "status": "OBSERVED",
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_percent": round((usage.used / usage.total) * 100, 2) if usage.total else None,
        }
    except OSError as exc:
        disk = {"status": "UNKNOWN", "reason": type(exc).__name__}

    queue_dirs: dict[str, Any] = {}
    for name in ("pending", "processing", "done", "failed"):
        path = queue_dir / name
        try:
            queue_dirs[name] = sum(1 for item in path.iterdir() if item.is_file() and item.suffix == ".json")
        except FileNotFoundError:
            queue_dirs[name] = "UNKNOWN"
        except OSError:
            queue_dirs[name] = "UNKNOWN"

    overall = "OBSERVED" if observer.get("status") == "OBSERVED" and disk.get("status") == "OBSERVED" else "UNKNOWN_OR_INCOMPLETE"
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "overall_status": overall,
        "observer": observer,
        "queue_filesystem_counts": queue_dirs,
        "disk": disk,
        "not_checked": {
            "service_liveness": "UNKNOWN",
            "API_health": "UNKNOWN",
            "backup_transfer_and_restore": "UNKNOWN",
            "production_deployment": "UNKNOWN",
        },
        "side_effects": "NONE_READ_ONLY",
    }


def render_text(report: dict[str, Any]) -> str:
    observer = report["observer"]
    lines = [
        "V91 LOCAL STATUS DASHBOARD (READ ONLY)",
        f"Overall: {report['overall_status']}",
        f"Observer: {observer.get('status', 'UNKNOWN')}",
    ]
    if observer.get("reason"):
        lines.append(f"Observer detail: {observer['reason']}")
    if observer.get("timestamp_utc"):
        lines.append(f"Observer timestamp (UTC): {observer['timestamp_utc']}")
    counts = observer.get("queue_counts")
    if isinstance(counts, dict):
        lines.append("Observer queue counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    audit = observer.get("audit")
    if isinstance(audit, dict):
        lines.append(f"Audit events={audit.get('events', 'UNKNOWN')}; parse errors={audit.get('parse_errors', 'UNKNOWN')}")
        last = audit.get("last_event")
        if isinstance(last, dict):
            lines.append(f"Last audit event: phase={last.get('phase', 'UNKNOWN')}; status={last.get('status', 'UNKNOWN')}; task={last.get('task_id', 'UNKNOWN')}")
    disk = report["disk"]
    if disk.get("status") == "OBSERVED":
        lines.append(f"Disk: {disk['used_percent']}% used; {disk['free_bytes']} bytes free")
    else:
        lines.append(f"Disk: UNKNOWN ({disk.get('reason', 'no data')})")
    lines.append("Not checked: service liveness, API health, backup/restore, production deployment.")
    lines.append("No services were started, stopped, scaled, repaired, or deployed.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--queue-dir", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--disk-path", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    report = build_report(args.runtime_dir, args.queue_dir, args.disk_path)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_text(report))
    return 0 if report["overall_status"] == "OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
