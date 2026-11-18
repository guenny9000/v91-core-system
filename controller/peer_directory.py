#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Durable peer directory for federation peers (Issue #103 environment).

Persistence layer behind the receiver's identity checks:
- SQLite-backed, restart-safe peer registry: membership, Ed25519
  public keys (hex), revocations with reasons, key rotation history
- fail-closed everywhere: unknown peer, revoked peer, expired peer and
  malformed keys all evaluate to NOT active (UNKNOWN != PASS)
- revocation is append-logged (never deleted), rotations keep the
  archived old key in a history table (ISOLATE_NOT_DESTROY)

Honest limits (DOCUMENTED != IMPLEMENTED elsewhere):
- NO key generation and NO private keys: the caller owns key material
  and its secure storage; this directory only records public facts
- NO network discovery, NO replication: this is a single-node registry;
  synchronizing directories across nodes is separate, reviewed work
- revocation takes effect for every consumer that queries this
  directory; the receiver is only as current as its last wiring
- NO expiry enforcement daemon: expiry is evaluated at query time
  against the provided now value (no timers, no background jobs)
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_ED25519_KEY_HEX_LEN = 64  # 32 raw bytes


class PeerDirectoryError(Exception):
    """Fail-closed directory error."""


@dataclass(frozen=True)
class PeerRecord:
    peer_id: str
    public_key_hex: str
    active: bool
    reason: str  # why active or not (audit-facing, not a secret)


class PeerDirectory:
    """Durable registry of federation peers with revocation and rotation."""

    def __init__(self, path: Path | str,
                 now_provider: Callable[[], int] | None = None) -> None:
        self._path = str(path)
        import time
        self._now = now_provider or (lambda: int(time.time()))
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS peers ("
                "peer_id TEXT PRIMARY KEY, public_key_hex TEXT NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'active', "
                "expires_at INTEGER NOT NULL, rotation_count INTEGER NOT NULL DEFAULT 0)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS revocation_log ("
                "peer_id TEXT NOT NULL, reason TEXT NOT NULL, at INTEGER NOT NULL)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS rotation_history ("
                "peer_id TEXT NOT NULL, old_key_hex TEXT NOT NULL, "
                "new_key_hex TEXT NOT NULL, at INTEGER NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=5.0)

    @staticmethod
    def _require_peer_id(peer_id: str) -> str:
        if not isinstance(peer_id, str) or not peer_id or len(peer_id) > 64:
            raise PeerDirectoryError("peer_id must be a non-empty string of at most 64 chars")
        return peer_id

    @staticmethod
    def _require_key_hex(public_key_hex: str) -> str:
        if not isinstance(public_key_hex, str) or len(public_key_hex) != _ED25519_KEY_HEX_LEN:
            raise PeerDirectoryError(
                f"public_key_hex must be exactly {_ED25519_KEY_HEX_LEN} hex chars")
        try:
            bytes.fromhex(public_key_hex)
        except ValueError as exc:
            raise PeerDirectoryError(f"public_key_hex is not valid hex: {exc}") from exc
        return public_key_hex

    def add_peer(self, *, peer_id: str, public_key_hex: str, expires_at: int) -> None:
        """Register a new peer. Refused on duplicates (rotation is explicit)."""
        peer_id = self._require_peer_id(peer_id)
        key = self._require_key_hex(public_key_hex)
        if type(expires_at) is not int or expires_at < 0:
            raise PeerDirectoryError("expires_at must be a non-negative int unix timestamp")
        with self._connect() as db:
            exists = db.execute("SELECT 1 FROM peers WHERE peer_id = ?",
                                (peer_id,)).fetchone()
            if exists:
                raise PeerDirectoryError(
                    f"peer {peer_id!r} already registered; use rotate_key, never re-add")
            db.execute("INSERT INTO peers (peer_id, public_key_hex, status, expires_at) "
                       "VALUES (?, ?, 'active', ?)", (peer_id, key, expires_at))
            db.commit()

    def revoke_peer(self, *, peer_id: str, reason: str) -> None:
        """Revoke a peer permanently; the log entry is never removed."""
        peer_id = self._require_peer_id(peer_id)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 256:
            raise PeerDirectoryError("a non-empty revocation reason (<= 256 chars) is required")
        with self._connect() as db:
            row = db.execute("SELECT status FROM peers WHERE peer_id = ?",
                             (peer_id,)).fetchone()
            if row is None:
                raise PeerDirectoryError(f"cannot revoke unknown peer {peer_id!r}")
            if row[1] == "revoked":
                raise PeerDirectoryError(f"peer {peer_id!r} is already revoked")
            db.execute("UPDATE peers SET status = 'revoked' WHERE peer_id = ?", (peer_id,))
            db.execute("INSERT INTO revocation_log (peer_id, reason, at) VALUES (?, ?, ?)",
                       (peer_id, reason, self._now()))
            db.commit()

    def rotate_key(self, *, peer_id: str, new_public_key_hex: str) -> None:
        """Archive the old key and activate a new one, in one transaction."""
        peer_id = self._require_peer_id(peer_id)
        new_key = self._require_key_hex(new_public_key_hex)
        with self._connect() as db:
            row = db.execute("SELECT public_key_hex, status FROM peers WHERE peer_id = ?",
                             (peer_id,)).fetchone()
            if row is None:
                raise PeerDirectoryError(f"cannot rotate unknown peer {peer_id!r}")
            if row[0] == new_key:
                raise PeerDirectoryError("new key must differ from the current key")
            if row[1] == "revoked":
                raise PeerDirectoryError(
                    f"peer {peer_id!r} is revoked; rotation of revoked peers is refused")
            db.execute("UPDATE peers SET public_key_hex = ?, "
                       "rotation_count = rotation_count + 1 WHERE peer_id = ?",
                       (new_key, peer_id))
            db.execute("INSERT INTO rotation_history (peer_id, old_key_hex, new_key_hex, at) "
                       "VALUES (?, ?, ?, ?)", (peer_id, row[0], new_key, self._now()))
            db.commit()

    def lookup(self, peer_id: str) -> PeerRecord | None:
        """Evaluate one peer's status at query time (revocation + expiry)."""
        peer_id = self._require_peer_id(peer_id)
        with self._connect() as db:
            row = db.execute(
                "SELECT public_key_hex, status, expires_at FROM peers WHERE peer_id = ?",
                (peer_id,)).fetchone()
        if row is None:
            return None
        key_hex, status, expires_at = row
        now = self._now()
        if status == "revoked":
            return PeerRecord(peer_id, key_hex, False, "revoked")
        if now >= expires_at:
            return PeerRecord(peer_id, key_hex, False,
                              f"expired at {expires_at} (now {now})")
        return PeerRecord(peer_id, key_hex, True,
                          f"active until {expires_at}")

    def active_keys(self) -> dict[str, str]:
        """Convenience view for wiring a receiver's peer_keys map."""
        result: dict[str, str] = {}
        with self._connect() as db:
            rows = db.execute(
                "SELECT peer_id, public_key_hex, status, expires_at FROM peers").fetchall()
        now = self._now()
        for peer_id, key_hex, status, expires_at in rows:
            if status == "active" and now < expires_at:
                result[peer_id] = key_hex
        return result

    def rotation_count(self, peer_id: str) -> int:
        with self._connect() as db:
            row = db.execute("SELECT rotation_count FROM peers WHERE peer_id = ?",
                             (peer_id,)).fetchone()
        if row is None:
            raise PeerDirectoryError(f"unknown peer {peer_id!r}")
        return int(row[0])
