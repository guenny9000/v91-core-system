"""Reality-first append-only JSONL ledger with SHA-256 tamper detection.

Scope: single-writer local file. This is not WORM storage and does not protect
against an attacker who can rewrite the whole file and recompute every hash.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

LEDGER_FILE = Path("ledger.jsonl")
GENESIS_HASH = "0" * 64
_REQUIRED_FIELDS = {"seq", "timestamp", "event", "prev_hash", "hash"}


def canonical_json(data: dict[str, Any]) -> str:
    """Stable JSON encoding; reject NaN/Infinity and unsupported objects."""
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )


def compute_hash(entry: dict[str, Any]) -> str:
    payload = {
        "seq": entry["seq"],
        "timestamp": entry["timestamp"],
        "event": entry["event"],
        "prev_hash": entry["prev_hash"],
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def verify_ledger_chain() -> dict[str, Any]:
    """Verify every record; raise ValueError on any malformed or altered data."""
    if not LEDGER_FILE.exists():
        return {"valid": True, "entries": 0, "last_hash": GENESIS_HASH}

    expected_seq = 1
    prev_hash = GENESIS_HASH

    with LEDGER_FILE.open("r", encoding="utf-8", newline="") as stream:
        for line_num, line in enumerate(stream, 1):
            if not line.endswith("\n"):
                raise ValueError(f"Unvollständiger Eintrag in Zeile {line_num}")
            raw = line[:-1]
            if not raw:
                raise ValueError(f"Leere Zeile {line_num}")

            try:
                entry = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Ungültiges JSON in Zeile {line_num}") from exc

            if not isinstance(entry, dict) or set(entry) != _REQUIRED_FIELDS:
                raise ValueError(f"Ungültige Struktur in Zeile {line_num}")
            if type(entry["seq"]) is not int or entry["seq"] != expected_seq:
                raise ValueError(f"Ungültige Sequenznummer in Zeile {line_num}")
            if not _valid_timestamp(entry["timestamp"]):
                raise ValueError(f"Ungültiger Zeitstempel in Zeile {line_num}")
            if not isinstance(entry["event"], dict):
                raise ValueError(f"Ungültiges Ereignis in Zeile {line_num}")
            if entry["prev_hash"] != prev_hash:
                raise ValueError(f"Vorheriger Hash falsch in Zeile {line_num}")
            if not isinstance(entry["hash"], str) or len(entry["hash"]) != 64:
                raise ValueError(f"Ungültiges Hashformat in Zeile {line_num}")
            try:
                expected_hash = compute_hash(entry)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Nicht hashbare Daten in Zeile {line_num}") from exc
            if entry["hash"] != expected_hash:
                raise ValueError(f"Hashfehler in Zeile {line_num}")

            prev_hash = entry["hash"]
            expected_seq += 1

    return {"valid": True, "entries": expected_seq - 1, "last_hash": prev_hash}


def append_ledger_entry(event_data: dict[str, Any]) -> dict[str, Any]:
    """Append one entry after verifying the full existing chain.

    Single-writer only: concurrent processes must be externally serialized.
    """
    if not isinstance(event_data, dict):
        raise TypeError("event_data muss ein Dictionary sein")
    # Validate JSON compatibility before touching the ledger.
    try:
        canonical_json(event_data)
    except (TypeError, ValueError) as exc:
        raise ValueError("event_data ist nicht gültiges, endliches JSON") from exc

    state = verify_ledger_chain()
    entry = {
        "seq": state["entries"] + 1,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event_data,
        "prev_hash": state["last_hash"],
    }
    entry["hash"] = compute_hash(entry)
    serialized = canonical_json(entry) + "\n"

    # Append, flush and request OS-level sync; this is not a WORM guarantee.
    with LEDGER_FILE.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)
        stream.flush()
        os.fsync(stream.fileno())

    return entry


if __name__ == "__main__":
    print(json.dumps(verify_ledger_chain(), sort_keys=True))
