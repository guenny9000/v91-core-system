"""Append-only, tamper-evident resource-flow ledger backed by SQLite.

This is NOT physical or administrative WORM: a host administrator can alter the
database or remove triggers. Independent signed checkpoints and separately
administered immutable retention are required for stronger rollback resistance.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENESIS_PREVIOUS_HASH = "0" * 64
GENESIS_PURPOSE = "SYSTEM"
ALLOWED_PURPOSES = frozenset({
    "HUMANITARIAN",
    "CRITICAL_SUPPLY_PROTECTION",
    "CIVILIAN_INFRASTRUCTURE",
    "ECOLOGICAL_RESTORATION",
    "GENERAL_CIVILIAN",
})
RESTRICTED_PURPOSES = frozenset({
    "WEAPONS_DEVELOPMENT",
    "TARGETING",
    "COMBAT_OPERATIONS",
    "ARMS_PRODUCTION",
})


class LedgerIntegrityError(RuntimeError):
    """Ledger is missing, malformed, or cryptographically inconsistent."""


class V91WormLedger:
    """SQLite hash-chain ledger; tamper-evident, not independently immutable."""

    def __init__(self, ledger_file_path: str | Path):
        self.ledger_path = Path(ledger_file_path).expanduser()
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @staticmethod
    def _canonical(block: dict[str, Any]) -> bytes:
        try:
            return json.dumps(
                {key: value for key, value in block.items() if key != "current_hash"},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError) as exc:
            raise LedgerIntegrityError("block cannot be canonically encoded") from exc

    @classmethod
    def _hash(cls, block: dict[str, Any]) -> str:
        return hashlib.sha256(cls._canonical(block)).hexdigest()

    @classmethod
    def _verify_rows(cls, rows: list[tuple[Any, ...]]) -> bool:
        """Verify a complete ordered snapshot before it is trusted or extended."""
        if not rows:
            return False
        expected_previous = GENESIS_PREVIOUS_HASH
        for expected_index, row in enumerate(rows):
            try:
                index, timestamp, flow, value, purpose, previous_hash, current_hash = row
                block = {
                    "block_index": index,
                    "timestamp_utc": timestamp,
                    "resource_flow": flow,
                    "value": value,
                    "purpose": purpose,
                    "previous_hash": previous_hash,
                }
                if index != expected_index or previous_hash != expected_previous:
                    return False
                if not isinstance(current_hash, str) or current_hash != cls._hash(block):
                    return False
                if index == 0 and (
                    timestamp != "1970-01-01T00:00:00Z"
                    or flow != "GENESIS" or value != 0.0
                    or purpose != GENESIS_PURPOSE
                    or previous_hash != GENESIS_PREVIOUS_HASH
                ):
                    return False
                expected_previous = current_hash
            except (TypeError, ValueError, LedgerIntegrityError):
                return False
        return True

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.ledger_path), timeout=10, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            db.execute("""
                CREATE TABLE IF NOT EXISTS resource_blocks (
                    block_index INTEGER PRIMARY KEY,
                    timestamp_utc TEXT NOT NULL,
                    resource_flow TEXT NOT NULL,
                    value REAL NOT NULL,
                    purpose TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    current_hash TEXT NOT NULL UNIQUE
                )
            """)
            db.execute("""
                CREATE TRIGGER IF NOT EXISTS resource_blocks_no_update
                BEFORE UPDATE ON resource_blocks
                BEGIN SELECT RAISE(ABORT, 'append-only ledger'); END
            """)
            db.execute("""
                CREATE TRIGGER IF NOT EXISTS resource_blocks_no_delete
                BEFORE DELETE ON resource_blocks
                BEGIN SELECT RAISE(ABORT, 'append-only ledger'); END
            """)
            row = db.execute(
                "SELECT block_index, timestamp_utc, resource_flow, value, purpose, "
                "previous_hash, current_hash FROM resource_blocks ORDER BY block_index LIMIT 1"
            ).fetchone()
            if row is None:
                genesis = {
                    "block_index": 0,
                    "timestamp_utc": "1970-01-01T00:00:00Z",
                    "resource_flow": "GENESIS",
                    "value": 0.0,
                    "purpose": GENESIS_PURPOSE,
                    "previous_hash": GENESIS_PREVIOUS_HASH,
                }
                db.execute(
                    "INSERT INTO resource_blocks VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (0, genesis["timestamp_utc"], genesis["resource_flow"], 0.0,
                     GENESIS_PURPOSE, GENESIS_PREVIOUS_HASH, self._hash(genesis)),
                )
            db.commit()

    def append_resource_flow(
        self, resource_type: str, value: float, purpose_classification: str
    ) -> str:
        if not isinstance(resource_type, str) or not resource_type.strip():
            raise ValueError("resource_type must be a non-empty string")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("resource value must be numeric")
        numeric_value = float(value)
        if not math.isfinite(numeric_value) or numeric_value < 0:
            raise ValueError("resource value must be finite and non-negative")
        if not isinstance(purpose_classification, str):
            raise ValueError("purpose classification is required")
        purpose = purpose_classification.strip().upper()
        if purpose in RESTRICTED_PURPOSES:
            raise PermissionError("resource flow rejected by configured non-military policy")
        if purpose not in ALLOWED_PURPOSES:
            raise ValueError("unknown purpose classification; manual policy review required")

        with closing(self._connect()) as db:
            # Hold the write lock while verifying and appending so no other
            # writer can change the chain between the integrity check and insert.
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT block_index, timestamp_utc, resource_flow, value, purpose, "
                "previous_hash, current_hash FROM resource_blocks ORDER BY block_index"
            ).fetchall()
            if not self._verify_rows(rows):
                db.rollback()
                raise LedgerIntegrityError("existing ledger chain is invalid; append refused")
            index, previous_hash = rows[-1][0], rows[-1][6]
            block = {
                "block_index": index + 1,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(
                    timespec="microseconds"
                ).replace("+00:00", "Z"),
                "resource_flow": resource_type.strip(),
                "value": numeric_value,
                "purpose": purpose,
                "previous_hash": previous_hash,
            }
            digest = self._hash(block)
            db.execute(
                "INSERT INTO resource_blocks VALUES (?, ?, ?, ?, ?, ?, ?)",
                (block["block_index"], block["timestamp_utc"], block["resource_flow"],
                 block["value"], block["purpose"], block["previous_hash"], digest),
            )
            db.commit()
            return digest

    def verify_ledger_chain(self) -> bool:
        try:
            with closing(self._connect()) as db:
                db.execute("BEGIN")
                rows = db.execute(
                    "SELECT block_index, timestamp_utc, resource_flow, value, purpose, "
                    "previous_hash, current_hash FROM resource_blocks ORDER BY block_index"
                ).fetchall()
                db.rollback()
            return self._verify_rows(rows)
        except sqlite3.Error:
            return False
