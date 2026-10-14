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
