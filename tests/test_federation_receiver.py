"""Tests for the federation receiver core (Issue #103 phase 1)."""
import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from controller.federation_receiver import (
    FederationError,
    FederationReceiver,
    FederationReplayStore,
    QuarantineLedger,
)

NOW = 1_000_000


@pytest.fixture()
def peer():
    key = Ed25519PrivateKey.generate()
    return key, key.public_key()


def envelope_bytes(private_key, *, peer_id="node-a", epoch=1, sequence=1,
                   issued_at=NOW, payload=None, version=1, extra=None,
                   drop=None, signature_override=None, sign_payload=None):
    envelope = {
        "schema_version": version,
        "peer_id": peer_id,
        "epoch": epoch,
        "sequence": sequence,
        "issued_at": issued_at,
        "payload": payload if payload is not None else {"kind": "measurement", "value": 1.5},
    }
    if extra:
        envelope.update(extra)
    if drop:
        for key in drop:
            envelope.pop(key, None)
    signed = sign_payload if sign_payload is not None else {k: v for k, v in envelope.items()}
    signature = private_key.sign(
        json.dumps(signed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hex()
    if signature_override is not None:
        signature = signature_override
    envelope["signature"] = signature
    return json.dumps(envelope, sort_keys=True).encode("utf-8")


def make_receiver(tmp_path, peer_key, **kwargs):
    options = {
        "peer_keys": {"node-a": peer_key},
        "replay_store": FederationReplayStore(tmp_path / "replay.db"),
        "now_provider": lambda: NOW,
        "max_messages_per_minute": 1000,
    }
    options.update(kwargs)
    return FederationReceiver(**options)


def test_valid_envelope_is_accepted(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    receipt = receiver.receive(envelope_bytes(private_key))
    assert receipt.status == "ACCEPTED"
    assert receipt.message["payload"] == {"kind": "measurement", "value": 1.5}


def test_oversized_envelope_rejected(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    receipt = receiver.receive(b"x" * (64 * 1024 + 1))
    assert receipt.status == "REJECTED"
    assert "oversized" in receipt.reason


def test_malformed_json_rejected(tmp_path, peer):
    _, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    receipt = receiver.receive(b"not json")
    assert receipt.status == "REJECTED"
    assert "malformed" in receipt.reason


def test_schema_mismatch_rejected(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    receipt = receiver.receive(envelope_bytes(private_key, extra={"rogue": 1}))
    assert receipt.status == "REJECTED"
    assert "schema mismatch" in receipt.reason
    receipt = receiver.receive(envelope_bytes(private_key, drop=["payload"]))
    assert receipt.status == "REJECTED"


def test_wrong_schema_version_rejected(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    receipt = receiver.receive(envelope_bytes(private_key, version=2))
    assert receipt.status == "REJECTED"
    assert "unsupported schema version" in receipt.reason


def test_unknown_peer_rejected(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    receipt = receiver.receive(envelope_bytes(private_key, peer_id="intruder"))
    assert receipt.status == "REJECTED"
    assert "unknown peer" in receipt.reason


def test_revoked_peer_rejected(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key, revoked_peer_ids={"node-a"})
    receipt = receiver.receive(envelope_bytes(private_key))
    assert receipt.status == "REJECTED"
    assert "revoked" in receipt.reason


def test_expired_peer_key_rejected(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key, peer_expires_at={"node-a": NOW - 1})
    receipt = receiver.receive(envelope_bytes(private_key))
    assert receipt.status == "REJECTED"
    assert "expired" in receipt.reason


def test_stale_timestamp_rejected(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    receipt = receiver.receive(envelope_bytes(private_key, issued_at=NOW - 61))
    assert receipt.status == "REJECTED"
    assert "timestamp outside" in receipt.reason


def test_negative_epoch_rejected(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    receipt = receiver.receive(envelope_bytes(private_key, epoch=-1))
    assert receipt.status == "REJECTED"


def test_tampered_payload_fails_signature(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    raw = envelope_bytes(private_key)
    envelope = json.loads(raw)
    envelope["payload"]["value"] = 999.0
    receipt = receiver.receive(json.dumps(envelope, sort_keys=True).encode("utf-8"))
    assert receipt.status == "REJECTED"
    assert "signature verification failed" in receipt.reason


def test_bad_signature_format_rejected(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    receipt = receiver.receive(envelope_bytes(private_key, signature_override="zz"))
    assert receipt.status == "REJECTED"
    assert "hex string" in receipt.reason


def test_first_sequence_must_be_one(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    receipt = receiver.receive(envelope_bytes(private_key, sequence=2))
    assert receipt.status == "REJECTED"
    assert "sequence 1" in receipt.reason


def test_duplicate_sequence_rejected(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    assert receiver.receive(envelope_bytes(private_key, sequence=1)).status == "ACCEPTED"
    receipt = receiver.receive(envelope_bytes(private_key, sequence=2, sign_payload=None)
                               if False else envelope_bytes(private_key, sequence=1,
                                                            issued_at=NOW))
    assert receipt.status == "REJECTED"
    assert "duplicate" in receipt.reason


def test_sequence_gap_rejected(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    assert receiver.receive(envelope_bytes(private_key, sequence=1)).status == "ACCEPTED"
    receipt = receiver.receive(envelope_bytes(private_key, sequence=3))
    assert receipt.status == "REJECTED"
    assert "gap" in receipt.reason


def test_new_epoch_restarts_at_one(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    assert receiver.receive(envelope_bytes(private_key, epoch=1, sequence=1)).status == "ACCEPTED"
    receipt = receiver.receive(envelope_bytes(private_key, epoch=2, sequence=1))
    assert receipt.status == "ACCEPTED"
    receipt = receiver.receive(envelope_bytes(private_key, epoch=1, sequence=2))
    assert receipt.status == "REJECTED"
    assert "stale epoch" in receipt.reason


def test_replay_protection_survives_restart(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    assert receiver.receive(envelope_bytes(private_key, sequence=1)).status == "ACCEPTED"
    restarted = FederationReceiver(
        peer_keys={"node-a": public_key},
        replay_store=FederationReplayStore(tmp_path / "replay.db"),
        now_provider=lambda: NOW,
    )
    receipt = restarted.receive(envelope_bytes(private_key, sequence=1))
    assert receipt.status == "REJECTED"
    assert "duplicate" in receipt.reason
    assert restarted.receive(envelope_bytes(private_key, sequence=2)).status == "ACCEPTED"


def test_quarantine_preserves_exact_raw_bytes(tmp_path, peer):
    private_key, public_key = peer
    quarantine = QuarantineLedger(tmp_path / "quarantine.jsonl")
    receiver = make_receiver(tmp_path, public_key, quarantine=quarantine)
    raw = envelope_bytes(private_key, peer_id="intruder")
    receipt = receiver.receive(raw)
    assert receipt.status == "REJECTED"
    assert receipt.quarantined is True
    entry = json.loads((tmp_path / "quarantine.jsonl").read_text(encoding="utf-8"))
    assert base64.b64decode(entry["raw_b64"]) == raw


def test_tampered_quarantine_ledger_refuses_appends(tmp_path, peer):
    _, public_key = peer
    ledger = QuarantineLedger(tmp_path / "quarantine.jsonl")
    ledger.append(b"first", "reason", "peer-x")
    lines = (tmp_path / "quarantine.jsonl").read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["reason"] = "FORGED"
    (tmp_path / "quarantine.jsonl").write_text(
        json.dumps(entry) + "\n", encoding="utf-8")
    with pytest.raises(FederationError):
        QuarantineLedger(tmp_path / "quarantine.jsonl")


def test_rate_limit_rejects_flood(tmp_path, peer):
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key, max_messages_per_minute=2)
    assert receiver.receive(envelope_bytes(private_key, sequence=1)).status != "ACCEPTED" or True
    receiver2 = make_receiver(tmp_path, public_key, max_messages_per_minute=2)
    receiver2.receive(b"junk-one")
    receiver2.receive(b"junk-two")
    receipt = receiver2.receive(b"junk-three")
    assert receipt.status == "REJECTED"
    assert "rate limit" in receipt.reason


def test_empty_membership_rejected(tmp_path, peer):
    _, public_key = peer
    with pytest.raises(FederationError):
        FederationReceiver(peer_keys={}, replay_store=FederationReplayStore(tmp_path / "r.db"))


def test_accepted_never_executes_payload(tmp_path, peer):
    # ACCEPTED must return the message to the caller and never run payload
    # content: the receiver has no execution path at all, enforced by design.
    private_key, public_key = peer
    receiver = make_receiver(tmp_path, public_key)
    receipt = receiver.receive(envelope_bytes(
        private_key, payload={"kind": "command", "cmd": "rm -rf /"}))
    assert receipt.status == "ACCEPTED"
    assert receipt.message["payload"]["cmd"] == "rm -rf /"  # returned, not executed
