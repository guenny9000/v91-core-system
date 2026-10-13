"""V91 cooperative peer handshake and learning-consent policy.

This module only evaluates a declared peer offer. It does not discover hosts,
connect to remote systems, verify cryptographic signatures, execute commands,
or ingest peer data. A trusted caller must supply the result of signature
verification; default behavior is deny.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping


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


def evaluate_peer_offer(
    offer: Mapping[str, Any],
    *,
    signature_verified: bool = False,
    now_epoch: int | None = None,
) -> Decision:
    """Fail-closed evaluation of a peer's voluntary cooperation offer.

    signature_verified must come from a trusted cryptographic verifier, not
    from a field in the peer-supplied offer. now_epoch is injectable for tests;
    ordinary callers use the system clock. If the clock cannot be read, deny.
    """
    reasons: list[str] = []

    if not signature_verified:
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
        else:
            if "CURRENT_TIME_UNAVAILABLE" not in reasons:
                reasons.append("INVALID_CURRENT_TIME")

    if reasons:
        return Decision("DENY", (), tuple(reasons))

    permitted = tuple(sorted(set(requested) & ALLOWED_PUBLIC_CAPABILITIES))
    if not permitted:
        return Decision("DENY", (), ("NO_ALLOWED_CAPABILITY_REQUESTED",))

    return Decision("ALLOW_READ_ONLY", permitted, ("EXPLICIT_CONSENT_AND_POLICY_CHECKS_PASSED",))


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
