#!/usr/bin/env python3
"""V91 bounded Docker Compose controller.

Runs on the Docker host, not inside the controller container. It observes real
Compose/Docker state, records a decision before any change, and only scales the
single allow-listed `worker` service. No shell is used and no arbitrary command
can be supplied through metrics or action data.

Real actions require V91_ENABLE_REAL_ACTIONS=1 and V91_PROJECT_NAME to match the
existing Compose project. Without explicit opt-in this is observe-and-plan only.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPOSE = ROOT / "docker-compose.yml"
ALLOWED_SERVICE = "worker"
MIN_REPLICAS = 1
MAX_REPLICAS = 3
SCALE_UP_CPU = 75.0
SCALE_UP_MEMORY = 80.0
SCALE_DOWN_CPU = 20.0
SCALE_DOWN_MEMORY = 50.0
LOW_SAMPLES_REQUIRED = 3


class ControlError(RuntimeError):
    """A runtime observation or control step could not be verified."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_json_lines(raw: str) -> list[dict[str, Any]]:
    """Accept Docker Compose's JSON array or newline-delimited JSON objects."""
    raw = raw.strip()
    if not raw:
        return []
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            if not all(isinstance(item, dict) for item in value):
                raise ControlError("Docker output contains a non-object entry.")
            return value
        if isinstance(value, dict):
            return [value]
        raise ControlError("Docker output is not a JSON object or array.")
    except json.JSONDecodeError:
        records = []
        for line_number, line in enumerate(raw.splitlines(), 1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ControlError(f"Invalid Docker JSON on line {line_number}.") from exc
            if not isinstance(item, dict):
                raise ControlError(f"Docker JSON line {line_number} is not an object.")
            records.append(item)
        return records


def parse_percent(value: Any) -> float:
    if not isinstance(value, str) or not value.strip().endswith("%"):
        raise ControlError("Docker returned a missing or malformed percentage.")
    try:
        result = float(value.strip()[:-1])
    except ValueError as exc:
        raise ControlError("Docker returned a non-numeric percentage.") from exc
    if not math.isfinite(result) or result < 0:
        raise ControlError("Docker returned an invalid percentage.")
    return result


def run_command(args: list[str], timeout: int = 25) -> str:
    """Run a fixed argument vector; never invokes a shell."""
    try:
        result = subprocess.run(
            args, check=False, capture_output=True, text=True, timeout=timeout,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ControlError(f"Command could not be completed: {args[0]} ({type(exc).__name__}).") from exc
    if result.returncode != 0:
        # Do not expose arbitrary command output as instructions or executable data.
        detail = result.stderr.strip()[-500:]
        raise ControlError(f"Command failed ({result.returncode}): {args[0]}; {detail}")
    return result.stdout


def compose_prefix(compose_file: Path, project_name: str) -> list[str]:
    if not project_name or not all(ch.isalnum() or ch in "-_" for ch in project_name):
        raise ControlError("V91_PROJECT_NAME must be an explicit Compose project name.")
    if not compose_file.is_absolute() or not compose_file.is_file():
        raise ControlError("Compose file must be an existing absolute path.")
    return ["docker", "compose", "--project-name", project_name, "--file", str(compose_file)]


def collect_snapshot(compose_file: Path, project_name: str) -> dict[str, Any]:
    """Read actual container state and Docker resource metrics; no synthetic fallback."""
    prefix = compose_prefix(compose_file, project_name)
    services = run_command(prefix + ["config", "--services"]).splitlines()
    if ALLOWED_SERVICE not in {service.strip() for service in services}:
        raise ControlError("Configured Compose project does not define the allow-listed worker service.")

    ps_records = parse_json_lines(run_command(prefix + ["ps", "--all", "--format", "json"]))
    workers = []
    for item in ps_records:
        service = item.get("Service") or item.get("service")
        if service == ALLOWED_SERVICE:
            workers.append(item)
    if not workers:
        raise ControlError("No worker containers were found; refusing to infer a healthy baseline.")

    stats_records = parse_json_lines(run_command([
        "docker", "stats", "--no-stream", "--format", "{{json .}}"
    ]))
    stats_by_name = {}
    for item in stats_records:
        name = item.get("Name") or item.get("name") or item.get("Container")
        if isinstance(name, str) and name:
            stats_by_name[name.lstrip("/")]=item

    observed = []
    for item in workers:
        name = item.get("Name") or item.get("name")
        state = str(item.get("State") or item.get("state") or "").lower()
        health = str(item.get("Health") or item.get("health") or "").lower()
        if not isinstance(name, str) or not name:
            raise ControlError("A worker container has no identifiable name.")
        stats = stats_by_name.get(name.lstrip("/"))
        if state != "running" or health in {"unhealthy", "starting"} or stats is None:
            raise ControlError("Worker state is not fully measurable/healthy; no automatic action allowed.")
        observed.append({
            "name": name,
            "state": state,
            "health": health or "not-reported",
            "cpu_percent": parse_percent(stats.get("CPUPerc") or stats.get("CPUPerc".lower())),
            "memory_percent": parse_percent(stats.get("MemPerc") or stats.get("MemPerc".lower())),
        })

    return {
        "timestamp_utc": utc_now(),
        "source": "DOCKER_LIVE",
        "project": project_name,
        "service": ALLOWED_SERVICE,
        "replicas": len(workers),
        "running": sum(1 for item in observed if item["state"] == "running"),
        "max_cpu_percent": max(item["cpu_percent"] for item in observed),
        "max_memory_percent": max(item["memory_percent"] for item in observed),
        "containers": observed,
    }


def read_low_sample_count(state_path: Path) -> int:
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        count = data.get("low_resource_samples", 0)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            return 0
        return min(count, LOW_SAMPLES_REQUIRED)
    except FileNotFoundError:
        return 0
    except (OSError, json.JSONDecodeError):
        # Corrupt state must not accelerate scale-down.
        return 0


def write_state(state_path: Path, low_samples: int) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temp = state_path.with_name(state_path.name + "." + uuid.uuid4().hex + ".tmp")
    payload = {"low_resource_samples": low_samples, "updated_at_utc": utc_now()}
    try:
        with temp.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, state_path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def decide(snapshot: dict[str, Any], low_samples: int) -> tuple[str | None, int, str]:
    """Return action, next low-sample count, and a plain-language reason."""
    replicas = snapshot["replicas"]
    cpu = snapshot["max_cpu_percent"]
    memory = snapshot["max_memory_percent"]
    if replicas < MIN_REPLICAS or replicas > MAX_REPLICAS:
        return None, 0, "Replica count is outside configured safety bounds."
    if (cpu >= SCALE_UP_CPU or memory >= SCALE_UP_MEMORY) and replicas < MAX_REPLICAS:
        return "scale_up_workers", 0, (
            f"Live Docker metrics exceed a scale-up threshold (CPU {cpu:.1f}%, "
            f"memory {memory:.1f}%); target {replicas + 1} replicas."
        )
    if cpu <= SCALE_DOWN_CPU and memory <= SCALE_DOWN_MEMORY and replicas > MIN_REPLICAS:
        next_count = min(low_samples + 1, LOW_SAMPLES_REQUIRED)
        if next_count >= LOW_SAMPLES_REQUIRED:
            return "scale_down_workers", next_count, (
                f"Low CPU ({cpu:.1f}%) and memory ({memory:.1f}%) persisted "
                f"for {LOW_SAMPLES_REQUIRED} samples; target {replicas - 1} replicas."
            )
        return None, next_count, (
            f"Low resource use sample {next_count}/{LOW_SAMPLES_REQUIRED}; "
            "waiting to avoid scaling oscillation."
        )
    return None, 0, (
        f"No threshold met (CPU {cpu:.1f}%, memory {memory:.1f}%, replicas {replicas})."
    )


def append_audit(audit_path: Path, event: dict[str, Any]) -> None:
    """Append one JSON event with an exclusive lock; never rewrites history."""
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = audit_path.with_name(audit_path.name + ".lock")
    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ControlError(f"Audit lock already exists: {lock_path}; inspect it, do not delete blindly.") from exc
    try:
        os.write(lock_fd, f"pid={os.getpid()} timestamp={utc_now()}\n".encode("utf-8"))
        os.fsync(lock_fd)
        with audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(lock_fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def scale_worker(compose_file: Path, project_name: str, replicas: int) -> None:
    if isinstance(replicas, bool) or not isinstance(replicas, int) or not MIN_REPLICAS <= replicas <= MAX_REPLICAS:
        raise ControlError("Requested worker replica count is outside the hard-coded 1..3 limit.")
    prefix = compose_prefix(compose_file, project_name)
    run_command(prefix + ["up", "--detach", "--scale", f"{ALLOWED_SERVICE}={replicas}", ALLOWED_SERVICE], timeout=120)


def run_cycle(compose_file: Path, project_name: str, runtime_dir: Path, allow_actions: bool) -> dict[str, Any]:
    if not runtime_dir.is_absolute():
        raise ControlError("Runtime directory must be absolute.")
    audit_path = runtime_dir / "v91-actions.jsonl"
    state_path = runtime_dir / "v91-controller-state.json"
    snapshot = collect_snapshot(compose_file, project_name)
    low_samples = read_low_sample_count(state_path)
    action, next_low_samples, reason = decide(snapshot, low_samples)
    write_state(state_path, next_low_samples)
    event_id = str(uuid.uuid4())
    target = snapshot["replicas"]
    if action == "scale_up_workers":
        target += 1
    elif action == "scale_down_workers":
        target -= 1
    event = {
        "event_id": event_id,
        "timestamp_utc": utc_now(),
        "phase": "DECISION",
        "source": snapshot["source"],
        "project": project_name,
        "service": ALLOWED_SERVICE,
        "observed": snapshot,
        "action": action or "NO_ACTION",
        "reason": reason,
        "before_replicas": snapshot["replicas"],
        "target_replicas": target,
        "authorization": "ENABLED" if allow_actions else "NOT_ENABLED",
        "expected_effect": (
            "Increase worker capacity by one replica."
            if action == "scale_up_workers" else
            "Reduce one worker replica after sustained low resource use."
            if action == "scale_down_workers" else
            "No infrastructure change."
        ),
        "rollback_plan": f"Restore worker replica count to {snapshot['replicas']} if post-check fails.",
        "status": "PROPOSED_NOT_EXECUTED" if action and not allow_actions else "NO_ACTION",
    }
    append_audit(audit_path, event)
    result = dict(event)
    if not action or not allow_actions:
        return result

    try:
        scale_worker(compose_file, project_name, target)
        post = collect_snapshot(compose_file, project_name)
        if post["replicas"] != target or post["running"] != target:
            raise ControlError("Post-action replica count or running-state verification failed.")
        append_audit(audit_path, {
            "event_id": event_id, "timestamp_utc": utc_now(), "phase": "VERIFY",
            "source": "DOCKER_LIVE", "before_replicas": snapshot["replicas"],
            "target_replicas": target, "after": post, "status": "VERIFIED",
        })
        result.update({"status": "VERIFIED", "after": post})
        return result
    except Exception as exc:
        rollback_status = "ROLLBACK_FAILED"
        rollback_detail = type(exc).__name__
        try:
            scale_worker(compose_file, project_name, snapshot["replicas"])
            rollback = collect_snapshot(compose_file, project_name)
            if rollback["replicas"] == snapshot["replicas"] and rollback["running"] == snapshot["replicas"]:
                rollback_status = "ROLLED_BACK"
            else:
                rollback_detail = "Rollback post-check did not match the original replica count."
        except Exception as rollback_exc:
            rollback_detail = f"{type(exc).__name__}; rollback {type(rollback_exc).__name__}"
        append_audit(audit_path, {
            "event_id": event_id, "timestamp_utc": utc_now(), "phase": "ROLLBACK",
            "source": "DOCKER_LIVE", "before_replicas": snapshot["replicas"],
            "attempted_replicas": target, "status": rollback_status,
            "failure_type": type(exc).__name__, "rollback_detail": rollback_detail,
        })
        result.update({"status": rollback_status, "failure_type": type(exc).__name__})
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="observe and decide once (default)")
    parser.add_argument("--watch", action="store_true", help="repeat bounded observation cycles")
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--compose-file", default=os.getenv("V91_COMPOSE_FILE", str(DEFAULT_COMPOSE)))
    parser.add_argument("--project", default=os.getenv("V91_PROJECT_NAME", ""))
    parser.add_argument("--runtime-dir", default=os.getenv("V91_RUNTIME_DIR", str(ROOT / "runtime")))
    args = parser.parse_args(argv)
    if args.interval_seconds < 15 or args.interval_seconds > 3600:
        parser.error("--interval-seconds must be between 15 and 3600")
    if args.watch and not args.project:
        parser.error("Set V91_PROJECT_NAME to the existing Docker Compose project name.")
    compose_file = Path(args.compose_file).expanduser().resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    allow_actions = os.getenv("V91_ENABLE_REAL_ACTIONS", "0").strip() == "1"
    if os.getenv("V91_ENABLE_REAL_ACTIONS", "0").strip() not in {"0", "1"}:
        parser.error("V91_ENABLE_REAL_ACTIONS must be exactly 0 or 1.")
    if not args.project:
        parser.error("Set V91_PROJECT_NAME to the existing Docker Compose project name.")
    while True:
        try:
            result = run_cycle(compose_file, args.project, runtime_dir, allow_actions)
            print(json.dumps(result, sort_keys=True, indent=2))
            if result["status"] in {"ROLLBACK_FAILED"}:
                return 2
        except ControlError as exc:
            print(json.dumps({
                "timestamp_utc": utc_now(), "status": "PENDING_WITNESS",
                "error_type": type(exc).__name__, "detail": str(exc),
            }, sort_keys=True), file=sys.stderr)
            return 2
        if not args.watch:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
