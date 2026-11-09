"""Verify externally signed monotonic replay-store checkpoints.

This is a verification primitive only. The caller must obtain a fresh,
challenge-bound response from an independently operated witness. No network
client, durable witness, automatic isolation, or runtime integration is added.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Mapping, Protocol, Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

DOMAIN = b"V91-REPLAY-STATE-HEARTBEAT-v1\x00"
_HEX_32 = re.compile(r"^[0-9a-f]{64}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_FIELDS = {
    "schema_version",
    "database_id",
    "epoch",
    "sequence",
    "state_root_hash",
    "issued_at_utc",
    "challenge",
}


class StateHeartbeatError(ValueError):
    """Malformed or unsupported signed state heartbeat."""


class LocalReplayState(Protocol):
    def get_database_id(self) -> str: ...
    def get_last_logged_sequence(self) -> int: ...
    def compute_current_state_hash(self) -> str: ...


def _canonical(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise StateHeartbeatError("heartbeat is not canonically serializable") from exc


def _validated_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if set(payload) != _FIELDS:
        raise StateHeartbeatError("heartbeat fields do not match schema v1")
    if payload["schema_version"] != 1:
        raise StateHeartbeatError("unsupported heartbeat schema")
    database_id = payload["database_id"]
    if not isinstance(database_id, str) or not database_id or len(database_id) > 128:
        raise StateHeartbeatError("invalid database_id")
    for name in ("epoch", "sequence"):
        value = payload[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise StateHeartbeatError(f"{name} must be a non-negative integer")
    root = payload["state_root_hash"]
    if not isinstance(root, str) or not _HEX_32.fullmatch(root):
        raise StateHeartbeatError("state_root_hash must be lowercase SHA-256 hex")
    challenge = payload["challenge"]
    if not isinstance(challenge, str) or not _HEX_32.fullmatch(challenge):
        raise StateHeartbeatError("challenge must be 256-bit lowercase hex")
    issued = payload["issued_at_utc"]
    if not isinstance(issued, str):
        raise StateHeartbeatError("issued_at_utc must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(issued.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StateHeartbeatError("invalid issued_at_utc") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StateHeartbeatError("issued_at_utc must include a timezone")
    return {
        "schema_version": 1,
        "database_id": database_id,
        "epoch": payload["epoch"],
        "sequence": payload["sequence"],
        "state_root_hash": root,
        "issued_at_utc": issued,
        "challenge": challenge,
    }


class V91StateMonotonicityGuard:
    """Fail-closed comparison against a fresh, trusted external witness."""

    def __init__(
        self,
        local_state_provider: LocalReplayState,
        trusted_keys: Mapping[str, Ed25519PublicKey],
        *,
        max_age_seconds: int = 300,
        clock=lambda: datetime.now(timezone.utc),
    ) -> None:
        if isinstance(max_age_seconds, bool) or max_age_seconds < 1:
            raise ValueError("max_age_seconds must be positive")
        self._local = local_state_provider
        self._trusted_keys = dict(trusted_keys)
        self._max_age = max_age_seconds
        self._clock = clock

    def verify_state_integrity(
        self,
        envelope: Mapping[str, Any],
        *,
        expected_challenge: str,
        key_id: str,
    ) -> tuple[bool, str]:
        if not isinstance(expected_challenge, str) or not _HEX_32.fullmatch(expected_challenge):
            return False, "INVALID_EXPECTED_CHALLENGE"
        if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
            return False, "INVALID_KEY_ID"
        public_key = self._trusted_keys.get(key_id)
        if public_key is None:
            return False, "UNKNOWN_WITNESS_KEY"
        if not isinstance(envelope, Mapping) or set(envelope) != {"algorithm", "key_id", "payload", "signature"}:
            return False, "INVALID_HEARTBEAT_ENVELOPE"
        if envelope["algorithm"] != "Ed25519" or envelope["key_id"] != key_id:
            return False, "INVALID_HEARTBEAT_ALGORITHM_OR_KEY"
        signature = envelope["signature"]
        if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{128}", signature):
            return False, "INVALID_HEARTBEAT_SIGNATURE_FORMAT"
        try:
            payload = _validated_payload(envelope["payload"])
            message = DOMAIN + _canonical(payload)
            public_key.verify(bytes.fromhex(signature), message)
        except InvalidSignature:
            return False, "HEARTBEAT_SIGNATURE_INVALID"
        except (StateHeartbeatError, TypeError, AttributeError):
            return False, "INVALID_HEARTBEAT_PAYLOAD"

        if payload["challenge"] != expected_challenge:
            return False, "HEARTBEAT_CHALLENGE_MISMATCH"
        try:
            local_database_id = self._local.get_database_id()
        except Exception:
            return False, "LOCAL_STATE_UNAVAILABLE"
        if payload["database_id"] != local_database_id:
            return False, "DATABASE_ID_MISMATCH"

        try:
            issued = datetime.fromisoformat(payload["issued_at_utc"].replace("Z", "+00:00"))
            now = self._clock()
            if now.tzinfo is None or now.utcoffset() is None:
                return False, "LOCAL_CLOCK_NOT_TIMEZONE_AWARE"
            age = (now - issued).total_seconds()
        except (TypeError, ValueError, AttributeError):
            return False, "INVALID_LOCAL_CLOCK"
        if age < -self._max_age or age > self._max_age:
            return False, "HEARTBEAT_OUTSIDE_FRESHNESS_WINDOW"

        try:
            local_sequence = self._local.get_last_logged_sequence()
            local_hash = self._local.compute_current_state_hash()
        except Exception:
            return False, "LOCAL_STATE_UNAVAILABLE"
        if isinstance(local_sequence, bool) or not isinstance(local_sequence, int) or local_sequence < 0:
            return False, "LOCAL_SEQUENCE_INVALID"
        if not isinstance(local_hash, str) or not _HEX_32.fullmatch(local_hash):
            return False, "LOCAL_STATE_HASH_INVALID"

        witness_sequence = payload["sequence"]
        if local_sequence < witness_sequence:
            return False, "ROLLBACK_DETECTED_SEQUENCE"
        if local_sequence == witness_sequence and local_hash != payload["state_root_hash"]:
            return False, "STATE_ROOT_MISMATCH"
        if local_sequence > witness_sequence:
            return False, "LOCAL_STATE_AHEAD_OF_WITNESS"
        return True, "STATE_VALID_AND_MONOTONIC"
