"""V99 Phase-2-Regressionstests (Reality-First, nur stdlib)."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v99.core.agent import ModuleReport, Status, V99Agent
from v99.core.lifecycle import LifecycleState, LifecycleStateMachine
from v99.core.module_standard import load_module_spec
from v99.core.registry import ModuleRegistry
from v99.core.scheduler import CycleScheduler, MAX_HISTORY
from v99.agent_shim import build_registry_from_config, run_once


def spec_dict(module_id="m1"):
    return {
        "module_id": module_id, "name": "Modul " + module_id, "version": "0.1.0",
        "api_version": "1", "enabled": True, "platforms": ["windows", "linux"],
        "capabilities": ["health_check"], "permissions": ["read_module_status"],
        "healthcheck": {"enabled": True, "interval_seconds": 300},
        "update_policy": {"automatic_check": True, "automatic_install": False,
                           "rollback_required": True},
    }


class HealthyAdapter:
    def __init__(self, module_id):
        self.module_id = module_id

    def inspect(self):
        return ModuleReport(self.module_id, "0.1.0", Status.HEALTHY)

    def propose_repair(self):
        return None

    def execute(self, proposal):
        return True


class TestScheduler(unittest.TestCase):
    def _scheduler(self, start=datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)):
        times = {"now": start}
        reg = ModuleRegistry()
        reg.register(load_module_spec(spec_dict("m1")), HealthyAdapter("m1"))
        agent = V99Agent(reg)
        sched = CycleScheduler(agent, interval_seconds=900,
                               clock=lambda: times["now"])
        return sched, times

    def test_first_cycle_due_and_healthy(self):
        sched, _ = self._scheduler()
        self.assertTrue(sched.due())
        result = sched.run_cycle()
        self.assertEqual(result.aggregate, "HEALTHY")
        self.assertEqual(result.module_statuses, {"m1": "HEALTHY"})

    def test_not_due_before_interval(self):
        sched, times = self._scheduler()
        sched.run_cycle()
        times["now"] += timedelta(seconds=899)
        self.assertFalse(sched.due())

    def test_due_after_interval(self):
        sched, times = self._scheduler()
        sched.run_cycle()
        times["now"] += timedelta(seconds=901)
        self.assertTrue(sched.due())
        self.assertEqual(sched.missed_intervals(), 1)

    def test_naive_clock_rejected_fail_closed(self):
        sched, times = self._scheduler()
        times["now"] = datetime(2026, 11, 6, 9, 0)  # naive, keine Zeitzone
        with self.assertRaises(ValueError):
            sched.run_cycle()

    def test_history_bounded(self):
        sched, _ = self._scheduler()
        for _ in range(MAX_HISTORY + 25):
            sched.run_cycle()
        self.assertEqual(len(sched.history), MAX_HISTORY)

    def test_empty_registry_aggregates_unknown(self):
        agent = V99Agent(ModuleRegistry())
        sched = CycleScheduler(agent, clock=lambda: datetime.now(timezone.utc))
        result = sched.run_cycle()
        self.assertEqual(result.aggregate, "UNKNOWN")

    def test_invalid_interval_rejected(self):
        with self.assertRaises(ValueError):
            CycleScheduler(V99Agent(ModuleRegistry()), interval_seconds=0)


class TestLifecycle(unittest.TestCase):
    def test_valid_transitions(self):
        machine = LifecycleStateMachine()
        self.assertEqual(machine.state, LifecycleState.INITIALIZING)
        machine.transition(LifecycleState.RUNNING)
        machine.transition(LifecycleState.PAUSED)
        machine.transition(LifecycleState.RUNNING)

    def test_invalid_transition_rejected(self):
        machine = LifecycleStateMachine()
        with self.assertRaises(ValueError):
            machine.transition(LifecycleState.PAUSED)

    def test_halted_is_absorbing_except_reset(self):
        machine = LifecycleStateMachine()
        machine.transition(LifecycleState.HALTED)
        with self.assertRaises(ValueError):
            machine.transition(LifecycleState.RUNNING)
        machine.reset()
        self.assertEqual(machine.state, LifecycleState.INITIALIZING)

    def test_type_check(self):
        machine = LifecycleStateMachine()
        with self.assertRaises(TypeError):
            machine.transition("RUNNING")


class TestMainShim(unittest.TestCase):
    def _config_dir(self, files):
        tmp = tempfile.mkdtemp()
        for name, data in files.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as handle:
                json.dump(data, handle)
        return tmp

    def test_empty_config_is_unknown_not_healthy(self):
        tmp = self._config_dir({})
        result = run_once(build_registry_from_config(tmp))
        self.assertEqual(result["aggregate"], "UNKNOWN")

    def test_example_file_ignored_and_real_module_registered(self):
        tmp = self._config_dir({
            "module.example.json": spec_dict("beispiel"),
            "node.json": spec_dict("node-a"),
        })
        registry = build_registry_from_config(tmp)
        self.assertEqual(registry.list_module_ids(), ["node-a"])
        result = run_once(registry)
        self.assertEqual(result["aggregate"], "UNKNOWN")  # kein Adapter -> UNKNOWN

    def test_duplicate_module_config_rejected(self):
        tmp = self._config_dir({
            "a.json": spec_dict("dup"),
            "b.json": spec_dict("dup"),
        })
        with self.assertRaises(ValueError):
            build_registry_from_config(tmp)


if __name__ == "__main__":
    unittest.main()
