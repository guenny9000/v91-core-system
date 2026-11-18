#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Signed peer heartbeats for V91 (Issue #37, items 2+3+5+6).

Closes the gap between HMAC transport checks (peer_sync) and Ed25519
origin proof for peer heartbeats. This module REUSES existing systems
instead of building duplicates (NO_DUPLICATE_SYSTEMS):

- crypto_receipts.canonical_record_bytes / sign_record /
  verify_record_signature: canonical byte stream and Ed25519 signature
  (items 2+3). The heartbeat is a signed record like a crypto receipt.
- peer_directory.PeerDirectory: the trust registry with revocation and
  expiry (item 5). There is exactly one registry; this module never
  keeps its own allowlist and NEVER takes a public key from the
  envelope (UNKNOWN != PASS: an unknown peer is rejected before any
  signature is even attempted).
- cooperation_register.Verification: verified heartbeats are exported
  as register evidence (ALIVE_VERIFIED only after every check ran).

Verification order is fail-closed and evidence-explicit:
  1. shape (kind, schema, types, signature format),
  2. unknown peer -> rejected (no key from the envelope),
  3. trust check via the directory at verification time
     (revoked or expired -> rejected),
  4. Ed25519 signature over the canonical unsigned record,
  5. freshness window (age > TTL -> stale; timestamp further in the
     future than max_future_seconds -> rejected; no abs() that would
     accept far-future timestamps),
  6. anti-replay: the nonce cache is consulted and extended ONLY AFTER
     the signature check passed (a forged envelope cannot burn a
     legitimate nonce), and the cache is bounded with time-based
     eviction (no unbounded memory growth).

signature_checked / freshness_checked / replay_checked become True
only when that check actually ran and passed; anything else stays
False (SCRIPTED != INSTALLED).

Honest limits: the nonce cache is in-memory and per process; a restart
forgets seen nonces; v1 caches by (peer_id, nonce) pair because the
registry has no per-peer sequence for heartbeats. This module has no
network code, no daemon and grants nothing: a verified heartbeat is
evidence about origin, not authorization (DETECTION != AUTHORIZATION).
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from controller import crypto_receipts
from controller.cooperation_register import Verification as _RegisterVerification
from controller.peer_directory import PeerDirectory

HEARTBEAT_KIND = "V91_SIGNED_HEARTBEAT"
SCHEMA_VERSION = 1
SIGNATURE_FIELD = crypto_receipts.SIGNATURE_FIELD
ORIGIN_VERIFIED = "VERIFIED_ORIGIN"
ORIGIN_REJECTED = "ORIGIN_REJECTED"
DEFAULT_TTL_SECONDS = 30.0
DEFAULT_MAX_FUTURE_SECONDS = 5.0
NONCE_MIN_BYTES = 8
NONCE_MAX_BYTES = 32
DEFAULT_MAX_SEEN_NONCES = 10000
_SIGNATURE_HEX_LENGTH = 128


class SignedHeartbeatError(Exception):
    """Raised for caller errors (bad parameters), never for rejects."""


@dataclass(frozen=True)
class HeartbeatVerification:
    """Result of one heartbeat verification (evidence, not a verdict)."""

    state: str
    reason: str
    peer_id: str = ""
    timestamp: Optional[float] = None
    nonce: Optional[str] = None
    signature_checked: bool = False
    freshness_checked: bool = False
    replay_checked: bool = False

    def as_register_verification(self) -> _RegisterVerification:
        """Export as cooperation-register evidence (degrades fail-closed).

        ALIVE_VERIFIED only for a fully verified origin; everything
        else becomes INVALID so the register never upgrades a view on
        incomplete evidence (CLAIM != EVIDENCE).
        """
        if (
            self.state == ORIGIN_VERIFIED
            and self.signature_checked
            and self.freshness_checked
            and self.replay_checked
        ):
            return _RegisterVerification(
                state="ALIVE_VERIFIED",
                reason=self.reason,
                signature_checked=True,
                freshness_checked=True,
                replay_checked=True,
            )
        return _RegisterVerification(
            state="INVALID",
            reason=f"{self.state}: {self.reason}",
            signature_checked=self.signature_checked,
            freshness_checked=self.freshness_checked,
            replay_checked=self.replay_checked,
        )


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SignedHeartbeatError(f"{label} must be a non-empty string")
    return value


def _require_nonce_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SignedHeartbeatError(f"{label} must be a non-empty hex string")
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        raise SignedHeartbeatError(f"{label} must be hex: {exc}") from exc
    if not (NONCE_MIN_BYTES <= len(raw) <= NONCE_MAX_BYTES):
        raise SignedHeartbeatError(
            f"{label} must be {NONCE_MIN_BYTES}..{NONCE_MAX_BYTES} bytes"
        )
    return value


