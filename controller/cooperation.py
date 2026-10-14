"""V91 cooperative peer handshake and learning-consent policy.

External callers may use evaluate_signed_peer_offer() only after loading the
public key from an independently trusted peer-to-key mapping. The function
verifies Ed25519 over canonical JSON before evaluating consent and capability
policy, but it does not bind peer_id to the supplied key or establish trust in a
self-supplied key. The policy-only helper is not a safe external entry point.
This module does not discover hosts, connect remotely, execute commands, or
ingest peer data.
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
        return False


def _evaluate_peer_offer_policy(
    offer: Mapping[str, Any],
    *,
    signature_verified: bool,
    now_epoch: int | None = None,
) -> Decision:
    """Internal policy evaluator; only trusted verification code may set True."""
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


def evaluate_peer_offer(
    offer: Mapping[str, Any], *, now_epoch: int | None = None
) -> Decision:
    """Safe public policy entry point without signature evidence: always deny."""
    return _evaluate_peer_offer_policy(
        offer, signature_verified=False, now_epoch=now_epoch
    )


def evaluate_signed_peer_offer(
    offer: Mapping[str, Any],
    *,
    public_key_bytes: bytes,
    signature_bytes: bytes,
    now_epoch: int | None = None,
) -> Decision:
    """Verify canonical offer JSON, then evaluate policy.

    Important: public_key_bytes must come from a trusted source independent of
    the offer. A key supplied by the peer proves only possession of that key;
    it does not authenticate the claimed peer_id or establish key trust.
    """
    message = canonical_offer_bytes(offer)
    verified = message is not None and verify_ed25519_signature(
        public_key_bytes, message, signature_bytes
    )
    return _evaluate_peer_offer_policy(
        offer, signature_verified=verified, now_epoch=now_epoch
    )


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
