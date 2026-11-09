"""Transactional SQLite provider for monotonic replay-state snapshots.

The provider is a local single-host store. Its hash is a deterministic snapshot
fingerprint, not a signature, WORM guarantee, or distributed consensus proof.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class ReplayStateProvider:
    """Append-only replay claims with consistent, deterministic state snapshots."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            self.db_path = base_dir / "ledger" / "replay_guard.db"
        else:
            self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.db_path), timeout=10, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _init_db(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=FULL")
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS replay_state_meta ("
                    "singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                    "database_id TEXT NOT NULL)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS replay_store ("
                    "sequence_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "provider_id TEXT NOT NULL, task_id TEXT NOT NULL, "
                    "nonce TEXT NOT NULL, timestamp_utc TEXT NOT NULL, "
                    "UNIQUE(provider_id, task_id), UNIQUE(provider_id, nonce))"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO replay_state_meta(singleton, database_id) "
                    "VALUES (1, ?)",
                    (str(uuid.uuid4()),),
                )
        except sqlite3.Error as exc:
            raise RuntimeError(f"CRITICAL: Replay-DB initialization failed: {exc}") from exc

    def get_database_id(self) -> str:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT database_id FROM replay_state_meta WHERE singleton=1"
                ).fetchone()
                if row is None or not row["database_id"]:
                    raise RuntimeError("database identity is missing")
                return str(row["database_id"])
        except (sqlite3.Error, RuntimeError) as exc:
            raise RuntimeError(f"CRITICAL: Replay-DB identity unavailable: {exc}") from exc

    def claim(self, provider_id: str, task_id: str, nonce: str) -> bool:
        """Atomically append a replay tombstone; duplicates and errors fail closed."""
        if not all(isinstance(value, str) and value.strip()
                   for value in (provider_id, task_id, nonce)):
            raise ValueError("provider_id, task_id and nonce must be non-empty strings")
        timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT INTO replay_store(provider_id, task_id, nonce, timestamp_utc) "
                    "VALUES (?, ?, ?, ?)",
                    (provider_id, task_id, nonce, timestamp),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
        except sqlite3.Error as exc:
            raise RuntimeError(f"CRITICAL: Replay-DB write failed: {exc}") from exc

    def record_transaction(
        self, task_id: str, nonce: str, sequence_id: int | None = None,
        provider_id: str = "default",
    ) -> int:
        """Compatibility helper; sequence IDs are database-assigned, never caller-set."""
        if sequence_id is not None:
            if isinstance(sequence_id, bool) or not isinstance(sequence_id, int):
                raise ValueError("sequence_id must be an integer when supplied")
            current = self.get_last_logged_sequence()
            if sequence_id != current + 1:
                raise ValueError("sequence_id is informational only and must equal next sequence")
        if not self.claim(provider_id, task_id, nonce):
            raise RuntimeError("CRITICAL: duplicate replay claim rejected")
        return self.get_last_logged_sequence()

    def get_last_logged_sequence(self) -> int:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COALESCE(MAX(sequence_id), 0) AS sequence "
                    "FROM replay_store"
                ).fetchone()
                return int(row["sequence"])
        except sqlite3.Error as exc:
            raise RuntimeError(f"CRITICAL: Replay-DB sequence read failed: {exc}") from exc

    def get_last_logged_timestamp(self) -> datetime:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT timestamp_utc FROM replay_store "
                    "ORDER BY sequence_id DESC LIMIT 1"
                ).fetchone()
                if row is None:
                    return datetime.min.replace(tzinfo=timezone.utc)
                value = datetime.fromisoformat(str(row["timestamp_utc"]).replace("Z", "+00:00"))
                if value.tzinfo is None or value.utcoffset() is None:
                    raise ValueError("stored timestamp has no timezone")
                return value.astimezone(timezone.utc)
        except (sqlite3.Error, ValueError) as exc:
            raise RuntimeError(f"CRITICAL: Replay-DB timestamp read failed: {exc}") from exc

    def compute_current_state_hash(self) -> str:
        """Hash one SQLite read snapshot; WAL permits writers without mixing snapshots."""
        try:
            with self._connect() as conn:
                conn.execute("BEGIN")
                meta = conn.execute(
                    "SELECT database_id FROM replay_state_meta WHERE singleton=1"
                ).fetchone()
                if meta is None:
                    raise RuntimeError("database identity is missing")
                rows = conn.execute(
                    "SELECT sequence_id, provider_id, task_id, nonce, timestamp_utc "
                    "FROM replay_store ORDER BY sequence_id ASC"
                ).fetchall()
                snapshot = {
                    "schema_version": 1,
                    "database_id": str(meta["database_id"]),
                    "records": [
                        {
                            "sequence_id": int(row["sequence_id"]),
                            "provider_id": str(row["provider_id"]),
                            "task_id": str(row["task_id"]),
                            "nonce": str(row["nonce"]),
                            "timestamp_utc": str(row["timestamp_utc"]),
                        }
                        for row in rows
                    ],
                }
                digest = hashlib.sha256(json.dumps(
                    snapshot, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False,
                ).encode("utf-8")).hexdigest()
                conn.rollback()
                return digest
        except (sqlite3.Error, RuntimeError, TypeError, ValueError) as exc:
            raise RuntimeError(f"CRITICAL: Replay-DB state hash failed: {exc}") from exc
