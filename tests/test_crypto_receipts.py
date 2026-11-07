import pytest

from controller.crypto_receipts import (
    CryptoReceiptError,
    canonical_record_bytes,
    generate_signing_keypair,
    sign_record,
    verify_record_signature,
)


@pytest.fixture
def keypair():
    return generate_signing_keypair()


def test_generated_keypair_has_raw_32_byte_keys(keypair):
    private_key, public_key = keypair
    assert len(private_key) == 32
    assert len(public_key) == 32


def test_sign_and_verify_roundtrip(keypair):
    private_key, public_key = keypair
    record = {"object_digest": "a" * 64, "owner_id": "node-1"}
    record["receipt_signature"] = sign_record(record, private_key)
    assert verify_record_signature(record, public_key) is True


def test_wrong_key_fails_verification(keypair):
    private_key, _ = keypair
    _, other_public = generate_signing_keypair()
    record = {"object_digest": "a" * 64, "owner_id": "node-1"}
    record["receipt_signature"] = sign_record(record, private_key)
    assert verify_record_signature(record, other_public) is False


def test_tampered_record_fails_verification(keypair):
    private_key, public_key = keypair
    record = {"object_digest": "a" * 64, "owner_id": "node-1"}
    record["receipt_signature"] = sign_record(record, private_key)
    record["owner_id"] = "node-evil"
    assert verify_record_signature(record, public_key) is False


def test_missing_signature_fails_verification(keypair):
    _, public_key = keypair
    assert verify_record_signature({"a": 1}, public_key) is False


def test_signing_record_with_existing_signature_is_refused(keypair):
    private_key, _ = keypair
    record = {"receipt_signature": "x"}
    with pytest.raises(CryptoReceiptError, match="signature"):
        sign_record(record, private_key)


def test_invalid_private_key_is_refused():
    with pytest.raises(CryptoReceiptError, match="32 bytes"):
        sign_record({}, b"short")


def test_canonical_bytes_are_key_order_insensitive():
    a = canonical_record_bytes({"x": 1, "y": 2})
    b = canonical_record_bytes({"y": 2, "x": 1})
    assert a == b
