"""Transactional migration and fail-closed ingress composition.

The legacy ingress_replay table remains untouched. Migration imports its replay
claims into ReplayStateProvider's database in one destination transaction.
This module does not provide a network witness client or execute accepted tasks.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from controller.task_ingress_gate import canonical_payload_bytes

logger = logging.getLogger("V91.DatabaseUnification")


class ReplayMigrationError(RuntimeError):
    """Migration cannot safely preserve all legacy replay claims."""


class V91ReplayDatabaseUnifier:
    """Import the actual SQLiteReplayStore schema without deleting its source."""

    LEGACY_TABLE = "ingress_replay"

    @staticmethod
    def _source_rows(old_db_path: Path) -> tuple[list[tuple[str, str, str, int]], str]:
        try:
            with closing(sqlite3.connect(str(old_db_path), timeout=10)) as source:
                source.execute("BEGIN")
                exists = source.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (V91ReplayDatabaseUnifier.LEGACY_TABLE,),
                ).fetchone()
                if exists is None:
                    raise ReplayMigrationError(
                        "legacy ingress_replay table is missing; refusing implicit empty migration"
                    )
                columns = {
                    row[1] for row in source.execute(
                        f"PRAGMA table_info({V91ReplayDatabaseUnifier.LEGACY_TABLE})"
                    ).fetchall()
                }
                required = {"provider_id", "task_id", "nonce", "claimed_at"}
                if columns != required:
                    raise ReplayMigrationError(
                        f"legacy schema mismatch: expected {sorted(required)}, got {sorted(columns)}"
                    )
                rows = source.execute(
                    "SELECT provider_id, task_id, nonce, claimed_at "
                    "FROM ingress_replay ORDER BY provider_id, task_id, nonce"
                ).fetchall()
                normalized: list[tuple[str, str, str, int]] = []
                for provider_id, task_id, nonce, claimed_at in rows:
                    if not all(isinstance(v, str) and v for v in (provider_id, task_id, nonce)):
                        raise ReplayMigrationError("legacy row contains an invalid identity field")
                    if isinstance(claimed_at, bool) or not isinstance(claimed_at, int):
                        raise ReplayMigrationError("legacy claimed_at must be an integer Unix timestamp")
                    normalized.append((provider_id, task_id, nonce, claimed_at))
                digest_input = {
                    "schema": sorted(columns),
                    "rows": [list(row) for row in normalized],
                }
                fingerprint = hashlib.sha256(json.dumps(
                    digest_input, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False,
                ).encode("utf-8")).hexdigest()
                source.rollback()
                return normalized, fingerprint
        except sqlite3.Error as exc:
            raise ReplayMigrationError(f"cannot read legacy replay database: {exc}") from exc

    @staticmethod
    def migrate_and_unify(old_db_path: Path, new_db_path: Path) -> bool:
        """Atomically import legacy claims; exact repeats are idempotent.

        Conflicting task-ID/nonce mappings abort the whole transaction. The
        source database is read-only from this operation's perspective and is
        never deleted or modified.
        """
        old_path = Path(old_db_path).expanduser()
        new_path = Path(new_db_path).expanduser()
        if not old_path.exists():
            logger.info("Legacy replay database absent; no migration required.")
            return True
        if old_path.resolve() == new_path.resolve():
            raise ReplayMigrationError("source and destination database paths must differ")
        if not new_path.exists():
            raise ReplayMigrationError(
                "destination database must be initialized by ReplayStateProvider before migration"
            )

        rows, fingerprint = V91ReplayDatabaseUnifier._source_rows(old_path)
        inserted = 0
        exact_existing = 0
        try:
            with closing(sqlite3.connect(str(new_path), timeout=10, isolation_level=None)) as dest:
                dest.execute("PRAGMA busy_timeout=10000")
                dest.execute("PRAGMA synchronous=FULL")
                dest.execute("BEGIN IMMEDIATE")
                tables = {
                    row[0] for row in dest.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                if not {"replay_store", "replay_state_meta"}.issubset(tables):
                    raise ReplayMigrationError(
                        "destination is not initialized with ReplayStateProvider schema"
                    )
                dest.execute(
                    "CREATE TABLE IF NOT EXISTS replay_migrations ("
                    "source_fingerprint TEXT PRIMARY KEY, imported_count INTEGER NOT NULL, "
                    "exact_existing_count INTEGER NOT NULL, completed_at_utc TEXT NOT NULL)"
                )
                prior = dest.execute(
                    "SELECT 1 FROM replay_migrations WHERE source_fingerprint=?",
                    (fingerprint,),
                ).fetchone()
                if prior is not None:
                    dest.commit()
                    return True

                for provider_id, task_id, nonce, claimed_at in rows:
                    timestamp = datetime.fromtimestamp(
                        claimed_at, tz=timezone.utc
                    ).isoformat(timespec="seconds").replace("+00:00", "Z")
                    by_task = dest.execute(
                        "SELECT nonce, timestamp_utc FROM replay_store WHERE provider_id=? AND task_id=?",
                        (provider_id, task_id),
                    ).fetchone()
                    by_nonce = dest.execute(
                        "SELECT task_id, timestamp_utc FROM replay_store WHERE provider_id=? AND nonce=?",
                        (provider_id, nonce),
                    ).fetchone()
                    if by_task is not None or by_nonce is not None:
                        if (by_task is not None and by_nonce is not None
                                and by_task[0] == nonce and by_nonce[0] == task_id
                                and by_task[1] == timestamp and by_nonce[1] == timestamp):
                            exact_existing += 1
                            continue
                        raise ReplayMigrationError(
                            "replay identity conflict: task ID, nonce or original timestamp "
                            "does not match the existing claim"
                        )
                    dest.execute(
                        "INSERT INTO replay_store "
                        "(provider_id, task_id, nonce, timestamp_utc) VALUES (?, ?, ?, ?)",
                        (provider_id, task_id, nonce, timestamp),
                    )
                    inserted += 1

                completed = datetime.now(timezone.utc).isoformat(
                    timespec="microseconds"
                ).replace("+00:00", "Z")
                dest.execute(
                    "INSERT INTO replay_migrations "
                    "(source_fingerprint, imported_count, exact_existing_count, completed_at_utc) "
                    "VALUES (?, ?, ?, ?)",
                    (fingerprint, inserted, exact_existing, completed),
                )
                dest.commit()
                logger.info(
                    "Replay migration committed: imported=%d exact_existing=%d",
                    inserted, exact_existing,
                )
                return True
        except ReplayMigrationError:
            try:
                dest.rollback()
            except (UnboundLocalError, sqlite3.Error):
                pass
            raise
        except (sqlite3.Error, OSError, ValueError, OverflowError) as exc:
            try:
                dest.rollback()
            except (UnboundLocalError, sqlite3.Error):
                pass
            raise ReplayMigrationError(
                f"CRITICAL: replay migration rolled back: {exc}"
            ) from exc


class VerifiedTaskIngressConnector:
    """Check a caller-supplied fresh witness challenge before task classification.

    The caller must obtain expected_challenge from an independently operated
    witness challenge exchange and supply its key_id. This connector performs
    no network calls, does not generate trust, and never authorizes execution.
    """

    def __init__(self, ingress_gate: Any, monotonicity_guard: Any, key_id: str):
        if not isinstance(key_id, str) or not key_id.strip():
            raise ValueError("a configured trusted witness key_id is required")
        self.ingress_gate = ingress_gate
        self.monotonicity_guard = monotonicity_guard
        self.key_id = key_id

    def handle_incoming_task(
        self,
        payload: dict,
        raw_body: bytes,
        signature: str,
        external_heartbeat: Mapping[str, Any],
        *,
        expected_challenge: str,
    ) -> dict:
        if not isinstance(raw_body, bytes):
            return {"decision": "GATE_CLOSED", "reason": "RAW_BODY_INVALID",
                    "execution_authorized": False}
        try:
            if raw_body != canonical_payload_bytes(payload):
                return {"decision": "GATE_CLOSED", "reason": "RAW_BODY_PAYLOAD_MISMATCH",
                        "execution_authorized": False}
        except (TypeError, ValueError, UnicodeError):
            return {"decision": "GATE_CLOSED", "reason": "RAW_BODY_PAYLOAD_INVALID",
                    "execution_authorized": False}
        try:
            valid, reason = self.monotonicity_guard.verify_state_integrity(
                external_heartbeat,
                expected_challenge=expected_challenge,
                key_id=self.key_id,
            )
        except Exception:
            valid, reason = False, "WITNESS_VERIFICATION_ERROR"
        if not valid:
            return {
                "decision": "GATE_CLOSED",
                "reason": f"WITNESS_REJECTED:{reason}",
                "execution_authorized": False,
            }
        try:
            decision = self.ingress_gate.validate(payload, signature)
            result = asdict(decision)
        except Exception:
            return {
                "decision": "GATE_CLOSED",
                "reason": "INGRESS_VALIDATION_ERROR",
                "execution_authorized": False,
            }
        return {
            "decision": result.get("status", "GATE_CLOSED"),
            "audit": result,
            "execution_authorized": False,
        }
