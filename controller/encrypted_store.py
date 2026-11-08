"""Encrypted opt-in peer object storage: AES-256-GCM + Ed25519 receipts.

Signed receipts are verified against an independently trusted public key
supplied by the caller. Receipt-carried keys are never trusted. Authentication
precedes object lookup and ciphertext checks. The in-memory store is opt-in;
durable/networked storage remains a later stage.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from controller.crypto_receipts import (
    SIGNATURE_ALGORITHM,
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
        if signing_key is not None and (not isinstance(signing_key, bytes) or len(signing_key) != 32):
            raise EncryptedStoreError("signing_key must be raw 32-byte Ed25519 private key")
        self._store_id = store_id
        self._aesgcm = AESGCM(master_key)
        self._signing_key = signing_key
        self._entries: dict[str, tuple[bytes, bytes]] = {}

    def store(self, data: bytes, *, owner_id: str) -> dict[str, Any]:
        """Encrypt and store one object; return an Ed25519-signed receipt if configured."""
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
            "algorithm": SIGNATURE_ALGORITHM,
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

    def retrieve(self, receipt: dict[str, Any], *, trusted_public_key: Optional[bytes] = None) -> bytes:
        """Authenticate receipt before lookup, then verify ciphertext and plaintext."""
        if not isinstance(receipt, dict):
            raise IntegrityError("receipt must be a dict")
        required = (
            "object_digest", "owner_id", "store_id", "algorithm",
            "encryption", "nonce", "ciphertext_digest",
        )
        for key in required:
            if key not in receipt:
                raise IntegrityError(f"receipt is missing '{key}'")

        signature_present = SIGNATURE_FIELD in receipt
        if self._signing_key is not None and not signature_present:
            raise IntegrityError(f"receipt is missing '{SIGNATURE_FIELD}' (this store signs receipts; fail-closed)")
        if signature_present:
            if receipt["algorithm"] != SIGNATURE_ALGORITHM:
                raise IntegrityError("unsupported receipt signature algorithm")
            if not isinstance(trusted_public_key, bytes) or len(trusted_public_key) != 32:
                raise IntegrityError("an independently trusted 32-byte Ed25519 public key is required")
            if not verify_record_signature(receipt, trusted_public_key):
                raise IntegrityError("receipt signature verification failed (fail-closed)")
        elif trusted_public_key is not None:
            raise IntegrityError("trusted public key supplied for an unsigned receipt")

        # Do not disclose store/object existence or ciphertext state until the
        # receipt signature and independently trusted key have been checked.
        if receipt["store_id"] != self._store_id:
            raise IntegrityError("receipt was issued by a different store")
        if receipt["encryption"] != ENCRYPTION_STATUS:
            raise IntegrityError(f"unsupported encryption status: {receipt['encryption']!r}")

        digest = receipt["object_digest"]
        if not isinstance(digest, str) or len(digest) != 64:
            raise IntegrityError("receipt object_digest must be a 64-character SHA-256 hex digest")
        try:
            bytes.fromhex(digest)
            nonce_from_receipt = bytes.fromhex(receipt["nonce"])
        except (TypeError, ValueError) as exc:
            raise IntegrityError("receipt digest or nonce encoding is invalid") from exc
        if len(nonce_from_receipt) != 12:
            raise IntegrityError("receipt nonce must be exactly 12 bytes")

        entry = self._entries.get(digest)
        if entry is None:
            raise IntegrityError(f"object {digest} is not available in this store")
        nonce, ciphertext = entry
        if nonce != nonce_from_receipt:
            raise IntegrityError(f"receipt nonce mismatch for {digest}; refusing to decrypt (ISOLATE_NOT_DESTROY)")
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
