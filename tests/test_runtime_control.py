import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "controller"))
import runtime_control as rc


def test_parse_compose_json_array_and_json_lines():
    assert rc.parse_json_lines('[{"Service":"worker"},{"Service":"api"}]') == [
        {"Service": "worker"}, {"Service": "api"}
    ]
    assert rc.parse_json_lines('{"Service":"worker"}\n{"Service":"api"}') == [
        {"Service": "worker"}, {"Service": "api"}
    ]


@pytest.mark.parametrize("value", ["", "80", "nan%", "-1%", "inf%", None])
def test_invalid_docker_percent_is_rejected(value):
    with pytest.raises(rc.ControlError):
        rc.parse_percent(value)


def test_scale_up_decision_uses_live_resource_observation():
    snapshot = {
        "replicas": 1, "max_cpu_percent": 88.0, "max_memory_percent": 42.0
    }
    action, low_count, reason = rc.decide(snapshot, 0)
    assert action == "scale_up_workers"
    assert low_count == 0
    assert "Live Docker metrics" in reason


def test_scale_down_requires_three_consecutive_low_samples():
    snapshot = {"replicas": 3, "max_cpu_percent": 10.0, "max_memory_percent": 25.0}
    assert rc.decide(snapshot, 0)[0] is None
    assert rc.decide(snapshot, 1)[0] is None
    action, count, reason = rc.decide(snapshot, 2)
    assert action == "scale_down_workers"
    assert count == 3
    assert "persisted" in reason


def test_replica_limits_are_hard_coded():
    with pytest.raises(rc.ControlError):
        rc.scale_worker(Path("/tmp/compose.yml"), "test-project", 0)
    with pytest.raises(rc.ControlError):
        rc.scale_worker(Path("/tmp/compose.yml"), "test-project", 4)


def test_scale_command_is_allowlisted_and_does_not_use_shell(monkeypatch, tmp_path):
    compose = tmp_path / "compose.yml"
    compose.write_text("services:\n  worker:\n    image: example\n", encoding="utf-8")
    seen = {}

    def fake_run(args, timeout=25):
        seen["args"] = args
        seen["timeout"] = timeout
        return ""

    monkeypatch.setattr(rc, "run_command", fake_run)
    rc.scale_worker(compose.resolve(), "v91-test", 2)
    args = seen["args"]
    assert args[:2] == ["docker", "compose"]
    assert "--scale" in args
    assert "worker=2" in args
    assert args[-1] == "worker"
    assert "shell" not in args
    assert seen["timeout"] == 120


def test_audit_append_is_jsonl_and_refuses_existing_lock(tmp_path):
    audit = tmp_path / "runtime" / "actions.jsonl"
    rc.append_audit(audit, {"phase": "DECISION", "status": "NO_ACTION"})
    event = json.loads(audit.read_text(encoding="utf-8").splitlines()[0])
    assert event["phase"] == "DECISION"
    lock = audit.with_name(audit.name + ".lock")
    lock.write_text("stale lock", encoding="utf-8")
    with pytest.raises(rc.ControlError):
        rc.append_audit(audit, {"phase": "VERIFY"})
    assert len(audit.read_text(encoding="utf-8").splitlines()) == 1


def test_run_cycle_only_proposes_when_actions_are_not_enabled(monkeypatch, tmp_path):
    snapshot = {
        "timestamp_utc": "2026-10-14T00:00:00.000Z",
        "source": "DOCKER_LIVE", "project": "v91-test", "service": "worker",
        "replicas": 1, "running": 1, "max_cpu_percent": 90.0,
        "max_memory_percent": 40.0, "containers": [],
    }
    monkeypatch.setattr(rc, "collect_snapshot", lambda *_: snapshot)
    result = rc.run_cycle(tmp_path / "compose.yml", "v91-test", tmp_path / "runtime", False)
    assert result["status"] == "PROPOSED_NOT_EXECUTED"
    assert result["action"] == "scale_up_workers"
    event = json.loads((tmp_path / "runtime" / "v91-actions.jsonl").read_text(encoding="utf-8"))
    assert event["phase"] == "DECISION"
    assert event["before_replicas"] == 1
    assert event["target_replicas"] == 2
    assert event["expected_effect"]
    assert event["rollback_plan"]


def test_scale_down_is_not_executed_without_separate_opt_in(monkeypatch, tmp_path):
    snapshot = {
        "timestamp_utc": "2026-10-14T00:00:00.000Z",
        "source": "DOCKER_LIVE", "project": "v91-test", "service": "worker",
        "replicas": 2, "running": 2, "max_cpu_percent": 5.0,
        "max_memory_percent": 10.0, "containers": [],
    }
    monkeypatch.setattr(rc, "collect_snapshot", lambda *_: snapshot)
    state_path = tmp_path / "runtime" / "v91-controller-state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"low_resource_samples": 2}', encoding="utf-8")
    def forbidden_scale(*_args, **_kwargs):
        raise AssertionError("scale-down must not run without explicit opt-in")
    monkeypatch.setattr(rc, "scale_worker", forbidden_scale)
    result = rc.run_cycle(tmp_path / "compose.yml", "v91-test", tmp_path / "runtime", True)
    assert result["action"] == "scale_down_workers"
    assert result["status"] == "PROPOSED_SCALE_DOWN_REQUIRES_OPT_IN"


