#!/usr/bin/env python3
"""Offline V91 task worker: bounded file-verification tasks, no shell or network."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import signal
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_control import ControlError, append_audit

ROOT = Path(__file__).resolve().parents[1]
QUEUE_ROOT = Path(os.getenv("V91_QUEUE_DIR", str(ROOT / "queue"))).resolve()
RUNTIME_ROOT = Path(os.getenv("V91_RUNTIME_DIR", str(ROOT / "runtime"))).resolve()
WORKSPACE_ROOT = Path(os.getenv("V91_WORKSPACE_DIR", str(ROOT / "workspace"))).resolve()
POLL_SECONDS = float(os.getenv("V91_WORKER_POLL_SECONDS", "1"))
TASK_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
ALLOWED_ACTIONS = {"health_snapshot", "sha256_file", "verify_sha256"}
STARTED = time.monotonic()
STOP = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ensure_layout() -> None:
    for name in ("pending", "processing", "done", "failed"):
        (QUEUE_ROOT / name).mkdir(parents=True, exist_ok=True)
    (RUNTIME_ROOT / "results").mkdir(parents=True, exist_ok=True)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


def workspace_file(relative_path: Any) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ControlError("relative_path is required.")
    raw = Path(relative_path)
    if raw.is_absolute() or any(part in {"..", "."} for part in raw.parts):
        raise ControlError("Only normalized relative paths inside the workspace are allowed.")
    candidate = WORKSPACE_ROOT
    for part in raw.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ControlError("Symbolic links are not allowed in workspace tasks.")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ControlError("Requested workspace file does not exist.") from exc
    if not resolved.is_relative_to(WORKSPACE_ROOT) or not resolved.is_file():
        raise ControlError("Requested path is not a regular file inside the workspace.")
    return resolved


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            digest.update(block)
    return digest.hexdigest(), size


def atomic_result(task_id: str, payload: dict[str, Any]) -> Path:
    if not TASK_ID_RE.fullmatch(task_id):
        raise ControlError("Invalid task_id.")
    result_path = RUNTIME_ROOT / "results" / f"{task_id}.json"
    encoded = (json.dumps(payload, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")
    try:
        fd = os.open(str(result_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ControlError("A result already exists for this task_id; refusing to overwrite it.") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            result_path.unlink()
        except OSError:
            pass
        raise
    return result_path


def execute_task(task: dict[str, Any], task_id: str) -> dict[str, Any]:
    if not isinstance(task, dict):
        raise ControlError("Task document must be a JSON object.")
    allowed_fields = {"task_id", "action", "relative_path", "expected_sha256"}
    if set(task) - allowed_fields:
        raise ControlError("Task contains unsupported fields.")
    if task.get("task_id") != task_id or not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        raise ControlError("Task ID must match its filename and the permitted ID format.")
    action = task.get("action")
    if action not in ALLOWED_ACTIONS:
        raise ControlError("Unknown task action.")
    base = {
        "task_id": task_id,
        "action": action,
        "timestamp_utc": utc_now(),
        "source": "LOCAL_WORKER",
        "evidence_status": "OBSERVED_LOCAL_STATE",
    }
    if action == "health_snapshot":
        pending = sum(1 for _ in (QUEUE_ROOT / "pending").glob("*.json"))
        processing = sum(1 for _ in (QUEUE_ROOT / "processing").glob("*.json"))
        return {
            **base, "status": "COMPLETED", "worker_id": f"{socket.gethostname()}:{os.getpid()}",
            "uptime_seconds": round(time.monotonic() - STARTED, 3),
            "pending_tasks": pending, "processing_tasks": processing,
        }

    path = workspace_file(task.get("relative_path"))
    digest, size = sha256_file(path)
    base.update({"relative_path": task["relative_path"], "sha256": digest, "size_bytes": size})
    if action == "sha256_file":
        return {**base, "status": "COMPLETED"}
    expected = task.get("expected_sha256")
    if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
        raise ControlError("expected_sha256 must contain exactly 64 hexadecimal characters.")
    matches = hmac.compare_digest(digest.lower(), expected.lower())
    return {**base, "status": "COMPLETED", "matches_expected": matches}


def claim_one() -> Path | None:
    pending_dir = QUEUE_ROOT / "pending"
    processing_dir = QUEUE_ROOT / "processing"
    for source in sorted(pending_dir.glob("*.json")):
        target = processing_dir / f"{source.stem}.{socket.gethostname()}.{os.getpid()}.{uuid.uuid4().hex}.json"
        try:
            os.rename(source, target)
            return target
        except FileNotFoundError:
            continue
        except FileExistsError:
            continue
    return None


def process_one() -> bool:
    claimed = claim_one()
    if claimed is None:
        return False
    task_id = claimed.name.split(".", 1)[0]
    try:
        append_audit(RUNTIME_ROOT / "v91-actions.jsonl", {
            "timestamp_utc": utc_now(), "phase": "TASK_CLAIMED",
            "task_id": task_id, "worker_id": f"{socket.gethostname()}:{os.getpid()}",
            "source": "LOCAL_QUEUE", "status": "CLAIMED",
        })
        task = json.loads(claimed.read_text(encoding="utf-8"))
        result = execute_task(task, task_id)
        result_path = atomic_result(task_id, result)
        append_audit(RUNTIME_ROOT / "v91-actions.jsonl", {
            "timestamp_utc": utc_now(), "phase": "TASK_COMPLETED",
            "task_id": task_id, "result_file": result_path.name,
            "source": "LOCAL_WORKER", "status": result["status"],
            "action": result["action"],
        })
        destination = QUEUE_ROOT / "done" / claimed.name
        os.rename(claimed, destination)
    except Exception as exc:
        failure = {
            "task_id": task_id, "timestamp_utc": utc_now(), "source": "LOCAL_WORKER",
            "status": "FAILED", "error_type": type(exc).__name__,
            "detail": str(exc) if isinstance(exc, ControlError) else "Task failed; internal details withheld.",
        }
        try:
            atomic_result(task_id, failure)
        except Exception:
            pass
        try:
            append_audit(RUNTIME_ROOT / "v91-actions.jsonl", {
                "timestamp_utc": utc_now(), "phase": "TASK_FAILED",
                "task_id": task_id, "source": "LOCAL_WORKER", "status": "FAILED",
                "error_type": type(exc).__name__,
            })
        finally:
            failed_path = QUEUE_ROOT / "failed" / claimed.name
            try:
                os.rename(claimed, failed_path)
            except OSError:
                pass
    return True


def _stop(_signum: int, _frame: Any) -> None:
    global STOP
    STOP = True


def main() -> int:
    global POLL_SECONDS
    try:
        if not (0.2 <= POLL_SECONDS <= 60):
            raise ValueError("V91_WORKER_POLL_SECONDS must be between 0.2 and 60.")
    except (TypeError, ValueError):
        print("Invalid worker polling interval; must be between 0.2 and 60 seconds.", file=sys.stderr)
        return 2
    ensure_layout()
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    print(json.dumps({
        "timestamp_utc": utc_now(), "status": "WORKER_READY",
        "mode": "OFFLINE_TASK_QUEUE", "allowed_actions": sorted(ALLOWED_ACTIONS),
        "network_calls": "NONE", "shell_execution": "NONE",
    }, sort_keys=True), flush=True)
    while not STOP:
        try:
            worked = process_one()
        except Exception as exc:
            print(json.dumps({
                "timestamp_utc": utc_now(), "status": "PENDING_WITNESS",
                "error_type": type(exc).__name__,
            }, sort_keys=True), file=sys.stderr, flush=True)
            worked = False
        if not worked:
            time.sleep(POLL_SECONDS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
