from datetime import datetime, timezone, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from controller.state_monotonicity import (
    DOMAIN,
    V91StateMonotonicityGuard,
    _canonical,
)


class Local:
    def __init__(self, seq=100, root="a" * 64):
        self.seq = seq
        self.root = root

    def get_database_id(self):
        return "replay-db-1"

    def get_last_logged_sequence(self):
        return self.seq

    def compute_current_state_hash(self):
        return self.root


def signed(private, challenge, *, seq=100, root="a" * 64, issued=None):
    payload = {
        "schema_version": 1,
        "database_id": "replay-db-1",
        "epoch": 7,
        "sequence": seq,
        "state_root_hash": root,
        "issued_at_utc": (issued or datetime.now(timezone.utc)).isoformat(),
        "challenge": challenge,
    }
    signature = private.sign(DOMAIN + _canonical(payload)).hex()
    return {"algorithm": "Ed25519", "key_id": "witness-1",
            "payload": payload, "signature": signature}


def make_guard(local, public, now=None):
    return V91StateMonotonicityGuard(
        local, {"witness-1": public}, clock=lambda: now or datetime.now(timezone.utc)
    )


def test_matching_fresh_signed_state_is_valid():
    private = Ed25519PrivateKey.generate()
    challenge = "c" * 64
    guard = make_guard(Local(), private.public_key())
    assert guard.verify_state_integrity(
        signed(private, challenge), expected_challenge=challenge, key_id="witness-1"
    ) == (True, "STATE_VALID_AND_MONOTONIC")


def test_restored_old_backup_is_detected_when_witness_is_ahead():
    private = Ed25519PrivateKey.generate()
    challenge = "d" * 64
    guard = make_guard(Local(seq=90), private.public_key())
    assert guard.verify_state_integrity(
        signed(private, challenge, seq=100), expected_challenge=challenge, key_id="witness-1"
    ) == (False, "ROLLBACK_DETECTED_SEQUENCE")


def test_same_sequence_with_different_root_is_detected():
    private = Ed25519PrivateKey.generate()
    challenge = "e" * 64
    guard = make_guard(Local(root="b" * 64), private.public_key())
    assert guard.verify_state_integrity(
        signed(private, challenge), expected_challenge=challenge, key_id="witness-1"
    ) == (False, "STATE_ROOT_MISMATCH")


def test_old_signed_heartbeat_cannot_be_replayed_for_new_challenge():
    private = Ed25519PrivateKey.generate()
    old_challenge = "f" * 64
    guard = make_guard(Local(), private.public_key())
    assert guard.verify_state_integrity(
        signed(private, old_challenge), expected_challenge="1" * 64, key_id="witness-1"
    ) == (False, "HEARTBEAT_CHALLENGE_MISMATCH")


def test_stale_heartbeat_fails_closed():
    private = Ed25519PrivateKey.generate()
    challenge = "2" * 64
    now = datetime.now(timezone.utc)
    guard = make_guard(Local(), private.public_key(), now=now)
    old = signed(private, challenge, issued=now - timedelta(seconds=301))
    assert guard.verify_state_integrity(
        old, expected_challenge=challenge, key_id="witness-1"
    ) == (False, "HEARTBEAT_OUTSIDE_FRESHNESS_WINDOW")


def test_local_ahead_of_witness_is_not_reported_as_valid():
    private = Ed25519PrivateKey.generate()
    challenge = "3" * 64
    guard = make_guard(Local(seq=101), private.public_key())
    assert guard.verify_state_integrity(
        signed(private, challenge, seq=100), expected_challenge=challenge, key_id="witness-1"
    ) == (False, "LOCAL_STATE_AHEAD_OF_WITNESS")


def test_modified_payload_signature_is_rejected():
    private = Ed25519PrivateKey.generate()
    challenge = "4" * 64
    envelope = signed(private, challenge)
    envelope["payload"]["sequence"] = 99
    guard = make_guard(Local(), private.public_key())
    assert guard.verify_state_integrity(
        envelope, expected_challenge=challenge, key_id="witness-1"
    ) == (False, "HEARTBEAT_SIGNATURE_INVALID")


def test_boolean_schema_version_is_rejected_even_with_valid_signature():
    private = Ed25519PrivateKey.generate()
    challenge = "5" * 64
    envelope = signed(private, challenge)
    envelope["payload"]["schema_version"] = True
    envelope["signature"] = private.sign(DOMAIN + _canonical(envelope["payload"])).hex()
    guard = make_guard(Local(), private.public_key())
    assert guard.verify_state_integrity(
        envelope, expected_challenge=challenge, key_id="witness-1"
    ) == (False, "INVALID_HEARTBEAT_PAYLOAD")


def test_max_age_seconds_must_be_positive_integer():
    private = Ed25519PrivateKey.generate()
    for value in (True, 1.5, 0):
        try:
            V91StateMonotonicityGuard(Local(), {"witness-1": private.public_key()}, max_age_seconds=value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid max_age_seconds must be rejected")
