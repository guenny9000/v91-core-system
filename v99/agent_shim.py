"""Verkettung Registry -> Agent -> Scheduler fuer main.py (Phase 2).

Module ohne konkreten Adapter melden UNKNOWN – ein Modul, das nur
beschrieben ist, ist noch kein geprueftes Modul (UNKNOWN_IS_NOT_SUCCESS).
"""
import glob
import json
import os

from controller.emergency_stop import EmergencyStopFlagReader
from v99.core.agent import V99Agent
from v99.core.module_standard import load_module_spec
from v99.core.registry import ModuleRegistry
from v99.core.scheduler import CycleScheduler


def build_registry_from_config(config_dir: str) -> ModuleRegistry:
    registry = ModuleRegistry()
    paths = sorted(glob.glob(os.path.join(config_dir, "*.json")))
    paths = [p for p in paths if not p.endswith(".example.json")]
    if not paths:
        return registry  # leere Registry ist zulaessig und fuehrt zu UNKNOWN
    for path in paths:
        with open(path, "r", encoding="utf-8") as handle:
            registry.register(load_module_spec(json.load(handle)))
    return registry


def run_once(registry: ModuleRegistry, max_cycles: int = 1,
             interval_seconds: int = 900,
             stop_flag_path: str = "ledger/v91_stop.flag") -> dict:
    """Run bounded cycles; every call path checks the local emergency stop."""
    if not isinstance(max_cycles, int) or max_cycles < 1:
        raise ValueError("max_cycles muss >= 1 sein")
    agent = V99Agent(registry)
    stop_reader = EmergencyStopFlagReader(stop_flag_path)
    scheduler = CycleScheduler(
        agent,
        interval_seconds=interval_seconds,
        stop_check=stop_reader.is_stopped,
    )
    last = None
    for _ in range(max_cycles):
        last = scheduler.run_cycle()
    if last is None:
        raise RuntimeError("Kein Zyklus ausgefuehrt")
    return {
        "aggregate": last.aggregate,
        "modules": last.module_statuses,
        "proposals": last.proposals,
        "executed": [list(item) for item in last.executed],
        "started_at": last.started_at,
        "finished_at": last.finished_at,
    }
