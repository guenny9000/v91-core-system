#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Governance Gate – fail-closed pre-change audit gate with a signed,
hash-chained decision ledger.

Honest scope (NACHWEIS > BEHAUPTUNG):
- This module evaluates, signs and logs governance decisions. It does
  NOT execute anything (DETECTION != AUTHORIZATION) and does NOT prove
  that any real system runs in production (SCRIPTED != INSTALLED).
- The ledger is an append-only JSONL file with an HMAC-SHA256 chain.
  Append-only is tamper-EVIDENT, not WORM; real WORM needs additional
  technical or organisational protection layers.
- The HMAC secret is never hard-coded: it comes only from the
  V91_GOVERNANCE_KEY environment variable, minimum 32 bytes,
  fail-closed (no default key, no fallback).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GOVERNANCE_KEY_ENV = "V91_GOVERNANCE_KEY"
CHECK_KEYS = ("goal_defined", "metric_defined", "risks_assessed", "rollback_possible")


class GovernanceGateError(Exception):
    """Raised on fail-closed conditions: bad key, bad input, corrupt ledger."""


def resolve_key() -> bytes:
    """Fail-closed key resolution: env only, >= 32 bytes, no default."""
    value = os.environ.get(GOVERNANCE_KEY_ENV, "")
    if not isinstance(value, str) or len(value.encode("utf-8")) < 32:
        raise GovernanceGateError(
            f"{GOVERNANCE_KEY_ENV} must be set with at least 32 bytes; refusing to run with a default key"
        )
    return value.encode("utf-8")


def evaluate_checks(metrics: dict[str, Any]) -> dict[str, Any]:
    """Evaluate the four audit questions fail-closed.

    Missing keys are NOT treated as True (no generous defaults): every
    check must be an explicit boolean True. Non-boolean values are
    rejected. The result is a dict, never a silent pass.
    """
    if not isinstance(metrics, dict):
        raise GovernanceGateError("metrics must be a dict")
    missing: list[str] = []
    rejected: list[str] = []
    failed: list[str] = []
    for key in CHECK_KEYS:
        if key not in metrics:
            missing.append(key)
            continue
        value = metrics[key]
        if not isinstance(value, bool):
            rejected.append(key)
        elif value is False:
            failed.append(key)
    if missing or rejected or failed:
        return {
            "decision": "BLOCKED",
            "reasons": [f"missing check: {k}" for k in missing]
            + [f"non-boolean check: {k}" for k in rejected]
            + [f"check failed: {k}" for k in failed],
        }
    return {"decision": "APPROVED", "reasons": []}


class GovernanceLedger:
    """HMAC-SHA256 hash-chained JSONL ledger for governance decisions."""

    def __init__(self, path: Path, key: bytes | None = None) -> None:
        self._path = Path(path)
        self._key = key if key is not None else resolve_key()
        if not isinstance(self._key, bytes) or len(self._key) < 32:
            raise GovernanceGateError("governance key must be at least 32 bytes")

    def _canonical(self, record: dict[str, Any]) -> bytes:
        payload = {k: v for k, v in record.items() if k != "entry_hmac"}
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _sign(self, record: dict[str, Any]) -> str:
        return hmac.new(self._key, self._canonical(record), hashlib.sha256).hexdigest()

    def _read_entries(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GovernanceGateError(f"corrupt governance ledger line: {exc}") from exc
            if not isinstance(entry, dict):
                raise GovernanceGateError("governance ledger entry must be a JSON object")
            entries.append(entry)
        return entries

    def verify_chain(self) -> bool:
        prev = "0" * 64
        for index, entry in enumerate(self._read_entries(), start=1):
            if entry.get("seq") != index or entry.get("prev_hash") != prev:
                return False
            mac = entry.get("entry_hmac")
            if not isinstance(mac, str) or len(mac) != 64:
                return False
            if not hmac.compare_digest(mac, self._sign(entry)):
                return False
            prev = entry.get("entry_hash", "")
            if not isinstance(prev, str) or len(prev) != 64:
                return False
        return True

    def append_decision(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """Verify the chain, evaluate fail-closed, append a signed decision."""
        entries = self._read_entries()
        if entries and not self.verify_chain():
            raise GovernanceGateError("existing governance ledger chain is invalid; append refused")
        evaluation = evaluate_checks(metrics)
        prev = entries[-1]["entry_hash"] if entries else "0" * 64
        record: dict[str, Any] = {
            "seq": len(entries) + 1,
            "prev_hash": prev,
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "decision": evaluation["decision"],
            "checks": {k: metrics.get(k) for k in CHECK_KEYS if k in metrics},
            "reasons": evaluation["reasons"],
        }
        record["entry_hash"] = hashlib.sha256(
            json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        record["entry_hmac"] = self._sign(record)
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        return record

    def verify_decision(self, record: dict[str, Any]) -> bool:
        mac = record.get("entry_hmac")
        return isinstance(mac, str) and hmac.compare_digest(mac, self._sign(record))