def test_collect_snapshot_reads_live_compose_and_docker_stats(monkeypatch, tmp_path):
    compose = tmp_path / "compose.yml"
    compose.write_text("services:\n  worker:\n    image: example\n", encoding="utf-8")
    calls = []
    def fake_command(args, timeout=25):
        calls.append(args)
        if args[-2:] == ["config", "--services"]:
            return "worker\ncontroller\n"
        if args[-4:] == ["ps", "--all", "--format", "json"]:
            return '[{"Name":"v91-worker-1","Service":"worker","State":"running","Health":"healthy"}]'
        if args[:2] == ["docker", "stats"]:
            return '{"Name":"v91-worker-1","CPUPerc":"81.00%","MemPerc":"43.00%"}\n'
        raise AssertionError(f"unexpected command: {args}")
    monkeypatch.setattr(rc, "run_command", fake_command)
    snapshot = rc.collect_snapshot(compose.resolve(), "v91-test")
    assert snapshot["source"] == "DOCKER_LIVE"
    assert snapshot["replicas"] == 1
    assert snapshot["running"] == 1
    assert snapshot["max_cpu_percent"] == 81.0
    assert snapshot["max_memory_percent"] == 43.0
    assert len(calls) == 3


def test_authorized_scale_up_is_audited_before_action_and_verified(monkeypatch, tmp_path):
    before = {
        "timestamp_utc": "2026-10-14T00:00:00.000Z", "source": "DOCKER_LIVE",
        "project": "v91-test", "service": "worker", "replicas": 1, "running": 1,
        "max_cpu_percent": 90.0, "max_memory_percent": 40.0, "containers": [],
    }
    after = {**before, "replicas": 2, "running": 2, "max_cpu_percent": 45.0}
    monkeypatch.setattr(rc, "collect_snapshot", lambda *_: before)
    observed = {}
    def scale(compose_file, project_name, replicas):
        audit = tmp_path / "runtime" / "v91-actions.jsonl"
        assert audit.exists(), "decision must be persisted before actuator call"
        record = json.loads(audit.read_text(encoding="utf-8").splitlines()[0])
        assert record["phase"] == "DECISION"
        assert record["target_replicas"] == replicas
        observed["replicas"] = replicas
    monkeypatch.setattr(rc, "scale_worker", scale)
    snapshots = iter([after])
    monkeypatch.setattr(rc, "collect_snapshot", lambda *_: next(snapshots))
    # Restore a pre-action snapshot for the initial read, then post-action snapshot.
    snapshots = iter([before, after])
    monkeypatch.setattr(rc, "collect_snapshot", lambda *_: next(snapshots))
    result = rc.run_cycle(tmp_path / "compose.yml", "v91-test", tmp_path / "runtime", True)
    assert observed["replicas"] == 2
    assert result["status"] == "VERIFIED"
    assert result["after"]["replicas"] == 2
    events = [json.loads(line) for line in (tmp_path / "runtime" / "v91-actions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [event["phase"] for event in events] == ["DECISION", "VERIFY"]


def test_failed_post_check_attempts_rollback_and_records_result(monkeypatch, tmp_path):
    before = {
        "timestamp_utc": "2026-10-14T00:00:00.000Z", "source": "DOCKER_LIVE",
        "project": "v91-test", "service": "worker", "replicas": 1, "running": 1,
        "max_cpu_percent": 90.0, "max_memory_percent": 40.0, "containers": [],
    }
    snapshots = iter([before])
    calls = []
    def collect(*_):
        value = next(snapshots)
        if value == "FAIL":
            raise rc.ControlError("post check failed")
        return value
    # First observation succeeds, post-action verification fails, rollback observation succeeds.
    observations = [before, rc.ControlError("post-check failure"), before]
    def collect_sequence(*_):
        item = observations.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    monkeypatch.setattr(rc, "collect_snapshot", collect_sequence)
    monkeypatch.setattr(rc, "scale_worker", lambda _file, _project, count: calls.append(count))
    result = rc.run_cycle(tmp_path / "compose.yml", "v91-test", tmp_path / "runtime", True)
    assert calls == [2, 1]
    assert result["status"] == "ROLLED_BACK"
    events = [json.loads(line) for line in (tmp_path / "runtime" / "v91-actions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [event["phase"] for event in events] == ["DECISION", "ROLLBACK"]
    assert events[-1]["status"] == "ROLLED_BACK"
