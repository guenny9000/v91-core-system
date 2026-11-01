#!/usr/bin/env python3
"""Tests – hash-chain ledger and stewardship gate."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from enforcement import StewardshipGate  # noqa: E402
from ledger import HashChainLedger, verify_chain  # noqa: E402

TS = "2026-11-01T00:00:00Z"
SAFE = {"resource_util": 0.9, "entropy": 0.9, "environment": 0.9, "human_impact": 0.1}


def test_chain_valid_and_resumes_after_restart(tmp_path):
    path = str(tmp_path / "l.jsonl")
    first = HashChainLedger(path)
    first.append({"a": 1}, TS)
    head = first.append({"a": 2}, TS)["hash"]
    reopened = HashChainLedger(path)
    assert reopened.head == head
    rec = reopened.append({"a": 3}, TS)
    assert rec["seq"] == 2 and rec["prev_hash"] == head
    assert verify_chain(path) == {"records_checked": 3, "chain_valid": True, "errors": []}


def test_tampered_payload_detected_and_open_refused(tmp_path):
    path = tmp_path / "l.jsonl"
    ledger = HashChainLedger(str(path))
    ledger.append({"v": 1}, TS)
    ledger.append({"v": 2}, TS)
    lines = path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["v"] = 999
    lines[0] = json.dumps(rec, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = verify_chain(str(path))
    assert not report["chain_valid"] and any("HASH_MISMATCH" in e for e in report["errors"])
    with pytest.raises(ValueError):
        HashChainLedger(str(path))


def test_deleted_record_detected(tmp_path):
    path = tmp_path / "l.jsonl"
    ledger = HashChainLedger(str(path))
    for i in range(3):
        ledger.append({"i": i}, TS)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[0] + "\n" + lines[2] + "\n", encoding="utf-8")
    assert not verify_chain(str(path))["chain_valid"]


def test_malformed_line_reported_not_raised(tmp_path):
    path = tmp_path / "l.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    assert verify_chain(str(path))["errors"] == ["line 1: MALFORMED"]


def test_gate_human_impact_veto_overrides_score(tmp_path):
    gate = StewardshipGate(str(tmp_path / "g.jsonl"))
    result = gate.evaluate("sys-x", {**SAFE, "human_impact": 0.5})
    assert result["decision"] == "REJECTED_HUMAN_IMPACT"


def test_gate_hysteresis_and_never_executes(tmp_path):
    path = str(tmp_path / "g.jsonl")
    gate = StewardshipGate(path)
    assert gate.evaluate("s", SAFE)["decision"] == "APPROVED_ADVISORY"
    mid = {"resource_util": 0.6, "entropy": 0.6, "environment": 0.6, "human_impact": 0.1}
    assert gate.evaluate("s", mid)["decision"] == "APPROVED_ADVISORY"  # stays above LOW
    low = {"resource_util": 0.2, "entropy": 0.2, "environment": 0.2, "human_impact": 0.1}
    assert gate.evaluate("s", low)["decision"] == "IDLE"
    with open(path, encoding="utf-8") as fh:
        assert all(json.loads(line)["payload"]["executed"] is False for line in fh)
    assert verify_chain(path)["chain_valid"]


@pytest.mark.parametrize("bad", [-0.1, 1.5, float("nan"), True, "0.5", None])
def test_gate_rejects_invalid_input(tmp_path, bad):
    gate = StewardshipGate(str(tmp_path / "g.jsonl"))
    with pytest.raises(ValueError):
        gate.evaluate("s", {**SAFE, "entropy": bad})


def test_gate_missing_key(tmp_path):
    gate = StewardshipGate(str(tmp_path / "g.jsonl"))
    with pytest.raises(ValueError):
        gate.evaluate("s", {"resource_util": 0.5})
