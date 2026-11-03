import math

import pytest

from controller.peer_sync import (
    HeartbeatError,
    PeerRegistry,
    create_heartbeat,
)


SECRET = b"v91-test-secret-material-at-least-32-bytes"
TRUST = {"node-a-key": ("node-a", SECRET)}


def valid_kwargs(**overrides):
    kwargs = {
        "peer_id": "node-a",
        "key_id": "node-a-key",
        "secret": SECRET,
        "sequence": 1,
        "software_version": "test-1",
        "capabilities": ["audit"],
    }
    kwargs.update(overrides)
    return kwargs


# ---- create_heartbeat: error paths (Review-Finding 5) ----


def test_short_secret_is_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(secret=b"too-short"))


def test_non_bytes_secret_is_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(secret="string-not-bytes"))


def test_empty_peer_id_is_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(peer_id=""))


def test_empty_key_id_is_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(key_id=""))


def test_empty_software_version_is_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(software_version=""))


def test_zero_sequence_is_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(sequence=0))


def test_boolean_sequence_is_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(sequence=True))


def test_unsupported_state_is_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(state="HACKED"))


def test_empty_capability_is_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(capabilities=["audit", ""]))


def test_duplicate_capabilities_are_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(capabilities=["audit", "audit"]))


def test_nan_timestamp_is_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(timestamp=float("nan")))


def test_infinite_timestamp_is_rejected():
    with pytest.raises(HeartbeatError):
        create_heartbeat(**valid_kwargs(timestamp=math.inf))


# ---- create_heartbeat: contract ----


def test_created_heartbeat_passes_registry_verification():
    registry = PeerRegistry(TRUST)
    message = create_heartbeat(**valid_kwargs(timestamp=1000.0))
    result = registry.receive(message, now=1005.0)
    assert result.state == "ALIVE_VERIFIED"


def test_capabilities_are_sorted_and_unique_in_payload():
    message = create_heartbeat(**valid_kwargs(capabilities=["b-cap", "a-cap"]))
    assert message["capabilities"] == ["a-cap", "b-cap"]


def test_signature_field_is_hex_sha256_length():
    message = create_heartbeat(**valid_kwargs(timestamp=1000.0))
    assert isinstance(message["signature"], str)
    assert len(message["signature"]) == 64
