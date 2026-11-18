#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schoepfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Federation receiver core (Issue #103, Phase 1).

Authenticated, fail-closed intake for federation messages:
- versioned, bounded envelope schema
- Ed25519 peer identity with explicit membership, revocation and expiry
  (signatures are public-key identities; HMAC is NOT used as identity)
- durable, restart-safe per-peer replay protection (SQLite sequence
  floors, strict in-order sequencing per epoch)
- optional quarantine ledger preserving the exact raw bytes of every
  rejected envelope (append-only hash chain, nothing is deleted)

Honest limits (DOCUMENTED != IMPLEMENTED elsewhere):
- NO transport, peer discovery, daemon, or network listener: this module
  validates envelopes handed to it; wiring to a socket is a later,
  separately reviewed phase (SHIPPING != INSTALLATION).
- NO command execution: an ACCEPTED envelope is returned to the caller;
  the receiver never executes payload content (DETECTION != AUTHORIZATION).
- Rate limiting is an in-memory per-instance guard, not a durable
  cross-restart quota.
- Restart-safety of replay floors depends on the SQLite file's durability;
  the store verifies monotonicity on every claim.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ENVELOPE_VERSION = 1
MAX_ENVELOPE_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 8 * 1024
GENESIS = "0" * 64
_HEX_SIGNATURE = re.compile(r"^[0-9a-f]{128}$")
_ALLOWED_KEYS = {
    "schema_version", "peer_id", "epoch", "sequence", "issued_at",
    "payload", "signature",
}


class FederationError(Exception):
    """Fail-closed receiver error."""


class Receipt:
    """Outcome of one receive call. ACCEPTED never implies execution."""

    def __init__(self, status: str, reason: str = "", message: dict | None = None,
                 quarantined: bool = False) -> None:
        self.status = status
        self.reason = reason
        self.message = message
        self.quarantined = quarantined

    def __repr__(self) -> str:  # pragma: no cover
        return f"Receipt(status={self.status!r}, reason={self.reason!r})"


class FederationReplayStore:
    """Durable per-peer sequence floors. Restart-safe via SQLite commits."""

    def __init__(self, path: Path | str) -> None:
        self._path = str(path)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS replay_floors ("
                "peer_id TEXT NOT NULL, epoch INTEGER NOT NULL, last_seq INTEGER NOT NULL,"
                " PRIMARY KEY (peer_id))"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=5.0)

    def claim(self, peer_id: str, epoch: int, sequence: int) -> tuple[bool, str]:
        """Advance the floor only for the exact next sequence of the current epoch."""
        with self._connect() as db:
            row = db.execute(
                "SELECT epoch, last_seq FROM replay_floors WHERE peer_id = ?", (peer_id,)
            ).fetchone()
            if row is None:
                if sequence != 1:
                    return False, "first message of a peer must use sequence 1"
                db.execute(
                    "INSERT INTO replay_floors (peer_id, epoch, last_seq) VALUES (?, ?, ?)",
                    (peer_id, epoch, sequence),
                )
                return True, ""
            stored_epoch, last_seq = int(row[0]), int(row[1])
            if epoch < stored_epoch:
                return False, f"stale epoch {epoch} (floor epoch {stored_epoch})"
            if epoch > stored_epoch:
                if sequence != 1:
                    return False, f"new epoch {epoch} must restart at sequence 1"
                db.execute(
                    "UPDATE replay_floors SET epoch = ?, last_seq = ? WHERE peer_id = ?",
                    (epoch, sequence, peer_id),
                )
                return True, ""
            if sequence <= last_seq:
                return False, f"duplicate or reordered sequence {sequence} (floor {last_seq})"
            if sequence != last_seq + 1:
                return False, f"sequence gap: expected {last_seq + 1}, got {sequence}"
            db.execute(
                "UPDATE replay_floors SET last_seq = ? WHERE peer_id = ?",
                (sequence, peer_id),
            )
            return True, ""