def _validate_metrics(metrics: Any) -> dict[str, Any]:
    """Whitelist metric values; bool is explicitly NOT a number here."""
    if not isinstance(metrics, Mapping):
        raise SignedHeartbeatError("metrics must be a mapping")
    checked: dict[str, Any] = {}
    for key, value in metrics.items():
        _require_text(key, "metric key")
        if isinstance(value, bool) or value is None:
            raise SignedHeartbeatError(f"metric {key!r}: bool/None not allowed")
        if isinstance(value, str):
            if not value:
                raise SignedHeartbeatError(f"metric {key!r}: empty string")
            checked[key] = value
        elif isinstance(value, (int, float)):
            if not math.isfinite(float(value)):
                raise SignedHeartbeatError(f"metric {key!r}: must be finite")
            checked[key] = value
        else:
            raise SignedHeartbeatError(f"metric {key!r}: unsupported type")
    return checked


def _require_finite_positive(value: Any, label: str, allow_zero: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SignedHeartbeatError(f"{label} must be a number")
    number = float(value)
    if not math.isfinite(number) or (number <= 0 if not allow_zero else number < 0):
        raise SignedHeartbeatError(f"{label} must be finite and positive")
    return number


def build_heartbeat(
    private_key: bytes,
    *,
    peer_id: str,
    key_id: str,
    metrics: Mapping[str, Any],
    nonce: Optional[str] = None,
    now_provider: Optional[Callable[[], float]] = None,
) -> dict[str, Any]:
    """Build and sign one heartbeat envelope (items 2+3).

    Returns the canonical record plus SIGNATURE_FIELD (Ed25519 over
    the canonical bytes of the unsigned record).
    """
    _require_text(peer_id, "peer_id")
    _require_text(key_id, "key_id")
    checked_metrics = _validate_metrics(metrics)
    nonce = _require_nonce_value(
        os.urandom(8).hex() if nonce is None else nonce, "nonce"
    )
    timestamp = float(time.time() if now_provider is None else now_provider())
    if not math.isfinite(timestamp):
        raise SignedHeartbeatError("timestamp must be finite")
    record: dict[str, Any] = {
        "kind": HEARTBEAT_KIND,
        "schema_version": SCHEMA_VERSION,
        "peer_id": peer_id,
        "key_id": key_id,
        "timestamp": timestamp,
        "nonce": nonce,
        "metrics": checked_metrics,
    }
    signature = crypto_receipts.sign_record(record, private_key)
    envelope = dict(record)
    envelope[SIGNATURE_FIELD] = signature
    return envelope


class SignedHeartbeatVerifier:
    """Verify signed heartbeats fail-closed (items 5+6).

    The verifier holds no keys of its own: trust comes exclusively
    from the peer directory at verification time (revocation and
    rotation are honored automatically).
    """

    def __init__(
        self,
        *,
        peer_directory: PeerDirectory,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_future_seconds: float = DEFAULT_MAX_FUTURE_SECONDS,
        now_provider: Optional[Callable[[], float]] = None,
        max_seen_nonces: int = DEFAULT_MAX_SEEN_NONCES,
    ) -> None:
        if not callable(getattr(peer_directory, "lookup", None)):
            raise SignedHeartbeatError("peer_directory must provide lookup()")
        self._ttl = _require_finite_positive(ttl_seconds, "ttl_seconds", False)
        self._max_future = _require_finite_positive(
            max_future_seconds, "max_future_seconds", True
        )
        if isinstance(max_seen_nonces, bool) or not isinstance(
            max_seen_nonces, int
        ) or max_seen_nonces < 1:
            raise SignedHeartbeatError("max_seen_nonces must be a positive int")
        self._directory = peer_directory
        self._now = now_provider or time.time
        self._max_seen = max_seen_nonces
        self._seen: dict[tuple[str, str], float] = {}

    def _reject(self, reason: str, envelope: Mapping[str, Any]) -> HeartbeatVerification:
        peer_id = envelope.get("peer_id") if isinstance(envelope, Mapping) else None
        timestamp = envelope.get("timestamp") if isinstance(envelope, Mapping) else None
        nonce = envelope.get("nonce") if isinstance(envelope, Mapping) else None
        return HeartbeatVerification(
            state=ORIGIN_REJECTED,
            reason=reason,
            peer_id=peer_id if isinstance(peer_id, str) else "",
            timestamp=timestamp if isinstance(timestamp, (int, float)) else None,
            nonce=nonce if isinstance(nonce, str) else None,
        )

    def _check_shape(self, envelope: Mapping[str, Any]) -> Optional[str]:
        if envelope.get("kind") != HEARTBEAT_KIND:
            return f"kind must be {HEARTBEAT_KIND}"
        if envelope.get("schema_version") != SCHEMA_VERSION:
            return f"schema_version must be {SCHEMA_VERSION}"
        for field in ("peer_id", "key_id"):
            value = envelope.get(field)
            if not isinstance(value, str) or not value.strip():
                return f"{field} must be a non-empty string"
        timestamp = envelope.get("timestamp")
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            return "timestamp must be a number"
        if not math.isfinite(float(timestamp)):
            return "timestamp must be finite"
        try:
            nonce = envelope.get("nonce")
            if isinstance(nonce, str):
                _require_nonce_value(nonce, "nonce")
            else:
                return "nonce must be a hex string"
        except SignedHeartbeatError as exc:
            return str(exc)
        try:
            _validate_metrics(envelope.get("metrics"))
        except SignedHeartbeatError as exc:
            return str(exc)
        signature = envelope.get(SIGNATURE_FIELD)
        if not isinstance(signature, str) or len(signature) != _SIGNATURE_HEX_LENGTH:
            return f"{SIGNATURE_FIELD} must be {_SIGNATURE_HEX_LENGTH} hex chars"
        try:
            bytes.fromhex(signature)
        except ValueError:
            return f"{SIGNATURE_FIELD} must be hex"
        return None

    def _prune_seen(self, now: float) -> None:
        cutoff = now - (self._ttl + self._max_future)
        expired = [key for key, at in self._seen.items() if at < cutoff]
        for key in expired:
            del self._seen[key]
        overflow = len(self._seen) - self._max_seen
        if overflow > 0:
            oldest = sorted(self._seen.items(), key=lambda item: item[1])
            for key, _at in oldest[:overflow]:
                del self._seen[key]

    def verify(self, envelope: Mapping[str, Any]) -> HeartbeatVerification:
        """Verify one envelope. Rejected results carry evidence flags."""
        if not isinstance(envelope, Mapping):
            return self._reject("envelope must be a mapping", {})

        shape_error = self._check_shape(envelope)
        if shape_error is not None:
            return self._reject(f"shape: {shape_error}", envelope)

        peer_id = envelope["peer_id"]
        record = self._directory.lookup(peer_id)
        if record is None:
            return self._reject("unknown peer (not in directory)", envelope)
        if not record.active:
            return self._reject(f"peer not trusted: {record.reason}", envelope)

        unsigned = {k: v for k, v in envelope.items() if k != SIGNATURE_FIELD}
        try:
            public_key = bytes.fromhex(record.public_key_hex)
            signature_ok = crypto_receipts.verify_record_signature(
                dict(envelope), public_key
            )
        except Exception:
            signature_ok = False
        if not signature_ok:
            return self._reject("signature check failed", envelope)

        now = float(self._now())
        timestamp = float(envelope["timestamp"])
        age = now - timestamp
        if age < -self._max_future:
            return HeartbeatVerification(
                state=ORIGIN_REJECTED,
                reason=(
                    f"timestamp {timestamp} is in the future beyond "
                    f"max_future_seconds={self._max_future}"
                ),
                peer_id=peer_id,
                timestamp=timestamp,
                nonce=envelope["nonce"],
                signature_checked=True,
            )
        if age > self._ttl:
            return HeartbeatVerification(
                state=ORIGIN_REJECTED,
                reason=f"stale heartbeat: age {age:.3f}s > ttl {self._ttl}s",
                peer_id=peer_id,
                timestamp=timestamp,
                nonce=envelope["nonce"],
                signature_checked=True,
                freshness_checked=True,
            )

        nonce = envelope["nonce"]
        cache_key = (peer_id, nonce)
        if cache_key in self._seen:
            return HeartbeatVerification(
                state=ORIGIN_REJECTED,
                reason=f"replayed nonce {nonce!r}",
                peer_id=peer_id,
                timestamp=timestamp,
                nonce=nonce,
                signature_checked=True,
                freshness_checked=True,
            )
        self._seen[cache_key] = now
        self._prune_seen(now)

        return HeartbeatVerification(
            state=ORIGIN_VERIFIED,
            reason=(
                "Ed25519 signature valid, fresh, nonce first use "
                "(VERIFIED_ORIGIN: origin evidence, no authorization)"
            ),
            peer_id=peer_id,
            timestamp=timestamp,
            nonce=nonce,
            signature_checked=True,
            freshness_checked=True,
            replay_checked=True,
        )
