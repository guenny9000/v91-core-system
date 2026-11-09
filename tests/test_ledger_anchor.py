from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from controller.ledger_anchor import (
    CheckpointError,
    compare_local_head,
    sign_checkpoint,
    verify_checkpoint,
)


def _checkpoint():
    return {
        "schema_version": 1,
        "ledger_id": "ledger-main",
        "sequence": 12,
        "head_hash": "a" * 64,
        "created_at_utc": "2026-11-09T07:00:00Z",
    }


def test_signed_checkpoint_verifies_and_matches():
    private_key = Ed25519PrivateKey.generate()
    envelope = sign_checkpoint(_checkpoint(), key_id="test-key-1", private_key=private_key)
    verified = verify_checkpoint(
        envelope,
        trusted_keys={"test-key-1": private_key.public_key()},
    )
    assert verified["status"] == "SIGNATURE_VALID"
    assert compare_local_head(
        verified,
        ledger_id="ledger-main",
        sequence=12,
        head_hash="a" * 64,
    ) == {"status": "CHECKPOINT_MATCH"}


def test_modified_checkpoint_is_rejected():
    private_key = Ed25519PrivateKey.generate()
    envelope = sign_checkpoint(_checkpoint(), key_id="test-key-1", private_key=private_key)
    envelope["checkpoint"]["head_hash"] = "b" * 64
    verified = verify_checkpoint(
        envelope,
        trusted_keys={"test-key-1": private_key.public_key()},
    )
    assert verified["status"] == "SIGNATURE_INVALID"


def test_unknown_key_is_not_a_pass():
    private_key = Ed25519PrivateKey.generate()
    envelope = sign_checkpoint(_checkpoint(), key_id="key-a", private_key=private_key)
    assert verify_checkpoint(envelope, trusted_keys={})["status"] == "UNKNOWN_KEY"


def test_rollback_is_detected_against_verified_checkpoint():
    private_key = Ed25519PrivateKey.generate()
    envelope = sign_checkpoint(_checkpoint(), key_id="test-key-1", private_key=private_key)
    verified = verify_checkpoint(
        envelope,
        trusted_keys={"test-key-1": private_key.public_key()},
    )
    assert compare_local_head(
        verified,
        ledger_id="ledger-main",
        sequence=11,
        head_hash="c" * 64,
    ) == {"status": "ROLLBACK_DETECTED"}


def test_invalid_checkpoint_sequence_is_rejected():
    invalid = _checkpoint()
    invalid["sequence"] = True
    try:
        sign_checkpoint(
            invalid,
            key_id="test-key-1",
            private_key=Ed25519PrivateKey.generate(),
        )
    except CheckpointError:
        pass
    else:
        raise AssertionError("boolean sequence must be rejected")