class QuarantineLedger:
    """Append-only hash-chained ledger preserving exact raw bytes."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._prev = GENESIS
        if self._path.exists():
            prev = GENESIS
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("prev_hash") != prev or entry.get("entry_hash") != self._hash(entry):
                    raise FederationError("quarantine ledger chain invalid; refusing appends")
                prev = entry["entry_hash"]
            self._prev = prev

    @staticmethod
    def _hash(entry: dict[str, Any]) -> str:
        payload = {k: v for k, v in entry.items() if k != "entry_hash"}
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def append(self, raw: bytes, reason: str, peer_id: str) -> None:
        record: dict[str, Any] = {
            "kind": "FEDERATION_QUARANTINE",
            "peer_id": peer_id,
            "reason": reason,
            "raw_b64": base64.b64encode(raw).decode("ascii"),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "received_at_unix": time.time(),
        }
        record["prev_hash"] = self._prev
        record["entry_hash"] = self._hash(record)
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._prev = record["entry_hash"]


class FederationReceiver:
    """Validate one envelope end-to-end. Fail closed. Never executes payloads."""

    def __init__(self, *, peer_keys: dict[str, Ed25519PublicKey],
                 replay_store: FederationReplayStore,
                 revoked_peer_ids: set[str] | None = None,
                 peer_expires_at: dict[str, int] | None = None,
                 now_provider: Callable[[], int] | None = None,
                 allowed_clock_skew_seconds: int = 60,
                 quarantine: QuarantineLedger | None = None,
                 max_messages_per_minute: int = 120) -> None:
        if not peer_keys:
            raise FederationError("explicit membership required: peer_keys must not be empty")
        for peer_id, key in peer_keys.items():
            if not isinstance(peer_id, str) or not peer_id.strip() or not isinstance(key, Ed25519PublicKey):
                raise FederationError("each peer needs a non-empty id and an Ed25519PublicKey")
        if type(allowed_clock_skew_seconds) is not int or allowed_clock_skew_seconds < 0:
            raise FederationError("clock skew must be a non-negative integer")
        if type(max_messages_per_minute) is not int or max_messages_per_minute < 1:
            raise FederationError("rate limit must be a positive integer")
        self._peers = dict(peer_keys)
        self._revoked = set(revoked_peer_ids or ())
        self._expires_at = dict(peer_expires_at or {})
        self._replay = replay_store
        self._now = now_provider or (lambda: int(time.time()))
        self._skew = allowed_clock_skew_seconds
        self._quarantine = quarantine
        self._rate_max = max_messages_per_minute
        self._rate_window: list[int] = []

    def _rate_limited(self) -> bool:
        now = self._now()
        self._rate_window = [t for t in self._rate_window if now - t < 60]
        if len(self._rate_window) >= self._rate_max:
            return True
        self._rate_window.append(now)
        return False

    def receive(self, raw: bytes) -> Receipt:
        def reject(reason: str, peer_id: str = "unknown") -> Receipt:
            if self._quarantine is not None:
                self._quarantine.append(raw, reason, peer_id)
            return Receipt("REJECTED", reason=reason, quarantined=self._quarantine is not None)

        if not isinstance(raw, bytes) or not raw or len(raw) > MAX_ENVELOPE_BYTES:
            return reject("envelope missing or oversized")
        if self._rate_limited():
            return reject("rate limit exceeded")
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return reject(f"malformed envelope: {exc}")
        if not isinstance(envelope, dict) or set(envelope) != _ALLOWED_KEYS:
            return reject("envelope schema mismatch")
        if envelope["schema_version"] != ENVELOPE_VERSION:
            return reject(f"unsupported schema version {envelope['schema_version']!r}")
        peer_id = envelope["peer_id"]
        if not isinstance(peer_id, str) or not peer_id.strip():
            return reject("peer_id must be a non-empty string")
        key = self._peers.get(peer_id)
        if key is None:
            return reject(f"unknown peer {peer_id!r}", peer_id)
        if peer_id in self._revoked:
            return reject(f"revoked peer {peer_id!r}", peer_id)
        expires_at = self._expires_at.get(peer_id)
        now = self._now()
        if expires_at is not None and now > expires_at:
            return reject(f"peer key expired for {peer_id!r}", peer_id)
        epoch, sequence, issued_at = envelope["epoch"], envelope["sequence"], envelope["issued_at"]
        if any(type(v) is not int or v < 0 for v in (epoch, sequence, issued_at)):
            return reject("epoch, sequence and issued_at must be non-negative integers", peer_id)
        if abs(now - issued_at) > self._skew:
            return reject("timestamp outside allowed window", peer_id)
        payload = envelope["payload"]
        if not isinstance(payload, dict) or len(json.dumps(payload)) > MAX_PAYLOAD_BYTES:
            return reject("payload must be a bounded object", peer_id)
        signature = envelope["signature"]
        if not isinstance(signature, str) or not _HEX_SIGNATURE.fullmatch(signature):
            return reject("signature must be a lowercase hex string", peer_id)
        signed_payload = {k: v for k, v in envelope.items() if k != "signature"}
        try:
            key.verify(bytes.fromhex(signature),
                       json.dumps(signed_payload, sort_keys=True,
                                  separators=(",", ":")).encode("utf-8"))
        except InvalidSignature:
            return reject("signature verification failed", peer_id)
        accepted, reason = self._replay.claim(peer_id, epoch, sequence)
        if not accepted:
            return reject(reason, peer_id)
        return Receipt("ACCEPTED", message=signed_payload)
