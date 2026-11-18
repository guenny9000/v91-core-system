#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Federation envelope sender core (Issue #103, Phase 3).

The mirror of the receiver: builds authenticated, replay-safe
envelopes for THIS node's outbound federation messages.
- Ed25519 signatures over the canonical signed payload (same wire
  contract as controller/federation_receiver.py; hex-encoded because
  JSON carries no bytes)
- durable, restart-safe monotonic sequence per epoch (SQLite, one
  committed transaction per envelope; gaps are impossible because the
  counter advances only on successfully signed builds)
- fail-closed input validation: non-dict payloads, non-JSON values,
  NaN/Inf, and oversized envelopes are refused before any counter
  advance (a refused build must never burn a sequence number)

Honest limits (DOCUMENTED != IMPLEMENTED elsewhere):
- NO network, NO sockets, NO queueing: build_envelope returns wire
  bytes; transmitting them is the caller's separately reviewed job
  (SHIPPING != INSTALLATION)
- NO private-key storage or rotation: the caller owns the key and its
  lifecycle (peer revocation on the receiving side stays the
  receiver's business)
- NO delivery guarantees, NO retries, NO acks: the receiver's durable
  replay floors make retransmission safe, but nothing here tracks
  whether an envelope ever arrived
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

MAX_PAYLOAD_BYTES = 8192  # mirrors the receiver envelope payload bound


class SenderError(Exception):
    """Fail-closed sender error (validation or state problems)."""


class SequenceStore:
    """Durable per-epoch monotonic sequence counter (restart-safe)."""

    def __init__(self, path: Path | str) -> None:
        self._path = str(path)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS outbound_sequence ("
                "peer_id TEXT NOT NULL, epoch INTEGER NOT NULL, "
                "last_seq INTEGER NOT NULL, PRIMARY KEY (peer_id, epoch))"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=5.0)

    def next_sequence(self, peer_id: str, epoch: int) -> int:
        """Advance and commit the counter in one transaction.

        The commit happens BEFORE the envelope is handed out: a crash
        after next_sequence() may burn a number (a gap), but can never
        rewind the floor, because a rewound floor would make our own
        future envelopes look like replays to honest receivers.
        """
        with self._connect() as db:
            row = db.execute(
                "SELECT last_seq FROM outbound_sequence WHERE peer_id = ? AND epoch = ?",
                (peer_id, epoch)).fetchone()
            last = row[0] if row else 0
            next_seq = last + 1
            db.execute(
                "INSERT INTO outbound_sequence (peer_id, epoch, last_seq) VALUES (?, ?, ?) "
                "ON CONFLICT(peer_id, epoch) DO UPDATE SET last_seq = excluded.last_seq",
                (peer_id, epoch, next_seq))
            db.commit()
            return next_seq


@dataclass(frozen=True)
class Envelope:
    wire: bytes
    epoch: int
    sequence: int


class EnvelopeSender:
    """Builds signed federation envelopes with durable sequence numbers."""

    def __init__(self, *, peer_id: str, private_key: Ed25519PrivateKey,
                 sequence_store: SequenceStore, epoch: int = 1,
                 now_provider: Callable[[], int] | None = None) -> None:
        if not isinstance(peer_id, str) or not peer_id or len(peer_id) > 64:
            raise SenderError("peer_id must be a non-empty string of at most 64 chars")
        if not isinstance(private_key, Ed25519PrivateKey):
            raise SenderError("an Ed25519 private key is required (HMAC is not identity)")
        if not isinstance(sequence_store, SequenceStore):
            raise SenderError("a durable SequenceStore is required (fail-closed)")
        if type(epoch) is not int or epoch < 0:
            raise SenderError("epoch must be a non-negative int (bool is not accepted)")
        import time
        self._now = now_provider or (lambda: int(time.time()))
        self._peer_id = peer_id
        self._key = private_key
        self._store = sequence_store
        self._epoch = epoch

    def build_envelope(self, payload: dict[str, Any]) -> Envelope:
        """Validate, number, sign, and serialize one outbound envelope.

        Fail-closed: validation happens BEFORE the sequence counter
        advances; a refused payload never consumes a number.
        """
        if not isinstance(payload, dict):
            raise SenderError("payload must be a JSON object (dict)")
        try:
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise SenderError(f"payload is not JSON-serializable: {exc}") from exc
        if len(encoded) > MAX_PAYLOAD_BYTES:
            raise SenderError(f"payload too large: {len(encoded)} > {MAX_PAYLOAD_BYTES} bytes")

        sequence = self._store.next_sequence(self._peer_id, self._epoch)
        issued_at = self._now()
        if type(issued_at) is not int or issued_at < 0:
            # Counter already advanced; refuse loudly rather than emit garbage.
            raise SenderError(f"now_provider returned an invalid timestamp: {issued_at!r}")
        signed_payload = {
            "schema_version": 1, "peer_id": self._peer_id, "epoch": self._epoch,
            "sequence": sequence, "issued_at": issued_at, "payload": payload,
        }
        canonical = json.dumps(signed_payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False).encode("utf-8")
        signature = self._key.sign(canonical).hex()
        envelope = dict(signed_payload)
        envelope["signature"] = signature
        wire = json.dumps(envelope, sort_keys=True,
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
        return Envelope(wire=wire, epoch=self._epoch, sequence=sequence)
