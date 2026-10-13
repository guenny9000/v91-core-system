"""One-shot, read-only V91 heartbeat with fail-closed evidence labels.

This is a diagnostic cycle, not a daemon, WORM service, or production activation.
It never executes infrastructure actions. Missing host telemetry is recorded as
NO_DATA_AVAILABLE; application health remains unknown.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import ledger

# The repository also has a top-level controller.py, so load the adapter from
# the controller directory explicitly instead of treating "controller" as a
# package (which would resolve to that module on some Python import paths).
_CONTROLLER_DIR = Path(__file__).resolve().parent / "controller"
if str(_CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(_CONTROLLER_DIR))
from real_metrics import collect_host_metrics  # noqa: E402

MAX_CPU_THRESHOLD_PERCENT = 85.0


def run_heartbeat_cycle() -> dict[str, Any]:
    """Verify the local chain, sample host telemetry, and append one audit event."""
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        chain_state = ledger.verify_ledger_chain()
        if not chain_state.get("valid", False):
            return {
                "status": "FAIL_CLOSED",
                "reason": "ledger_integrity_invalid",
                "timestamp_utc": timestamp,
                "ledger_entry_written": False,
                "application_metrics": "NO_DATA_AVAILABLE",
            }

        metrics = collect_host_metrics()
        if metrics.get("status") != "DOCUMENTED":
            status = "NO_DATA_AVAILABLE"
        elif metrics["cpu_percent"] > MAX_CPU_THRESHOLD_PERCENT:
            status = "WARNING_HIGH_HOST_CPU"
        else:
            status = "HOST_TELEMETRY_DOCUMENTED"

        event = {
            "event_type": "HEARTBEAT_CYCLE",
            "status": status,
            "timestamp_utc": timestamp,
            "host_metrics": metrics,
            "application_metrics": "NO_DATA_AVAILABLE",
            "prior_ledger_entries": chain_state["entries"],
            "infrastructure_actions_executed": False,
        }
        entry = ledger.append_ledger_entry(event)
        return {
            "status": status,
            "seq": entry["seq"],
            "hash": entry["hash"],
            "timestamp_utc": timestamp,
            "ledger_entry_written": True,
            "application_metrics": "NO_DATA_AVAILABLE",
        }
    except Exception:
        # Do not claim the failure was recorded: the ledger itself may be corrupt
        # or unavailable, in which case appending would not be trustworthy.
        return {
            "status": "FAIL_CLOSED",
            "reason": "ledger_or_telemetry_cycle_failed",
            "timestamp_utc": timestamp,
            "ledger_entry_written": False,
            "application_metrics": "NO_DATA_AVAILABLE",
        }


if __name__ == "__main__":
    import json
    print(json.dumps(run_heartbeat_cycle(), sort_keys=True))
