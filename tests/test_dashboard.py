import json
from pathlib import Path

from scripts.v91_dashboard import build_report, read_observer, render_text


def write_observer(runtime: Path, *, status="OBSERVED", parse_errors=0):
    runtime.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp_utc": "2026-10-24T00:00:00Z",
        "source": "LOCAL_FILESYSTEM",
        "status": status,
        "queue_counts": {"pending": 1, "processing": 0, "done": 3, "failed": 0},
        "audit": {
            "events": 3,
            "parse_errors": parse_errors,
            "last_event": {"phase": "TASK_COMPLETED", "status": "COMPLETED", "task_id": "task-1"},
        },
    }
    (runtime / "v91-observer.json").write_text(json.dumps(payload), encoding="utf-8")


def test_dashboard_reports_observed_local_state_without_claiming_production(tmp_path):
    runtime = tmp_path / "runtime"
    queue = tmp_path / "queue"
    write_observer(runtime)
    for name in ("pending", "processing", "done", "failed"):
        (queue / name).mkdir(parents=True)
    (queue / "pending" / "task-1.json").write_text("{}", encoding="utf-8")

    report = build_report(runtime, queue, tmp_path)

    assert report["overall_status"] == "OBSERVED"
    assert report["observer"]["queue_counts"]["done"] == 3
    assert report["queue_filesystem_counts"]["pending"] == 1
    assert report["not_checked"]["API_health"] == "UNKNOWN"
    assert report["side_effects"] == "NONE_READ_ONLY"
    assert "production deployment" in render_text(report)


def test_missing_observer_is_unknown_not_zero_or_pass(tmp_path):
    report = read_observer(tmp_path / "missing")

    assert report["status"] == "UNKNOWN"
    assert "file not found" in report["reason"]


def test_malformed_observer_is_unknown(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "v91-observer.json").write_text("{broken", encoding="utf-8")

    report = read_observer(runtime)

    assert report["status"] == "UNKNOWN"
    assert "invalid JSON" in report["reason"]


def test_audit_parse_errors_prevent_observed_status(tmp_path):
    runtime = tmp_path / "runtime"
    write_observer(runtime, parse_errors=1)

    report = read_observer(runtime)

    assert report["status"] == "PENDING_WITNESS"


def test_invalid_queue_count_is_unknown(tmp_path):
    runtime = tmp_path / "runtime"
    write_observer(runtime)
    payload_path = runtime / "v91-observer.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["queue_counts"]["pending"] = -1
    payload_path.write_text(json.dumps(payload), encoding="utf-8")

    report = read_observer(runtime)

    assert report["status"] == "UNKNOWN"
