#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Durable measurement quarantine (Issue #100, master handover section 12).

Preserves rejected/quarantined measurements with full context. Never
silently deletes damaged entries: resolutions are appended as new
records referencing the original sequence. Fail-closed on corrupt
chain. Append-only JSONL with SHA-256 hash chain and fsync.

Honest limits: single-writer via lock file (no distributed locking,
no crash-concurrency proof); append-only is tamper-EVIDENT, not WORM;
this module stores data, it does not decide authorizations.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOCK_SUFFIX = ".lock"


class QuarantineError(Exception):
    """Raised on fail-closed conditions: corrupt chain, lock conflict, bad input."""


def _canonical(record: dict[str, Any]) -> bytes:
    payload = {k: v for k, v in record.items() if k != "entry_hash"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash_record(record: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(record)).hexdigest()


class MeasurementQuarantine:
    """Append-only, hash-chained quarantine store. Single writer per path."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock_path = Path(str(self._path) + LOCK_SUFFIX)
        self._lock_fd: int | None = None
        try:
            self._lock_fd = os.open(str(self._lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise QuarantineError(
                "another writer holds the quarantine lock; refusing concurrent writes"
            ) from exc

    def close(self) -> None:
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None
            try:
                self._lock_path.unlink()
            except FileNotFoundError:
                pass

    def __enter__(self) -> "MeasurementQuarantine":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

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
                raise QuarantineError(f"corrupt quarantine line: {exc}") from exc
            if not isinstance(entry, dict):
                raise QuarantineError("quarantine entry must be a JSON object")
            entries.append(entry)
        return entries

    def verify_chain(self) -> bool:
        prev = "0" * 64
        for index, entry in enumerate(self._read_entries(), start=1):
            if entry.get("seq") != index or entry.get("prev_hash") != prev:
                return False
            entry_hash = entry.get("entry_hash")
            if not isinstance(entry_hash, str) or len(entry_hash) != 64:
                return False
            if _hash_record(entry) != entry_hash:
                return False
            prev = entry_hash
        return True

    def _append(self, record: dict[str, Any]) -> dict[str, Any]:
        if self._lock_fd is None:
            raise QuarantineError("quarantine is closed; refusing writes")
        entries = self._read_entries()
        if entries and not self.verify_chain():
            raise QuarantineError("existing quarantine chain is invalid; append refused")
        record["seq"] = len(entries) + 1
        record["prev_hash"] = entries[-1]["entry_hash"] if entries else "0" * 64
        record["received_at_utc"] = datetime.now(UTC).isoformat()
        record["entry_hash"] = _hash_record(record)
        line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        return record

    def quarantine(
        self,
        raw_data: Any,
        *,
        reason: str,
        sender: str = "unknown",
        source_id: str = "unknown",
        claimed_source_time: str | None = None,
        protocol_version: str = "unknown",
        verdict: str = "QUARANTINE",
    ) -> dict[str, Any]:
        """Preserve the original raw data with full context. Never repairs."""
        if not isinstance(reason, str) or not reason.strip():
            raise QuarantineError("reason must be a non-empty string")
        record: dict[str, Any] = {
            "kind": "QUARANTINE_ENTRY",
            "data_hash": hashlib.sha256(
                json.dumps(raw_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
            ).hexdigest(),
            "raw_data": raw_data,
            "sender": sender,
            "source_id": source_id,
            "claimed_source_time": claimed_source_time,
            "protocol_version": protocol_version,
            "reason": reason,
            "verdict": verdict,
            "status": "OPEN",
        }
        return self._append(record)

    def resolve(self, original_seq: int, *, resolution: str, resolved_by: str) -> dict[str, Any]:
        """Record exactly one resolution as a NEW entry; the original is never modified or deleted."""
        if type(original_seq) is not int or original_seq < 1:
            raise QuarantineError("original_seq must be a positive integer")
        for name, value in (("resolution", resolution), ("resolved_by", resolved_by)):
            if not isinstance(value, str) or not value.strip():
                raise QuarantineError(f"{name} must be a non-empty string")
        entries = self._read_entries()
        original = next((e for e in entries if e.get("seq") == original_seq and e.get("kind") == "QUARANTINE_ENTRY"), None)
        if original is None:
            raise QuarantineError(f"no quarantine entry with seq {original_seq}")
        if any(
            e.get("kind") == "RESOLUTION" and e.get("original_seq") == original_seq
            for e in entries
        ):
            raise QuarantineError(f"quarantine entry {original_seq} is already resolved")
        record: dict[str, Any] = {
            "kind": "RESOLUTION",
            "original_seq": original_seq,
            "original_hash": original["entry_hash"],
            "resolution": resolution,
            "resolved_by": resolved_by,
            "status": "RESOLVED",
        }
        return self._append(record)

    def list_open(self) -> list[dict[str, Any]]:
        resolved: set[int] = {
            e["original_seq"] for e in self._read_entries()
            if e.get("kind") == "RESOLUTION" and isinstance(e.get("original_seq"), int)
        }
        return [
            e for e in self._read_entries()
            if e.get("kind") == "QUARANTINE_ENTRY" and e.get("seq") not in resolved
        ]
