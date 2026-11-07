import hashlib

import pytest

from controller.peer_store import (
    ENCRYPTION_STATUS,
    IntegrityError,
    PeerObjectStore,
    PeerStoreError,
    ReceiptValidationError,
)

SECRET = b'x' * 32


def make_store(**overrides):
    values = {'store_id': 'node-alpha', 'shared_secret': SECRET, 'opt_in': True}
    values.update(overrides)
    return PeerObjectStore(**values)


def test_store_is_opt_in_only():
    with pytest.raises(PeerStoreError, match='opt-in only'):
        make_store(opt_in=False)


def test_weak_secret_is_refused():
    with pytest.raises(PeerStoreError, match='32 bytes'):
        make_store(shared_secret=b'short')


def test_store_returns_signed_content_addressed_receipt():
    store = make_store()
    receipt = store.store(b'payload', owner_id='node-beta')
    assert receipt['object_digest'] == hashlib.sha256(b'payload').hexdigest()
    assert receipt['algorithm'] == 'HMAC-SHA256'
    assert len(receipt['receipt_mac']) == 64


def test_receipt_states_encryption_gap_honestly():
    receipt = make_store().store(b'payload', owner_id='node-beta')
    assert receipt['encryption'] == ENCRYPTION_STATUS
    assert ENCRYPTION_STATUS.startswith('NOT_IMPLEMENTED')


def test_retrieve_roundtrip_with_valid_receipt():
    store = make_store()
    receipt = store.store(b'payload', owner_id='node-beta')
    assert store.retrieve(receipt) == b'payload'


def test_retrieve_rejects_foreign_store_receipt():
    store = make_store()
    receipt = store.store(b'payload', owner_id='node-beta')
    other = make_store(store_id='node-gamma')
    with pytest.raises(ReceiptValidationError, match='different store'):
        other.retrieve(receipt)


def test_retrieve_rejects_tampered_mac():
    store = make_store()
    receipt = store.store(b'payload', owner_id='node-beta')
    receipt['receipt_mac'] = 'f' * 64
    with pytest.raises(ReceiptValidationError, match='HMAC mismatch'):
        store.retrieve(receipt)


def test_retrieve_rejects_tampered_owner():
    store = make_store()
    receipt = store.store(b'payload', owner_id='node-beta')
    receipt['owner_id'] = 'node-evil'
    with pytest.raises(ReceiptValidationError):
        store.retrieve(receipt)


def test_retrieve_rejects_missing_keys():
    store = make_store()
    receipt = store.store(b'payload', owner_id='node-beta')
    del receipt['receipt_mac']
    with pytest.raises(ReceiptValidationError, match='receipt_mac'):
        store.retrieve(receipt)


def test_availability_is_rechecked_not_assumed():
    store = make_store()
    receipt = store.store(b'payload', owner_id='node-beta')
    digest = receipt['object_digest']
    assert store.is_available(digest) is True
    store._objects[digest] = b'corrupted'
    assert store.is_available(digest) is False
    with pytest.raises(IntegrityError, match='ISOLATE_NOT_DESTROY'):
        store.retrieve(receipt)


def test_corrupted_object_is_not_deleted():
    store = make_store()
    receipt = store.store(b'payload', owner_id='node-beta')
    digest = receipt['object_digest']
    store._objects[digest] = b'corrupted'
    with pytest.raises(IntegrityError):
        store.retrieve(receipt)
    assert store.object_count() == 1  # ISOLATE_NOT_DESTROY


def test_identical_content_is_idempotent():
    store = make_store()
    r1 = store.store(b'payload', owner_id='node-beta')
    r2 = store.store(b'payload', owner_id='node-beta')
    assert r1['object_digest'] == r2['object_digest']
    assert store.object_count() == 1


def test_missing_object_is_reported_not_assumed():
    store = make_store()
    receipt = {'object_digest': 'a' * 64, 'owner_id': 'x', 'store_id': 'node-alpha',
               'algorithm': 'HMAC-SHA256', 'encryption': ENCRYPTION_STATUS, 'receipt_mac': 'b' * 64}
    with pytest.raises(ReceiptValidationError, match='not available'):
        store.retrieve(receipt)
