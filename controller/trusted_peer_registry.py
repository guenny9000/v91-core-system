"""Fail-closed lookup for independently provisioned V91 peer public keys.

The registry must come from a trusted local/admin-controlled source. Never load
it from the peer offer or from an unauthenticated remote response. This module
does not itself authenticate who provisioned the registry.
"""
from __future__ import annotations

import base64
import binascii
from typing import Any, Mapping


ED25519_PUBLIC_KEY_BYTES = 32


def resolve_trusted_ed25519_key(
    registry: Mapping[str, Any],
    *,
    peer_id: str,
    key_id: str,
) -> bytes | None:
    """Return an active, correctly shaped Ed25519 key; otherwise fail closed."""
    if not isinstance(registry, Mapping):
        return None
    if not isinstance(peer_id, str) or not peer_id.strip():
        return None
    if not isinstance(key_id, str) or not key_id.strip():
        return None

    peers = registry.get("peers")
    if not isinstance(peers, Mapping):
        return None
    peer = peers.get(peer_id)
    if not isinstance(peer, Mapping):
        return None
    keys = peer.get("keys")
    if not isinstance(keys, Mapping):
        return None
    entry = keys.get(key_id)
    if not isinstance(entry, Mapping):
        return None

    # A revoked key is never accepted, even if its signature is mathematically valid.
    if entry.get("status") != "active" or entry.get("algorithm") != "Ed25519":
        return None
    encoded = entry.get("public_key_b64")
    if not isinstance(encoded, str) or not encoded:
        return None
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(raw) != ED25519_PUBLIC_KEY_BYTES:
        return None
    return raw
