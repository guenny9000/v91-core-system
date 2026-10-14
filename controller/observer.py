#!/usr/bin/env python3
"""Real local observer for V91 queue and action-log state; no synthetic metrics."""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUEUE_ROOT = Path(os.getenv("V91_QUEUE_DIR", str(ROOT / "queue"))).resolve()
RUNTIME_ROOT = Path(os.getenv("V91_RUNTIME_DIR", str(ROOT / "runtime"))).resolve()
POLL_SECONDS = int(os.getenv("V91_OBSERVER_POLL_SECONDS", "10"))
STOP = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def count_tasks(name: str) -> int | None:
    path = QUEUE_ROOT / name
    try:
        return sum(1 for item in path.iterdir() if item.is_file() and item.suffix == ".json")
    except FileNotFoundError:
        return 0
    except OSError:
        return None


def inspect_action_log() -> dict[str, Any]:
    path = RUNTIME_ROOT / "v91-actions.jsonl"
    summary: dict[str, Any] = {"events": 0, "parse_errors": 0, "last_event": None}
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError("event is not an object")
                except (json.JSONDecodeError, ValueError):
                    summary["parse_errors"] += 1
                    continue
                summary["events"] += 1
                summary["last_event"] = {
                    "timestamp_utc": event.get("timestamp_utc"),
                    "phase": event.get("phase"),
                    "status": event.get("status") or event.get("action_status"),
                    "task_id": event.get("task_id"),
                    "action": event.get("action"),
                }
    except FileNotFoundError:
        pass
    except OSError:
        summary["parse_errors"] += 1
    return summary


def snapshot() -> dict[str, Any]:
    counts = {name: count_tasks(name) for name in ("pending", "processing", "done", "failed")}
    audit = inspect_action_log()
    known = all(value is not None for value in counts.values())
    status = "OBSERVED" if known and audit["parse_errors"] == 0 else "PENDING_WITNESS"
    return {
        "timestamp_utc": utc_now(),
        "source": "LOCAL_FILESYSTEM",
        "status": status,
        "evidence_status": "OBSERVED_LOCAL_STATE" if status == "OBSERVED" else "INCOMPLETE_OR_CORRUPT",
        "queue_counts": counts,
        "audit": audit,
        "note": "This is local queue/log state, not proof of model correctness or production availability.",
    }


def _stop(_signum: int, _frame: Any) -> None:
    global STOP
    STOP = True


def main() -> int:
    if not 5 <= POLL_SECONDS <= 3600:
        print("V91_OBSERVER_POLL_SECONDS must be between 5 and 3600.", file=sys.stderr)
        return 2
    for name in ("pending", "processing", "done", "failed"):
        (QUEUE_ROOT / name).mkdir(parents=True, exist_ok=True)
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    while not STOP:
        data = snapshot()
        atomic_write(RUNTIME_ROOT / "v91-observer.json", data)
        print(json.dumps(data, sort_keys=True), flush=True)
        time.sleep(POLL_SECONDS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
