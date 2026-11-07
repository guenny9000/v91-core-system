"""Ed25519-signed receipts (Issue #47, stage 5 completion).

Requires the 'cryptography' dependency - explicitly approved by Sebastian
('gruen', 2026-11-07) after it was deliberately withheld in PR #56.

Design:
- Receipts are signed with Ed25519 over the canonical JSON of the receipt
  record (sorted keys, no whitespace), excluding the signature field itself.
- Verification is fail-closed and constant-time via the library's own
  verification; a missing, malformed or wrong-key signature is always a
  refusal, never a warning.
- Keys are handled as raw 32-byte values; callers are responsible for
  storing private keys in the existing Secret Store (v99/security) - this
  module never persists keys.
"""
from __future__ import annotations

import json
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

SIGNATURE_FIELD = "receipt_signature"
SIGNATURE_ALGORITHM = "ED25519"


class CryptoReceiptError(ValueError):
    """Raised when the signed-receipt contract is violated."""


def canonical_record_bytes(record: dict[str, Any]) -> bytes:
    """Canonical JSON: sorted keys, no whitespace. Signature field is excluded by the caller."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def generate_signing_keypair() -> tuple[bytes, bytes]:
    """Generate a fresh Ed25519 keypair; returns (private_key_raw32, public_key_raw32)."""
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    return (
        private.private_bytes_raw(),
        public.public_bytes_raw(),
    )


def _load_private(private_key: bytes) -> Ed25519PrivateKey:
    if not isinstance(private_key, bytes) or len(private_key) != 32:
        raise CryptoReceiptError("private signing key must be raw 32 bytes")
    return Ed25519PrivateKey.from_private_bytes(private_key)


def _load_public(public_key: bytes) -> Ed25519PublicKey:
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        raise CryptoReceiptError("public verification key must be raw 32 bytes")
    return Ed25519PublicKey.from_public_bytes(public_key)


def sign_record(record: dict[str, Any], private_key: bytes) -> str:
    """Sign the canonical form of a record (without the signature field) and return hex."""
    if not isinstance(record, dict):
        raise CryptoReceiptError("record must be a dict")
    if SIGNATURE_FIELD in record:
        raise CryptoReceiptError(f"record must not already contain '{SIGNATURE_FIELD}'")
    signing_key = _load_private(private_key)
    signature = signing_key.sign(canonical_record_bytes(record))
    return signature.hex()


def verify_record_signature(record: dict[str, Any], public_key: bytes) -> bool:
    """Verify an embedded Ed25519 signature. Fail-closed: any anomaly is False."""
    if not isinstance(record, dict):
        return False
    signature_hex = record.get(SIGNATURE_FIELD)
    if not isinstance(signature_hex, str) or len(signature_hex) != 128:
        return False
    unsigned = {k: v for k, v in record.items() if k != SIGNATURE_FIELD}
    try:
        verification_key = _load_public(public_key)
        signature = bytes.fromhex(signature_hex)
        verification_key.verify(signature, canonical_record_bytes(unsigned))
    except Exception:
        return False
    return True


def algorithm_name() -> str:
    return SIGNATURE_ALGORITHM
