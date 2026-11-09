"""Offline, signed ledger checkpoints.

This module provides cryptographic checkpoint creation and verification only.
It does not upload checkpoints, provide trusted time, or implement WORM retention.
Private keys must be provisioned and protected outside this repository.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

DOMAIN = b"V91-LEDGER-CHECKPOINT-v1\x00"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
KEY_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
CHECKPOINT_FIELDS = {
    "schema_version",
    "ledger_id",
    "sequence",
    "head_hash",
    "created_at_utc",
}


class CheckpointError(ValueError):
    """Raised when checkpoint input is malformed or inconsistent."""


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize the restricted checkpoint schema deterministically."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise CheckpointError("checkpoint is not canonically serializable") from exc


def _validate_checkpoint(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    if set(checkpoint) != CHECKPOINT_FIELDS:
        raise CheckpointError("checkpoint fields do not match schema v1")
    if checkpoint["schema_version"] != 1:
        raise CheckpointError("unsupported checkpoint schema version")
    ledger_id = checkpoint["ledger_id"]
    if not isinstance(ledger_id, str) or not ledger_id or len(ledger_id) > 128:
        raise CheckpointError("invalid ledger_id")
    sequence = checkpoint["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise CheckpointError("sequence must be a non-negative integer")
    head_hash = checkpoint["head_hash"]
    if not isinstance(head_hash, str) or not HASH_RE.fullmatch(head_hash):
        raise CheckpointError("head_hash must be a lowercase SHA-256 hex digest")
    created_at = checkpoint["created_at_utc"]
    if not isinstance(created_at, str) or not created_at or len(created_at) > 64:
        raise CheckpointError("invalid created_at_utc")
    # Copy only after exact-field validation; callers cannot mutate signed data later.
    return {
        "schema_version": 1,
        "ledger_id": ledger_id,
        "sequence": sequence,
        "head_hash": head_hash,
        "created_at_utc": created_at,
    }


def checkpoint_message(checkpoint: Mapping[str, Any]) -> bytes:
    """Return the domain-separated bytes covered by the Ed25519 signature."""
    validated = _validate_checkpoint(checkpoint)
    return DOMAIN + _canonical_bytes(validated)


def sign_checkpoint(
    checkpoint: Mapping[str, Any],
    *,
    key_id: str,
    private_key: Ed25519PrivateKey,
) -> dict[str, Any]:
    """Create an independently verifiable Ed25519 checkpoint envelope."""
    if not isinstance(key_id, str) or not KEY_ID_RE.fullmatch(key_id):
        raise CheckpointError("invalid key_id")
    message = checkpoint_message(checkpoint)
    signature = private_key.sign(message)
    return {
        "algorithm": "Ed25519",
        "key_id": key_id,
        "checkpoint": _validate_checkpoint(checkpoint),
        "signature": signature.hex(),
    }


def verify_checkpoint(
    envelope: Mapping[str, Any],
    *,
    trusted_keys: Mapping[str, Ed25519PublicKey],
) -> dict[str, Any]:
    """Verify signature and return an explicit result; never imply WORM status."""
    if set(envelope) != {"algorithm", "key_id", "checkpoint", "signature"}:
        raise CheckpointError("checkpoint envelope fields do not match schema")
    if envelope["algorithm"] != "Ed25519":
        raise CheckpointError("unsupported signature algorithm")
    key_id = envelope["key_id"]
    if not isinstance(key_id, str) or not KEY_ID_RE.fullmatch(key_id):
        raise CheckpointError("invalid key_id")
    public_key = trusted_keys.get(key_id)
    if public_key is None:
        return {"status": "UNKNOWN_KEY", "key_id": key_id}
    signature_hex = envelope["signature"]
    if not isinstance(signature_hex, str) or not re.fullmatch(r"[0-9a-f]{128}", signature_hex):
        raise CheckpointError("signature must be 64-byte lowercase hex")
    checkpoint = _validate_checkpoint(envelope["checkpoint"])
    try:
        public_key.verify(bytes.fromhex(signature_hex), checkpoint_message(checkpoint))
    except InvalidSignature:
        return {"status": "SIGNATURE_INVALID", "key_id": key_id}
    return {
        "status": "SIGNATURE_VALID",
        "key_id": key_id,
        "checkpoint": checkpoint,
    }


def compare_local_head(
    verified_checkpoint: Mapping[str, Any],
    *,
    ledger_id: str,
    sequence: int,
    head_hash: str,
) -> dict[str, str]:
    """Compare a verified checkpoint with a local head; detects rollback/divergence."""
    if verified_checkpoint.get("status") != "SIGNATURE_VALID":
        return {"status": "ANCHOR_NOT_VERIFIED"}
    checkpoint = verified_checkpoint["checkpoint"]
    if checkpoint["ledger_id"] != ledger_id:
        return {"status": "LEDGER_ID_MISMATCH"}
    if sequence < checkpoint["sequence"]:
        return {"status": "ROLLBACK_DETECTED"}
    if sequence == checkpoint["sequence"] and head_hash != checkpoint["head_hash"]:
        return {"status": "HEAD_DIVERGENCE"}
    if sequence > checkpoint["sequence"]:
        return {"status": "LOCAL_AHEAD_OF_CHECKPOINT"}
    return {"status": "CHECKPOINT_MATCH"}
