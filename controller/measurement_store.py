#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Durable measurement store for Issue #100: hash-chained, HMAC-signed
JSONL records for both VALID measurements and QUARANTINED raw data.

Honest scope:
- Single-writer via an exclusive lock file; appends are fsynced.
- Corrupt or truncated chains refuse further appends (fail-closed).
- Quarantine preserves the original raw payload; nothing is deleted.
- This module does NOT connect sensors, run a daemon, or prove that any
  real measurement pipeline is live (SCRIPTED != INSTALLED).
- The HMAC secret comes only from V91_MEASUREMENT_STORE_KEY (>= 32
  bytes); there is no default key.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STORE_KEY_ENV = "V91_MEASUREMENT_STORE_KEY"
GENESIS = "0" * 64


class MeasurementStoreError(Exception):
    """Raised on fail-closed conditions: bad key, bad input, corrupt chain."""


def resolve_key() -> bytes:
    """Fail-closed key resolution: env only, >= 32 bytes, no default."""
    value = os.environ.get(STORE_KEY_ENV, "")
    if not isinstance(value, str) or len(value.encode("utf-8")) < 32:
        raise MeasurementStoreError(
            f"{STORE_KEY_ENV} must be set with at least 32 bytes; refusing a default key"
        )
    return value.encode("utf-8")


def canonical_bytes(record: dict[str, Any]) -> bytes:
    payload = {k: v for k, v in record.items() if k != "entry_hmac"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class MeasurementStore:
    """Append-only, HMAC-SHA256-chained store for validated/quarantined measurements."""

    def __init__(self, path: Path, key: bytes | None = None) -> None:
        self._path = Path(path)
        self._key = key if key is not None else resolve_key()
        if not isinstance(self._key, bytes) or len(self._key) < 32:
            raise MeasurementStoreError("store key must be at least 32 bytes")

    def _sign(self, record: dict[str, Any]) -> str:
        return hmac.new(self._key, canonical_bytes(record), hashlib.sha256).hexdigest()

    def _read_entries(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            self._path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line:
                raise MeasurementStoreError(f"blank store line: {line_number}")
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MeasurementStoreError(f"corrupt store line: {exc}") from exc
            if not isinstance(entry, dict):
                raise MeasurementStoreError("store entry must be a JSON object")
            entries.append(entry)
        return entries

    def verify_chain(self) -> bool:
        prev = GENESIS
        for index, entry in enumerate(self._read_entries(), start=1):
            if entry.get("seq") != index or entry.get("prev_hash") != prev:
                return False
            entry_hash = entry.get("entry_hash")
            if not isinstance(entry_hash, str) or len(entry_hash) != 64:
                return False
            if not hmac.compare_digest(entry_hash, self._hash_record(entry)):
                return False
            mac = entry.get("entry_hmac")
            if not isinstance(mac, str) or len(mac) != 64:
                return False
            if not hmac.compare_digest(mac, self._sign(entry)):
                return False
            prev = entry_hash
            if not isinstance(prev, str) or len(prev) != 64:
                return False
        return True

    def _append(self, record: dict[str, Any]) -> dict[str, Any]:
        """Single-writer append: lock before reading, verify, append, then unlock."""
        lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise MeasurementStoreError("another writer holds the store lock") from exc
        try:
            with os.fdopen(lock_fd, "w", encoding="utf-8") as lock:
                lock.write(str(os.getpid()))
                lock.flush()
                os.fsync(lock.fileno())

            # Read and verify only after acquiring the lock. Otherwise two
            # writers can both read the same sequence before either locks,
            # then append duplicate sequence numbers after taking turns.
            entries = self._read_entries()
            if entries and not self.verify_chain():
                raise MeasurementStoreError("existing store chain is invalid; append refused")
            prev = entries[-1]["entry_hash"] if entries else GENESIS
            record["seq"] = len(entries) + 1
            record["prev_hash"] = prev
            record["received_at_utc"] = datetime.now(UTC).isoformat()
            record["entry_hash"] = self._hash_record(record)
            record["entry_hmac"] = self._sign(record)

            with open(self._path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
        return record

    def record_valid(
        self,
        *,
        sensor_id: str,
        metric: str,
        normalized_value: float,
        unit: str,
        timestamp_utc: str,
        source: str = "unknown",
        calibration_ref: str | None = None,
        calibration_status: str = "UNKNOWN",
    ) -> dict[str, Any]:
        """Persist a validated measurement and its calibration evidence state."""
        for name, value in (("sensor_id", sensor_id), ("metric", metric), ("unit", unit), ("timestamp_utc", timestamp_utc)):
            if not isinstance(value, str) or not value.strip():
                raise MeasurementStoreError(f"{name} must be a non-empty string")
        if calibration_ref is not None:
            if not isinstance(calibration_ref, str) or not calibration_ref.strip() or len(calibration_ref) > 2048:
                raise MeasurementStoreError("calibration_ref must be a non-empty opaque reference of at most 2048 characters")
        if not isinstance(calibration_status, str) or calibration_status not in {
            "UNKNOWN", "MISSING_REFERENCE", "REFERENCE_PRESENT_NOT_VERIFIED"
        }:
            raise MeasurementStoreError("calibration_status is not a supported evidence state")
        if calibration_ref is None and calibration_status == "REFERENCE_PRESENT_NOT_VERIFIED":
            raise MeasurementStoreError("calibration status claims a reference that is absent")
        if calibration_ref is not None and calibration_status == "MISSING_REFERENCE":
            raise MeasurementStoreError("calibration status claims a missing reference that is present")
        if isinstance(normalized_value, bool) or not isinstance(normalized_value, (int, float)):
            raise MeasurementStoreError("normalized_value must be numeric")
        try:
            finite_value = math.isfinite(normalized_value)
        except OverflowError:
            finite_value = False
        if not finite_value:
            raise MeasurementStoreError("normalized_value must be finite")
        record: dict[str, Any] = {
            "record_type": "MEASUREMENT_VALID",
            "sensor_id": sensor_id,
            "metric": metric,
            "normalized_value": normalized_value,
            "unit": unit,
            "source_time_utc": timestamp_utc,
            "source": source,
            "calibration_ref": calibration_ref,
            "calibration_status": calibration_status,
        }
        return self._append(record)

    def quarantine(self, raw: dict[str, Any], *, reason: str, claimed_source_time: str | None = None) -> dict[str, Any]:
        """Persist the untouched raw payload plus the failure reason."""
        if not isinstance(raw, dict):
            raise MeasurementStoreError("raw payload must be a dict; refusing to store non-objects")
        if not isinstance(reason, str) or not reason.strip():
            raise MeasurementStoreError("reason must be a non-empty string")
        record: dict[str, Any] = {
            "record_type": "MEASUREMENT_QUARANTINE",
            "reason": reason,
            "claimed_source_time": claimed_source_time,
            "raw_payload": raw,
            "raw_payload_sha256": hashlib.sha256(
                json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
            "disposition": "OPEN",
        }
        return self._append(record)

    @staticmethod
    def _hash_record(record: dict[str, Any]) -> str:
        payload = {
            key: value for key, value in record.items()
            if key not in {"entry_hash", "entry_hmac"}
        }
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def verify_record(self, record: dict[str, Any]) -> bool:
        entry_hash = record.get("entry_hash")
        mac = record.get("entry_hmac")
        if not isinstance(entry_hash, str) or len(entry_hash) != 64:
            return False
        if not hmac.compare_digest(entry_hash, self._hash_record(record)):
            return False
        return isinstance(mac, str) and hmac.compare_digest(mac, self._sign(record))

    def count(self) -> int:
        return len(self._read_entries())
