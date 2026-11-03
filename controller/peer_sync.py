"""Local, transport-independent peer heartbeat validation for V91.

This module does not open sockets, execute peer-supplied code, or grant authority.
It provides a small authenticated message format and a local freshness/replay
state machine. HMAC is symmetric authentication for a controlled MVP; it is
not a public-key identity system or non-repudiation mechanism.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = 1


class HeartbeatError(ValueError):
    """Raised when a heartbeat cannot be safely constructed or parsed."""


@dataclass(frozen=True)
class PeerHeartbeat:
    peer_id: str
    key_id: str
    sequence: int
    timestamp: float
    software_version: str
    capabilities: tuple[str, ...]
    state: str
    signature: str
    schema_version: int = SCHEMA_VERSION

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "peer_id": self.peer_id,
            "key_id": self.key_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "software_version": self.software_version,
            "capabilities": list(self.capabilities),
            "state": self.state,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.unsigned_payload()
        payload["signature"] = self.signature
        return payload


@dataclass(frozen=True)
class PeerResult:
    peer_id: str | None
    state: str
    reason: str
    sequence: int | None = None


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def create_heartbeat(
    *,
    peer_id: str,
    key_id: str,
    secret: bytes,
    sequence: int,
    software_version: str,
    capabilities: tuple[str, ...] | list[str] = (),
    state: str = "READY",
    timestamp: float | None = None,
) -> dict[str, Any]:
    """Create a signed heartbeat dictionary; caller retains key custody."""
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise HeartbeatError("secret must contain at least 32 bytes")
    if not peer_id or not key_id or not software_version:
        raise HeartbeatError("peer_id, key_id and software_version are required")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise HeartbeatError("sequence must be a positive integer")
    if state not in {"READY", "BUSY", "DEGRADED", "STOPPING"}:
        raise HeartbeatError("unsupported peer state")
    caps = tuple(capabilities)
    if any(not isinstance(item, str) or not item for item in caps):
        raise HeartbeatError("capabilities must be non-empty strings")
    if len(set(caps)) != len(caps):
        raise HeartbeatError("capabilities must be unique")
    sent_at = time.time() if timestamp is None else timestamp
    if isinstance(sent_at, bool) or not isinstance(sent_at, (int, float)):
        raise HeartbeatError("timestamp must be numeric")
    if not math.isfinite(sent_at):
        raise HeartbeatError("timestamp must be finite")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "peer_id": peer_id,
        "key_id": key_id,
        "sequence": sequence,
        "timestamp": float(sent_at),
        "software_version": software_version,
        "capabilities": sorted(caps),
        "state": state,
    }
    signature = hmac.new(secret, _canonical_bytes(payload), hashlib.sha256).hexdigest()
    payload["signature"] = signature
    return payload


class PeerRegistry:
    """In-memory trust registry and replay/freshness gate.

    trusted_keys maps key_id to (expected_peer_id, secret_bytes). Persisting
    secrets, distributing trust roots, key rotation and revocation are
    deliberately outside this module's scope.
    """

    def __init__(
        self,
        trusted_keys: Mapping[str, tuple[str, bytes]],
        *,
        max_age_seconds: float = 90.0,
        max_future_skew_seconds: float = 15.0,
    ) -> None:
        if max_age_seconds <= 0 or max_future_skew_seconds < 0:
            raise ValueError("invalid freshness limits")
        self._trusted_keys = dict(trusted_keys)
        self._max_age = float(max_age_seconds)
        self._future_skew = float(max_future_skew_seconds)
        self._last_sequence: dict[str, int] = {}
        self._states: dict[str, PeerResult] = {}
        self._accepted_at: dict[str, float] = {}

    @property
    def states(self) -> dict[str, PeerResult]:
        """Return a copy so callers cannot mutate registry state."""
        return dict(self._states)

    def receive(self, message: Mapping[str, Any], *, now: float | None = None) -> PeerResult:
        """Validate one message as untrusted data; never execute its contents."""
        current_time = time.time() if now is None else now
        try:
            required = {
                "schema_version", "peer_id", "key_id", "sequence", "timestamp",
                "software_version", "capabilities", "state", "signature",
            }
            if set(message) != required:
                raise HeartbeatError("schema fields do not match")
            peer_id = message["peer_id"]
            key_id = message["key_id"]
            sequence = message["sequence"]
            timestamp = message["timestamp"]
            if (
                isinstance(message["schema_version"], bool)
                or message["schema_version"] != SCHEMA_VERSION
            ):
                raise HeartbeatError("unsupported schema version")
            if not isinstance(peer_id, str) or not peer_id:
                raise HeartbeatError("invalid peer_id")
            if not isinstance(key_id, str) or not key_id:
                raise HeartbeatError("invalid key_id")
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
                raise HeartbeatError("invalid sequence")
            if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
                raise HeartbeatError("invalid timestamp")
            if not math.isfinite(timestamp):
                raise HeartbeatError("invalid timestamp")
            if not isinstance(message["software_version"], str) or not message["software_version"]:
                raise HeartbeatError("invalid software_version")
            if not isinstance(message["capabilities"], list) or any(
                not isinstance(item, str) or not item for item in message["capabilities"]
            ):
                raise HeartbeatError("invalid capabilities")
            if len(set(message["capabilities"])) != len(message["capabilities"]):
                raise HeartbeatError("duplicate capabilities")
            if message["state"] not in {"READY", "BUSY", "DEGRADED", "STOPPING"}:
                raise HeartbeatError("invalid state")
            signature = message["signature"]
            if not isinstance(signature, str) or len(signature) != 64:
                raise HeartbeatError("invalid signature format")
            if not isinstance(current_time, (int, float)) or not math.isfinite(current_time):
                raise HeartbeatError("invalid receiver time")
        except (HeartbeatError, TypeError, ValueError) as exc:
            return PeerResult(None, "INVALID", str(exc))

        trusted = self._trusted_keys.get(key_id)
        if trusted is None:
            return PeerResult(peer_id, "INVALID", "unknown key_id", sequence)
        expected_peer_id, secret = trusted
        if peer_id != expected_peer_id:
            return PeerResult(peer_id, "INVALID", "key is not bound to this peer_id", sequence)
        if not isinstance(secret, bytes) or len(secret) < 32:
            return PeerResult(peer_id, "INVALID", "trusted key material is invalid", sequence)

        payload = {key: value for key, value in message.items() if key != "signature"}
        expected_signature = hmac.new(
            secret, _canonical_bytes(payload), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return PeerResult(peer_id, "INVALID", "signature verification failed", sequence)

        age = float(current_time) - float(timestamp)
        if age < -self._future_skew:
            return PeerResult(
                peer_id, "INVALID", "heartbeat timestamp is too far in the future", sequence
            )
        previous = self._last_sequence.get(peer_id, 0)
        if sequence <= previous:
            return PeerResult(peer_id, "INVALID", "replay or non-increasing sequence", sequence)
        self._last_sequence[peer_id] = sequence

        if age > self._max_age:
            result = PeerResult(peer_id, "STALE", "heartbeat exceeded freshness window", sequence)
        else:
            result = PeerResult(
                peer_id, "ALIVE_VERIFIED", "signature and freshness verified", sequence
            )
            self._accepted_at[peer_id] = float(current_time)
        self._states[peer_id] = result
        return result

    def mark_unseen_stale(self, *, now: float | None = None) -> dict[str, PeerResult]:
        """Mark previously verified peers stale when their last heartbeat expires.

        The caller invokes this on demand; this class starts no background loop.
        """
        current_time = time.time() if now is None else now
        for peer_id, result in tuple(self._states.items()):
            if result.state == "ALIVE_VERIFIED":
                # The timestamp is stored separately only for accepted messages.
                accepted_at = self._accepted_at.get(peer_id)
                if accepted_at is not None and current_time - accepted_at > self._max_age:
                    self._states[peer_id] = PeerResult(
                        peer_id, "STALE", "no fresh heartbeat within configured window",
                        result.sequence,
                    )
        return self.states

    def receive_and_track(
        self, message: Mapping[str, Any], *, now: float | None = None
    ) -> PeerResult:
        """Receive a heartbeat and retain receiver-time for stale marking."""
        current_time = time.time() if now is None else now
        result = self.receive(message, now=current_time)
        if result.state == "ALIVE_VERIFIED" and result.peer_id is not None:
            self._accepted_at[result.peer_id] = float(current_time)
        return result
