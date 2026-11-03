from controller.peer_sync import PeerRegistry, create_heartbeat


SECRET = b"v91-test-secret-material-at-least-32-bytes"
TRUST = {"node-a-key": ("node-a", SECRET)}


def heartbeat(sequence=1, timestamp=1000.0):
    return create_heartbeat(
        peer_id="node-a",
        key_id="node-a-key",
        secret=SECRET,
        sequence=sequence,
        software_version="test-1",
        capabilities=["audit", "offline-check"],
        timestamp=timestamp,
    )


def test_valid_fresh_heartbeat_is_verified():
    registry = PeerRegistry(TRUST)
    result = registry.receive(heartbeat(), now=1005.0)
    assert result.state == "ALIVE_VERIFIED"
    assert result.peer_id == "node-a"


def test_tampered_payload_is_rejected():
    message = heartbeat()
    message["state"] = "BUSY"
    result = PeerRegistry(TRUST).receive(message, now=1005.0)
    assert result.state == "INVALID"
    assert result.reason == "signature verification failed"


def test_unknown_key_is_rejected():
    message = heartbeat()
    message["key_id"] = "unknown"
    result = PeerRegistry(TRUST).receive(message, now=1005.0)
    assert result.state == "INVALID"
    assert result.reason == "unknown key_id"


def test_key_cannot_impersonate_another_peer():
    message = heartbeat()
    message["peer_id"] = "node-b"
    result = PeerRegistry(TRUST).receive(message, now=1005.0)
    assert result.state == "INVALID"
    assert result.reason == "key is not bound to this peer_id"


def test_replayed_or_non_increasing_sequence_is_rejected():
    registry = PeerRegistry(TRUST)
    assert registry.receive(heartbeat(sequence=4), now=1005.0).state == "ALIVE_VERIFIED"
    replay = registry.receive(heartbeat(sequence=4), now=1006.0)
    assert replay.state == "INVALID"
    assert replay.reason == "replay or non-increasing sequence"


def test_old_heartbeat_is_stale():
    result = PeerRegistry(TRUST, max_age_seconds=30).receive(
        heartbeat(timestamp=1000.0), now=1040.0
    )
    assert result.state == "STALE"


def test_future_heartbeat_is_invalid_without_consuming_sequence():
    registry = PeerRegistry(TRUST, max_future_skew_seconds=5)
    future = registry.receive(heartbeat(sequence=1, timestamp=1020.0), now=1000.0)
    assert future.state == "INVALID"
    valid = registry.receive(heartbeat(sequence=1, timestamp=1000.0), now=1000.0)
    assert valid.state == "ALIVE_VERIFIED"


def test_verified_peer_becomes_stale_when_heartbeat_expires():
    registry = PeerRegistry(TRUST, max_age_seconds=10)
    assert registry.receive(heartbeat(timestamp=1000.0), now=1000.0).state == "ALIVE_VERIFIED"
    states = registry.mark_unseen_stale(now=1011.0)
    assert states["node-a"].state == "STALE"


def test_registry_state_is_returned_as_a_copy():
    registry = PeerRegistry(TRUST)
    registry.receive(heartbeat(), now=1000.0)
    snapshot = registry.states
    snapshot.clear()
    assert "node-a" in registry.states
