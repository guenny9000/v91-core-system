from __future__ import annotations

import json
from pathlib import Path

import pytest

from measurement_core import (
    GENESIS, MeasurementError, append_snapshot, event_hash, metric,
    verify_ledger,
)


def test_missing_metric_is_unknown():
    value = metric(None, "Wh", "physical_meter")
    assert value["value"] is None
    assert value["status"] == "UNKNOWN"


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True, "0"])
def test_invalid_metric_rejected(bad):
    with pytest.raises(MeasurementError):
        metric(bad, "percent", "test")


def test_append_and_verify_chain(tmp_path: Path):
    ledger = tmp_path / "measurements.jsonl"
    snapshot = {"energy_wh": metric(None, "Wh", "meter")}
    first = append_snapshot(ledger, snapshot)
    second = append_snapshot(ledger, snapshot)
    state = verify_ledger(ledger)
    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert state["status"] == "CHAIN_VALID"
    assert state["events"] == 2


def test_tampering_is_detected(tmp_path: Path):
    ledger = tmp_path / "measurements.jsonl"
    append_snapshot(ledger, {"cpu": metric(12.5, "%", "test")})
    record = json.loads(ledger.read_text(encoding="utf-8"))
    record["snapshot"]["cpu"]["value"] = 99.0
    ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(MeasurementError, match="Event hash mismatch"):
        verify_ledger(ledger)


def test_empty_ledger_is_not_a_passed_measurement(tmp_path: Path):
    state = verify_ledger(tmp_path / "not-created.jsonl")
    assert state["status"] == "EMPTY_LEDGER"
    assert state["events"] == 0
    assert state["last_hash"] == GENESIS
