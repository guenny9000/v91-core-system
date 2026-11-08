import pytest

from controller.crypto_receipts import SIGNATURE_FIELD, generate_signing_keypair, sign_record
from controller.encrypted_store import (
    ENCRYPTION_STATUS,
    EncryptedObjectStore,
    EncryptedStoreError,
    IntegrityError,
)

MASTER = b"m" * 32


@pytest.fixture
def keypair():
    return generate_signing_keypair()


@pytest.fixture
def store(keypair):
    private_key, _ = keypair
    return EncryptedObjectStore(store_id="node-alpha", master_key=MASTER, opt_in=True,
                                signing_key=private_key)


def _resign(receipt, private_key):
    unsigned = {key: value for key, value in receipt.items() if key != SIGNATURE_FIELD}
    receipt[SIGNATURE_FIELD] = sign_record(unsigned, private_key)


def test_store_is_opt_in_only():
    with pytest.raises(EncryptedStoreError, match="opt-in only"):
        EncryptedObjectStore(store_id="x", master_key=MASTER, opt_in=False)


def test_master_key_length_is_enforced():
    with pytest.raises(EncryptedStoreError, match="32 bytes"):
        EncryptedObjectStore(store_id="x", master_key=b"short", opt_in=True)


def test_store_encrypts_and_signs(store, keypair):
    _, public_key = keypair
    receipt = store.store(b"payload", owner_id="node-beta")
    assert receipt["encryption"] == ENCRYPTION_STATUS == "AES-256-GCM"
    assert len(receipt["nonce"]) == 24
    assert len(receipt[SIGNATURE_FIELD]) == 128
    assert "_verification_key" not in receipt
    assert "verification_key_hex" not in receipt
    assert store.retrieve(receipt, trusted_public_key=public_key) == b"payload"


def test_signed_receipt_requires_independently_trusted_key(store):
    receipt = store.store(b"payload", owner_id="node-beta")
    with pytest.raises(IntegrityError, match="independently trusted"):
        store.retrieve(receipt)


def test_self_signed_foreign_key_is_refused(store, keypair):
    _, trusted_public_key = keypair
    attacker_private, _ = generate_signing_keypair()
    receipt = store.store(b"payload", owner_id="node-beta")
    _resign(receipt, attacker_private)
    with pytest.raises(IntegrityError, match="signature verification failed"):
        store.retrieve(receipt, trusted_public_key=trusted_public_key)


def test_wrong_trusted_key_is_refused(store):
    _, attacker_public_key = generate_signing_keypair()
    receipt = store.store(b"payload", owner_id="node-beta")
    with pytest.raises(IntegrityError, match="signature verification failed"):
        store.retrieve(receipt, trusted_public_key=attacker_public_key)


def test_unexpected_transport_field_is_covered_by_signature(store, keypair):
    _, public_key = keypair
    receipt = store.store(b"payload", owner_id="node-beta")
    receipt["_untrusted_transport_metadata"] = "attacker-controlled"
    with pytest.raises(IntegrityError, match="signature verification failed"):
        store.retrieve(receipt, trusted_public_key=public_key)


def test_wrong_master_key_cannot_decrypt(keypair):
    private_key, public_key = keypair
    s1 = EncryptedObjectStore(store_id="node-alpha", master_key=MASTER, opt_in=True, signing_key=private_key)
    receipt = s1.store(b"payload", owner_id="node-beta")
    s2 = EncryptedObjectStore(store_id="node-alpha", master_key=b"k" * 32, opt_in=True)
    with pytest.raises(IntegrityError, match="not available"):
        s2.retrieve(receipt, trusted_public_key=public_key)


def test_foreign_store_receipt_is_refused(store, keypair):
    private_key, public_key = keypair
    receipt = store.store(b"payload", owner_id="node-beta")
    other = EncryptedObjectStore(store_id="node-gamma", master_key=MASTER, opt_in=True, signing_key=private_key)
    with pytest.raises(IntegrityError, match="different store"):
        other.retrieve(receipt, trusted_public_key=public_key)


def test_missing_signature_with_signing_store_is_refused(store, keypair):
    _, public_key = keypair
    receipt = store.store(b"payload", owner_id="node-beta")
    del receipt[SIGNATURE_FIELD]
    with pytest.raises(IntegrityError, match="missing"):
        store.retrieve(receipt, trusted_public_key=public_key)


def test_tampered_signature_is_refused(store, keypair):
    _, public_key = keypair
    receipt = store.store(b"payload", owner_id="node-beta")
    receipt[SIGNATURE_FIELD] = "f" * 128
    with pytest.raises(IntegrityError, match="signature verification failed"):
        store.retrieve(receipt, trusted_public_key=public_key)


def test_tampered_ciphertext_digest_is_refused(store, keypair):
    private_key, public_key = keypair
    receipt = store.store(b"payload", owner_id="node-beta")
    receipt["ciphertext_digest"] = "0" * 64
    _resign(receipt, private_key)
    with pytest.raises(IntegrityError, match="ciphertext digest mismatch"):
        store.retrieve(receipt, trusted_public_key=public_key)


def test_corrupted_ciphertext_is_isolated_not_destroyed(store, keypair):
    _, public_key = keypair
    receipt = store.store(b"payload", owner_id="node-beta")
    digest = receipt["object_digest"]
    nonce, _ = store._entries[digest]
    store._entries[digest] = (nonce, b"corrupted-ciphertext")
    with pytest.raises(IntegrityError, match="ciphertext digest mismatch"):
        store.retrieve(receipt, trusted_public_key=public_key)
    assert store.object_count() == 1


def test_availability_is_rechecked_by_decryption(keypair):
    private_key, _ = keypair
    store = EncryptedObjectStore(store_id="node-alpha", master_key=MASTER, opt_in=True, signing_key=private_key)
    receipt = store.store(b"payload", owner_id="node-beta")
    assert store.is_available(receipt["object_digest"]) is True
    digest = receipt["object_digest"]
    nonce, _ = store._entries[digest]
    store._entries[digest] = (nonce, b"corrupted-ciphertext")
    assert store.is_available(digest) is False


def test_identical_content_is_idempotent(store, keypair):
    _, public_key = keypair
    r1 = store.store(b"payload", owner_id="node-beta")
    r2 = store.store(b"payload", owner_id="node-beta")
    assert r1["object_digest"] == r2["object_digest"]
    assert r1["nonce"] == r2["nonce"]
    assert store.object_count() == 1
    assert store.retrieve(r1, trusted_public_key=public_key) == b"payload"


def test_unsigned_receipt_is_allowed_only_without_signing_configuration():
    store = EncryptedObjectStore(store_id="node-alpha", master_key=MASTER, opt_in=True)
    receipt = store.store(b"payload", owner_id="node-beta")
    assert SIGNATURE_FIELD not in receipt
    assert store.retrieve(receipt) == b"payload"


def test_unsigned_receipt_cannot_claim_trusted_key():
    store = EncryptedObjectStore(store_id="node-alpha", master_key=MASTER, opt_in=True)
    receipt = store.store(b"payload", owner_id="node-beta")
    _, public_key = generate_signing_keypair()
    with pytest.raises(IntegrityError, match="unsigned receipt"):
        store.retrieve(receipt, trusted_public_key=public_key)
