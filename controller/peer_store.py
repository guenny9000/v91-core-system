"""Opt-in, content-addressed peer object storage with HMAC-signed receipts.

Issue #47, stage 5 (stdlib part). Explicit, opt-in only: no store exists
until a participant consciously constructs one with opt_in=True. There is
no silent data upload anywhere in this module.

What is real here:
- Content addressing: every object is stored and retrievable by its SHA-256
  digest; retrieval re-verifies the content hash (availability and
  integrity are RECHECKED, never assumed).
- Receipts: HMAC-SHA256 over a canonical receipt record using a shared
  secret. Receipt verification is fail-closed: wrong HMAC, wrong digest,
  corrupted or missing object -> retrieval refuses.
- ISOLATE_NOT_DESTROY: verification failures raise; nothing is deleted,
  overwritten or 'repaired' automatically.

What is honestly NOT here:
- Encryption. The Python standard library provides no vetted symmetric
  cipher, and rolling a homemade cipher is categorically rejected here.
  Real object encryption requires the 'cryptography' dependency - that
  decision is deliberately reserved for Sebastian. Until then, receipts
  state 'encryption': 'NOT_IMPLEMENTED_STDLIB_GAP' explicitly, and no
  encrypted-storage claim is ever made.
- Asymmetric signatures (Ed25519) likewise require 'cryptography'.
- This is an in-memory implementation; durable/networked storage is a
  later stage.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

RECEIPT_ALGORITHM = "HMAC-SHA256"
ENCRYPTION_STATUS = "NOT_IMPLEMENTED_STDLIB_GAP"


class PeerStoreError(ValueError):
    """Raised when the peer-store contract is violated."""


class IntegrityError(PeerStoreError):
    """Raised when stored content fails verification; nothing is deleted."""


class ReceiptValidationError(PeerStoreError):
    """Raised when a receipt fails HMAC or digest validation (fail-closed)."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_receipt_bytes(record: dict[str, Any]) -> bytes:
    parts = [
        record["object_digest"],
        record["owner_id"],
        record["store_id"],
        record["algorithm"],
        record["encryption"],
    ]
    return "|".join(parts).encode("utf-8")


class PeerObjectStore:
    """Opt-in content-addressed object store with HMAC-signed receipts."""

    def __init__(self, *, store_id: str, shared_secret: bytes, opt_in: bool = False) -> None:
        if opt_in is not True:
            raise PeerStoreError("peer storage is opt-in only; construct with opt_in=True after a conscious decision")
        if not isinstance(store_id, str) or not store_id.strip():
            raise PeerStoreError("store_id must be a non-empty string")
        if not isinstance(shared_secret, bytes) or len(shared_secret) < 32:
            raise PeerStoreError("shared_secret must be at least 32 bytes of high-entropy key material")
        self._store_id = store_id
        self._secret = shared_secret
        self._objects: dict[str, bytes] = {}

    @property
    def store_id(self) -> str:
        return self._store_id

    def store(self, data: bytes, *, owner_id: str) -> dict[str, Any]:
        """Store one object under its SHA-256 digest and return a signed receipt.

        Storing the same bytes twice is idempotent (same digest), and an
        existing digest is NEVER overwritten with different content because
        content addressing makes that impossible by construction.
        """
        if not isinstance(data, bytes):
            raise PeerStoreError("object data must be bytes")
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise PeerStoreError("owner_id must be a non-empty string")
        digest = _sha256(data)
        existing = self._objects.get(digest)
        if existing is not None and existing != data:
            raise IntegrityError(f"digest collision for {digest}: refusing to overwrite (ISOLATE_NOT_DESTROY)")
        self._objects[digest] = data
        receipt = {
            "object_digest": digest,
            "owner_id": owner_id,
            "store_id": self._store_id,
            "algorithm": RECEIPT_ALGORITHM,
            "encryption": ENCRYPTION_STATUS,
        }
        receipt["receipt_mac"] = hmac.new(self._secret, _canonical_receipt_bytes(receipt), hashlib.sha256).hexdigest()
        return dict(receipt)

    def is_available(self, object_digest: str) -> bool:
        """Availability is rechecked (content re-hashed), never assumed."""
        data = self._objects.get(object_digest)
        if data is None:
            return False
        return hmac.compare_digest(_sha256(data), object_digest)

    def retrieve(self, receipt: dict[str, Any]) -> bytes:
        """Verify the receipt and the stored content, then return the object (fail-closed)."""
        if not isinstance(receipt, dict):
            raise ReceiptValidationError("receipt must be a dict")
        for key in ("object_digest", "owner_id", "store_id", "algorithm", "encryption", "receipt_mac"):
            if key not in receipt:
                raise ReceiptValidationError(f"receipt is missing '{key}'")
        if receipt["store_id"] != self._store_id:
            raise ReceiptValidationError("receipt was issued by a different store")
        if receipt["algorithm"] != RECEIPT_ALGORITHM:
            raise ReceiptValidationError(f"unsupported receipt algorithm: {receipt['algorithm']!r}")
        expected = hmac.new(self._secret, _canonical_receipt_bytes(receipt), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(receipt["receipt_mac"])):
            raise ReceiptValidationError("receipt HMAC mismatch (fail-closed)")
        digest = receipt["object_digest"]
        data = self._objects.get(digest)
        if data is None:
            raise ReceiptValidationError(f"object {digest} is not available in this store")
        if not hmac.compare_digest(_sha256(data), digest):
            raise IntegrityError(f"object {digest} failed content verification; refusing to return it (ISOLATE_NOT_DESTROY)")
        return data

    def object_count(self) -> int:
        return len(self._objects)
