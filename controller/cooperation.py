""""V91 cooperative peer handshake and learning-consent policy.

This module evaluates a declared peer offer. It does not discover hosts,
connect to remote systems, execute commands, or ingest peer data. The
high-level signed-offer path verifies Ed25519 over the canonical JSON encoding
of the complete offer before applying the fail-closed policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519


PROTOCOL_VERSION = "v1"
ALLOWED_PUBLIC_CAPABILITIES = frozenset({"describe", "share_public_metadata"})
FORBIDDEN_CAPABILITIES = frozenset(
    {"execute", "write", "admin", "install", "control", "read_private_data"}
)


@dataclass(frozen=True)
class Decision:
    status: str
    allowed_capabilities: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def allowed(self) -> bool:
        return self.status == "ALLOW_READ_ONLY"


def canonical_offer_bytes(offer: Mapping[str, Any]) -> bytes | None:
    """Serialize the exact offer deterministically for signature verification."""
    try:
        return json.dumps(
            dict(offer),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        return None


def verify_ed25519_signature(
    public_key_bytes: bytes, message_bytes: bytes, signature_bytes: bytes
) -> bool:
    """Return True only for a valid Ed25519 signature; malformed input denies."""
    if not all(isinstance(value, bytes) for value in (public_key_bytes, message_bytes, signature_bytes)):
        return False
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature_bytes, message_bytes)
        return True
    except (InvalidSignature, TypeError, ValueError):
        return False
    except Exception:
        # Fail closed if the cryptographic backend raises an unexpected error.
        return False


def evaluate_peer_offer(
    offer: Mapping[str, Any],
    *,
    signature_verified: bool = False,
    now_epoch: int | None = None,
) -> Decision:
    """Fail-closed evaluation of a peer's voluntary cooperation offer.

    signature_verified is intended only for callers that have already used a
    trusted cryptographic verifier. Prefer evaluate_signed_peer_offer at
    external trust boundaries; never read this value from the peer's offer.
    """
    reasons: list[str] = []

    if signature_verified is not True:
        reasons.append("PEER_SIGNATURE_NOT_VERIFIED")
    if offer.get("protocol_version") != PROTOCOL_VERSION:
        reasons.append("UNSUPPORTED_PROTOCOL_VERSION")
    if not isinstance(offer.get("peer_id"), str) or not offer.get("peer_id", "").strip():
        reasons.append("MISSING_PEER_ID")
    if offer.get("consent") is not True:
        reasons.append("EXPLICIT_CONSENT_MISSING")
    if offer.get("share_public_metadata") is not True:
        reasons.append("PUBLIC_METADATA_SHARING_NOT_APPROVED")

    requested = offer.get("requested_capabilities")
    if not isinstance(requested, list) or any(not isinstance(x, str) for x in requested):
        reasons.append("INVALID_CAPABILITY_LIST")
        requested = []

    forbidden = sorted(set(requested) & FORBIDDEN_CAPABILITIES)
    if forbidden:
        reasons.append("FORBIDDEN_CAPABILITIES_REQUESTED:" + ",".join(forbidden))

    unknown = sorted(set(requested) - ALLOWED_PUBLIC_CAPABILITIES - FORBIDDEN_CAPABILITIES)
    if unknown:
        reasons.append("UNKNOWN_CAPABILITIES_REQUESTED:" + ",".join(unknown))

    expires_at = offer.get("expires_at")
    if not isinstance(expires_at, int) or isinstance(expires_at, bool):
        reasons.append("INVALID_EXPIRY")

    if now_epoch is None:
        try:
            now_epoch = int(time.time())
        except (OSError, OverflowError, ValueError):
            reasons.append("CURRENT_TIME_UNAVAILABLE")
    elif not isinstance(now_epoch, int) or isinstance(now_epoch, bool):
        reasons.append("INVALID_CURRENT_TIME")

    if isinstance(expires_at, int) and not isinstance(expires_at, bool):
        if isinstance(now_epoch, int) and not isinstance(now_epoch, bool):
            if expires_at <= now_epoch:
                reasons.append("OFFER_EXPIRED")
        elif "CURRENT_TIME_UNAVAILABLE" not in reasons:
            reasons.append("INVALID_CURRENT_TIME")

    if reasons:
        return Decision("DENY", (), tuple(reasons))

    permitted = tuple(sorted(set(requested) & ALLOWED_PUBLIC_CAPABILITIES))
    if not permitted:
        return Decision("DENY", (), ("NO_ALLOWED_CAPABILITY_REQUESTED",))

    return Decision("ALLOW_READ_ONLY", permitted, ("EXPLICIT_CONSENT_AND_POLICY_CHECKS_PASSED",))


def evaluate_signed_peer_offer(
    offer: Mapping[str, Any],
    *,
    public_key_bytes: bytes,
    signature_bytes: bytes,
    now_epoch: int | None = None,
) -> Decision:
    """Verify a peer's Ed25519 signature over canonical offer JSON, then evaluate it."""
    message = canonical_offer_bytes(offer)
    verified = message is not None and verify_ed25519_signature(
        public_key_bytes, message, signature_bytes
    )
    return evaluate_peer_offer(offer, signature_verified=verified, now_epoch=now_epoch)


def public_decision_record(offer: Mapping[str, Any], decision: Decision) -> dict[str, Any]:
    """Create a minimal audit record; never copy peer payloads or private data."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "peer_id": offer.get("peer_id") if isinstance(offer.get("peer_id"), str) else None,
        "status": decision.status,
        "allowed_capabilities": list(decision.allowed_capabilities),
        "reasons": list(decision.reasons),
        "data_ingested": False,
        "remote_actions_executed": False,
    }
