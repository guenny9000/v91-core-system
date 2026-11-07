"""Encrypted opt-in peer object storage: AES-256-GCM + Ed25519 receipts.

Issue #47, stage 5 completion. Requires 'cryptography' - explicitly
approved by Sebastian ('gruen', 2026-11-07).

Properties:
- Opt-in only (like controller/peer_store.py): no store without a
  conscious opt_in=True. No silent data upload.
- Objects are encrypted with AES-256-GCM (12-byte random nonce, store_id
  as additional authenticated data). The ciphertext is stored; the receipt
  carries the PLAINTEXT digest for content addressing.
- Receipts are Ed25519-signed over the canonical record (see
  controller/crypto_receipts.py). Retrieval verifies the signature, the
  GCM tag and the plaintext digest - fail-closed on any anomaly.
- ISOLATE_NOT_DESTROY: verification failures raise; nothing is deleted,
  overwritten or 'repaired'.
- Availability is rechecked (decrypt + rehash), never assumed.

Honest limits:
- The master key must come from the Secret Store (v99/security); this
  module never persists keys and never claims key management.
- In-memory implementation; durable/networked storage remains a later stage.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from controller.crypto_receipts import (
    SIGNATURE_FIELD,
    sign_record,
    verify_record_signature,
)

ENCRYPTION_STATUS = "AES-256-GCM"


class EncryptedStoreError(ValueError):
    """Raised when the encrypted-store contract is violated."""


class IntegrityError(EncryptedStoreError):
    """Raised when stored content fails verification; nothing is deleted."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class EncryptedObjectStore:
    """Opt-in encrypted content-addressed object store with signed receipts."""

    def __init__(self, *, store_id: str, master_key: bytes, opt_in: bool = False,
                 signing_key: Optional[bytes] = None) -> None:
        if opt_in is not True:
            raise EncryptedStoreError("encrypted peer storage is opt-in only; construct with opt_in=True after a conscious decision")
        if not isinstance(store_id, str) or not store_id.strip():
            raise EncryptedStoreError("store_id must be a non-empty string")
        if not isinstance(master_key, bytes) or len(master_key) != 32:
            raise EncryptedStoreError("master_key must be exactly 32 bytes (AES-256)")
        self._store_id = store_id
        self._aesgcm = AESGCM(master_key)
        self._signing_key = signing_key
        self._entries: dict[str, tuple[bytes, bytes]] = {}  # plaintext_digest -> (nonce, ciphertext)

    def store(self, data: bytes, *, owner_id: str) -> dict[str, Any]:
        """Encrypt and store one object; return an Ed25519-signed receipt."""
        if not isinstance(data, bytes):
            raise EncryptedStoreError("object data must be bytes")
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise EncryptedStoreError("owner_id must be a non-empty string")
        digest = _sha256(data)
        entry = self._entries.get(digest)
        if entry is None:
            nonce = os.urandom(12)
            ciphertext = self._aesgcm.encrypt(nonce, data, self._store_id.encode("utf-8"))
            entry = (nonce, ciphertext)
            self._entries[digest] = entry
        receipt: dict[str, Any] = {
            "object_digest": digest,
            "owner_id": owner_id,
            "store_id": self._store_id,
            "algorithm": "ED25519",
            "encryption": ENCRYPTION_STATUS,
            "nonce": entry[0].hex(),
            "ciphertext_digest": _sha256(entry[1]),
        }
        if self._signing_key is not None:
            receipt[SIGNATURE_FIELD] = sign_record(receipt, self._signing_key)
        return receipt

    def is_available(self, object_digest: str) -> bool:
        """Availability is rechecked (decrypt + rehash), never assumed."""
        entry = self._entries.get(object_digest)
        if entry is None:
            return False
        nonce, ciphertext = entry
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, self._store_id.encode("utf-8"))
        except InvalidTag:
            return False
        return _sha256(plaintext) == object_digest

    def retrieve(self, receipt: dict[str, Any]) -> bytes:
        """Verify signature and ciphertext, decrypt, and rehash the plaintext."""
        if not isinstance(receipt, dict):
            raise IntegrityError("receipt must be a dict")
        for key in ("object_digest", "owner_id", "store_id", "encryption", "nonce", "ciphertext_digest"):
            if key not in receipt:
                raise IntegrityError(f"receipt is missing '{key}'")
        if receipt["store_id"] != self._store_id:
            raise IntegrityError("receipt was issued by a different store")
        if receipt["encryption"] != ENCRYPTION_STATUS:
            raise IntegrityError(f"unsupported encryption status: {receipt['encryption']!r}")

        if self._signing_key is not None and SIGNATURE_FIELD not in receipt:
            raise IntegrityError(f"receipt is missing '{SIGNATURE_FIELD}'")
        if SIGNATURE_FIELD in receipt:
            verification_key = _public_key_for(receipt)
            # The raw verification key is transport metadata, not part of the
            # signed receipt. Remove it before canonical signature verification.
            signed_receipt = {key: value for key, value in receipt.items() if key != "_verification_key"}
            if not verify_record_signature(signed_receipt, verification_key):
                raise IntegrityError("receipt signature verification failed (fail-closed)")

        digest = receipt["object_digest"]
        entry = self._entries.get(digest)
        if entry is None:
            raise IntegrityError(f"object {digest} is not available in this store")
        nonce, ciphertext = entry
        if _sha256(ciphertext) != receipt["ciphertext_digest"]:
            raise IntegrityError(f"ciphertext digest mismatch for {digest}; refusing to decrypt (ISOLATE_NOT_DESTROY)")
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, self._store_id.encode("utf-8"))
        except InvalidTag:
            raise IntegrityError(f"decryption failed for {digest}; refusing to return anything (ISOLATE_NOT_DESTROY)")
        if _sha256(plaintext) != digest:
            raise IntegrityError(f"plaintext digest mismatch for {digest}; refusing to return it (ISOLATE_NOT_DESTROY)")
        return plaintext

    def object_count(self) -> int:
        return len(self._entries)


def _public_key_for(receipt: dict[str, Any]) -> bytes:
    """Read the verifier's public key supplied alongside the receipt.

    'verification_key_hex' is an explicit receipt field; '_verification_key'
    is an out-of-band raw-byte value and is stripped before signature checking.
    The private signing key remains with the owner.
    """
    key = receipt.get("_verification_key")
    if isinstance(key, bytes) and len(key) == 32:
        return key
    hex_key = receipt.get("verification_key_hex")
    if isinstance(hex_key, str) and len(hex_key) == 64:
        try:
            return bytes.fromhex(hex_key)
        except ValueError as exc:
            raise IntegrityError("invalid Ed25519 verification key encoding") from exc
    raise IntegrityError("no Ed25519 verification key supplied with the receipt")
