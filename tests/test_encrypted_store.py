import pytest

from controller.crypto_receipts import generate_signing_keypair, sign_record
from controller.encrypted_store import (
    ENCRYPTION_STATUS,
    EncryptedObjectStore,
    EncryptedStoreError,
    IntegrityError,
)

MASTER = b'm' * 32


@pytest.fixture
def keypair():
    return generate_signing_keypair()


@pytest.fixture
def store(keypair):
    private_key, _ = keypair
    return EncryptedObjectStore(store_id='node-alpha', master_key=MASTER, opt_in=True,
                                signing_key=private_key)


def test_store_is_opt_in_only():
    with pytest.raises(EncryptedStoreError, match='opt-in only'):
        EncryptedObjectStore(store_id='x', master_key=MASTER, opt_in=False)


def test_master_key_length_is_enforced():
    with pytest.raises(EncryptedStoreError, match='32 bytes'):
        EncryptedObjectStore(store_id='x', master_key=b'short', opt_in=True)


def test_store_encrypts_and_signs(store, keypair):
    _, public_key = keypair
    receipt = store.store(b'payload', owner_id='node-beta')
    assert receipt['encryption'] == ENCRYPTION_STATUS
    assert receipt['encryption'] == 'AES-256-GCM'
    assert len(receipt['nonce']) == 24  # 12 bytes hex
    assert len(receipt['receipt_signature']) == 128
    receipt['_verification_key'] = public_key
    assert store.retrieve(receipt) == b'payload'


def test_ciphertext_is_not_plaintext(store):
    receipt = store.store(b'payload', owner_id='node-beta')
    nonce, ciphertext = store._entries[receipt['object_digest']]
    assert b'payload' not in ciphertext


def test_wrong_master_key_cannot_decrypt(keypair):
    private_key, public_key = keypair
    s1 = EncryptedObjectStore(store_id='node-alpha', master_key=MASTER, opt_in=True, signing_key=private_key)
    receipt = s1.store(b'payload', owner_id='node-beta')
    s2 = EncryptedObjectStore(store_id='node-alpha', master_key=b'k' * 32, opt_in=True)
    receipt['_verification_key'] = public_key
    # ciphertext exists only in s1; s2 lacks the object entirely:
    with pytest.raises(IntegrityError, match='not available'):
        s2.retrieve(receipt)


def test_foreign_store_receipt_is_refused(store, keypair):
    private_key, public_key = keypair
    receipt = store.store(b'payload', owner_id='node-beta')
    other = EncryptedObjectStore(store_id='node-gamma', master_key=MASTER, opt_in=True, signing_key=private_key)
    receipt['_verification_key'] = public_key
    with pytest.raises(IntegrityError, match='different store'):
        other.retrieve(receipt)


def test_missing_signature_with_signing_store_is_refused(store, keypair):
    _, public_key = keypair
    receipt = store.store(b'payload', owner_id='node-beta')
    receipt['_verification_key'] = public_key
    del receipt['receipt_signature']
    with pytest.raises(IntegrityError, match="missing 'receipt_signature'"):
        store.retrieve(receipt)


def test_tampered_signature_is_refused(store, keypair):
    _, public_key = keypair
    receipt = store.store(b'payload', owner_id='node-beta')
    receipt['receipt_signature'] = 'f' * 128
    receipt['_verification_key'] = public_key
    with pytest.raises(IntegrityError, match='signature verification failed'):
        store.retrieve(receipt)


def test_tampered_ciphertext_digest_is_refused(store, keypair):
    _, public_key = keypair
    receipt = store.store(b'payload', owner_id='node-beta')
    receipt['ciphertext_digest'] = '0' * 64
    receipt['_verification_key'] = public_key
    # The receipt itself is now tampered, so signature validation fails first.
    with pytest.raises(IntegrityError, match='signature verification failed'):
        store.retrieve(receipt)


def test_corrupted_ciphertext_is_isolated_not_destroyed(store, keypair):
    _, public_key = keypair
    receipt = store.store(b'payload', owner_id='node-beta')
    digest = receipt['object_digest']
    nonce, _ = store._entries[digest]
    store._entries[digest] = (nonce, b'corrupted-ciphertext')
    receipt['_verification_key'] = public_key
    with pytest.raises(IntegrityError):
        store.retrieve(receipt)
    assert store.object_count() == 1  # nothing deleted


def test_availability_is_rechecked_by_decryption(keypair):
    private_key, _ = keypair
    store = EncryptedObjectStore(store_id='node-alpha', master_key=MASTER, opt_in=True, signing_key=private_key)
    receipt = store.store(b'payload', owner_id='node-beta')
    assert store.is_available(receipt['object_digest']) is True
    digest = receipt['object_digest']
    nonce, _ = store._entries[digest]
    store._entries[digest] = (nonce, b'corrupted-ciphertext')
    assert store.is_available(digest) is False


def test_identical_content_is_idempotent(store, keypair):
    r1 = store.store(b'payload', owner_id='node-beta')
    r2 = store.store(b'payload', owner_id='node-beta')
    assert r1['object_digest'] == r2['object_digest']
    assert r1['nonce'] == r2['nonce']  # stored entry reused
    assert store.object_count() == 1


def test_receipt_without_optional_signature_when_no_signing_key():
    s = EncryptedObjectStore(store_id='node-alpha', master_key=MASTER, opt_in=True)
    receipt = s.store(b'payload', owner_id='node-beta')
    assert 'receipt_signature' not in receipt
    assert s.retrieve(receipt) == b'payload'
