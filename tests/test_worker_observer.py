import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "controller"))
import observer
import worker
from runtime_control import ControlError


def configure_worker(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "QUEUE_ROOT", tmp_path / "queue")
    monkeypatch.setattr(worker, "RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(worker, "WORKSPACE_ROOT", tmp_path / "workspace")
    worker.ensure_layout()


def test_worker_hashes_real_workspace_file(monkeypatch, tmp_path):
    configure_worker(monkeypatch, tmp_path)
    (worker.WORKSPACE_ROOT / "evidence.txt").write_text("V91 evidence\n", encoding="utf-8")
    expected = hashlib.sha256(b"V91 evidence\n").hexdigest()
    result = worker.execute_task({
        "task_id": "job_01", "action": "verify_sha256",
        "relative_path": "evidence.txt", "expected_sha256": expected,
    }, "job_01")
    assert result["status"] == "COMPLETED"
    assert result["matches_expected"] is True
    assert result["verification_status"] == "MATCH"
    assert result["sha256"] == expected
    assert result["source"] == "LOCAL_WORKER"


@pytest.mark.parametrize("relative_path", ["../secret.txt", "/etc/passwd", "missing.txt"])
def test_worker_rejects_paths_outside_or_missing_from_workspace(monkeypatch, tmp_path, relative_path):
    configure_worker(monkeypatch, tmp_path)
    with pytest.raises(ControlError):
        worker.workspace_file(relative_path)


def test_worker_rejects_unknown_or_malformed_actions(monkeypatch, tmp_path):
    configure_worker(monkeypatch, tmp_path)
    for action in ("run_shell", ["sha256_file"], {"action": "sha256_file"}):
        with pytest.raises(ControlError):
            worker.execute_task({"task_id": "job_02", "action": action}, "job_02")


def test_worker_claims_processes_and_audits_task(monkeypatch, tmp_path):
    configure_worker(monkeypatch, tmp_path)
    (worker.WORKSPACE_ROOT / "sample.txt").write_text("real file", encoding="utf-8")
    task = {"task_id": "job_03", "action": "sha256_file", "relative_path": "sample.txt"}
    (worker.QUEUE_ROOT / "pending" / "job_03.json").write_text(json.dumps(task), encoding="utf-8")
    assert worker.process_one() is True
    result = json.loads((worker.RUNTIME_ROOT / "results" / "job_03.json").read_text(encoding="utf-8"))
    assert result["status"] == "COMPLETED"
    assert result["size_bytes"] == len(b"real file")
    assert len(list((worker.QUEUE_ROOT / "done").glob("*.json"))) == 1
    assert not list((worker.QUEUE_ROOT / "pending").glob("*.json"))
    events = [json.loads(line) for line in (worker.RUNTIME_ROOT / "v91-actions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [event["phase"] for event in events] == ["TASK_CLAIMED", "TASK_COMPLETED"]
    assert events[-1]["result_summary"]["sha256"] == result["sha256"]


def test_worker_never_overwrites_existing_result(monkeypatch, tmp_path):
    configure_worker(monkeypatch, tmp_path)
    (worker.RUNTIME_ROOT / "results" / "job_04.json").write_text('{"status":"old"}', encoding="utf-8")
    with pytest.raises(ControlError):
        worker.atomic_result("job_04", {"status": "new"})
    assert json.loads((worker.RUNTIME_ROOT / "results" / "job_04.json").read_text(encoding="utf-8"))["status"] == "old"


def test_observer_reports_real_queue_counts_and_audit_errors(monkeypatch, tmp_path):
    queue = tmp_path / "queue"
    runtime = tmp_path / "runtime"
    for name in ("pending", "processing", "done", "failed"):
        (queue / name).mkdir(parents=True)
    (queue / "pending" / "a.json").write_text("{}", encoding="utf-8")
    (queue / "done" / "b.json").write_text("{}", encoding="utf-8")
    runtime.mkdir()
    (runtime / "v91-actions.jsonl").write_text(
        '{"timestamp_utc":"2026-10-14T00:00:00Z","phase":"TASK_COMPLETED","status":"COMPLETED"}\n'
        '{not-json}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(observer, "QUEUE_ROOT", queue)
    monkeypatch.setattr(observer, "RUNTIME_ROOT", runtime)
    result = observer.snapshot()
    assert result["queue_counts"] == {"pending": 1, "processing": 0, "done": 1, "failed": 0}
    assert result["audit"]["events"] == 1
    assert result["audit"]["parse_errors"] == 1
    assert result["status"] == "PENDING_WITNESS"


def test_worker_reports_hash_mismatch_as_mismatch_not_success(monkeypatch, tmp_path):
    configure_worker(monkeypatch, tmp_path)
    (worker.WORKSPACE_ROOT / "evidence.txt").write_text("real content", encoding="utf-8")
    result = worker.execute_task({
        "task_id": "job_05", "action": "verify_sha256",
        "relative_path": "evidence.txt", "expected_sha256": "0" * 64,
    }, "job_05")
    assert result["status"] == "COMPLETED"
    assert result["matches_expected"] is False
    assert result["verification_status"] == "MISMATCH"


def test_worker_rejects_oversized_workspace_file(monkeypatch, tmp_path):
    configure_worker(monkeypatch, tmp_path)
    target = worker.WORKSPACE_ROOT / "large.bin"
    target.write_bytes(b"x")
    monkeypatch.setattr(worker, "MAX_WORKSPACE_FILE_BYTES", 0)
    with pytest.raises(ControlError, match="512 MiB"):
        worker.workspace_file("large.bin")
