"""Issue #70 wiring: emergency stop at the real entry points."""
import json

from controller.emergency_stop import EmergencyStopFlagReader
from main import main as cli_main
from v99.agent_shim import run_once
from v99.core.registry import ModuleRegistry
from v99.core.scheduler import CycleScheduler


class FakeAgent:
    def __init__(self):
        self.inspected = False

    def inspect_all(self):
        self.inspected = True
        return []

    def prepare_repairs(self):
        return []

    def execute_safe_repairs(self, proposals):
        return ()


def test_scheduler_skips_all_work_when_stopped():
    agent = FakeAgent()
    scheduler = CycleScheduler(agent, stop_check=lambda: (True, "STOPPED_FLAG_PRESENT"))
    result = scheduler.run_cycle()
    assert agent.inspected is False
    assert result.aggregate == "HALTED"
    assert result.proposals == 0 and result.executed == ()
    assert len(scheduler.history) == 1


def test_scheduler_runs_normally_when_not_stopped():
    agent = FakeAgent()
    scheduler = CycleScheduler(agent, stop_check=lambda: (False, "RUNNING_NO_FLAG"))
    result = scheduler.run_cycle()
    assert agent.inspected is True
    assert result.aggregate == "UNKNOWN"  # leere Reports != gesund


def test_scheduler_without_stop_check_is_unchanged():
    agent = FakeAgent()
    scheduler = CycleScheduler(agent)
    scheduler.run_cycle()
    assert agent.inspected is True


def test_flag_reader_reads_real_flag(tmp_path):
    flag = tmp_path / "stop.flag"
    assert EmergencyStopFlagReader(flag).is_stopped() == (False, "RUNNING_NO_FLAG")
    flag.write_text("incident", encoding="utf-8")
    assert EmergencyStopFlagReader(flag).is_stopped() == (True, "STOPPED_FLAG_PRESENT")


def test_cli_exits_2_when_stop_flag_present(tmp_path, capsys):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    flag = tmp_path / "stop.flag"
    flag.write_text("incident", encoding="utf-8")
    code = cli_main(["--config-dir", str(config_dir), "--stop-flag", str(flag)])
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "EMERGENCY_STOPPED"
    assert payload["reason"] == "STOPPED_FLAG_PRESENT"


def test_cli_runs_when_no_flag(tmp_path, capsys):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    code = cli_main(["--config-dir", str(config_dir),
                     "--stop-flag", str(tmp_path / "absent.flag")])
    assert code in (0, 1)  # leere Config: kein Notaus, normaler Lauf
    payload = json.loads(capsys.readouterr().out)
    assert payload.get("status") != "EMERGENCY_STOPPED"


def test_run_once_wires_stop_flag_into_scheduler(tmp_path):
    flag = tmp_path / "stop.flag"
    flag.write_text("incident", encoding="utf-8")
    result = run_once(ModuleRegistry(), stop_flag_path=str(flag))
    assert result["aggregate"] == "HALTED"
    assert result["proposals"] == 0
    assert result["executed"] == []


def test_run_once_without_flag_keeps_empty_registry_unknown(tmp_path):
    result = run_once(
        ModuleRegistry(),
        stop_flag_path=str(tmp_path / "missing.flag"),
    )
    assert result["aggregate"] == "UNKNOWN"
