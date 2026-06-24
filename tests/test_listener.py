#!/usr/bin/env python3
"""
Integration Tests – v91 Interop Listener
Tests cover: SafeSignal protocol, HITL routing, quarantine, audit logging.
"""

import hashlib
import hmac
import json
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow importing from controller/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

import v91_listener as listener


# ── Fixtures ──────────────────────────────────────────────────────────────────

TEST_KEY = b"test-secret-key-for-unit-tests"


def _setup_db(db_path: str) -> None:
    """Initialise test DB using the canonical SQL schema."""
    sql_path = Path(__file__).parent.parent / "data" / "init_listener_db.sql"
    schema = sql_path.read_text()
    conn = sqlite3.connect(db_path)
    conn.executescript(schema)
    conn.commit()
    conn.close()


def _make_event(payload: dict, key: bytes = TEST_KEY, ts_offset_s: int = 0) -> bytes:
    """Build a valid SafeSignal-signed event envelope."""
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
    ts = datetime.fromtimestamp(
        time.time() + ts_offset_s, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    event = {
        "safesignal": {"version": "1", "sig": sig, "ts": ts},
        "payload": payload,
    }
    return json.dumps(event).encode()


def _count(db_path: str, table: str, where: str = "") -> int:
    conn = sqlite3.connect(db_path)
    q = f"SELECT COUNT(*) FROM {table}"
    if where:
        q += f" WHERE {where}"
    (n,) = conn.execute(q).fetchone()
    conn.close()
    return n


# ── SafeSignal Tests ──────────────────────────────────────────────────────────

def test_safesignal_valid():
    """Valid signature is accepted."""
    payload = {"event_type": "test", "source": "pytest", "data": {}}
    raw = _make_event(payload)
    event = json.loads(raw)
    valid, reason = listener.safesignal_check(event, raw, TEST_KEY)
    assert valid, f"Expected valid, got: {reason}"
    print("✓ test_safesignal_valid")


def test_safesignal_wrong_key():
    """Signature made with wrong key is rejected."""
    payload = {"event_type": "test", "source": "pytest", "data": {}}
    raw = _make_event(payload, key=b"wrong-key")
    event = json.loads(raw)
    valid, reason = listener.safesignal_check(event, raw, TEST_KEY)
    assert not valid
    assert "signature mismatch" in reason
    print("✓ test_safesignal_wrong_key")


def test_safesignal_missing_envelope():
    """Event without safesignal envelope is rejected."""
    event = {"payload": {"event_type": "test", "source": "s", "data": {}}}
    valid, reason = listener.safesignal_check(event, b"{}", TEST_KEY)
    assert not valid
    assert "missing safesignal envelope" in reason
    print("✓ test_safesignal_missing_envelope")


def test_safesignal_old_timestamp():
    """Events older than 5 minutes are rejected."""
    payload = {"event_type": "test", "source": "pytest", "data": {}}
    raw = _make_event(payload, ts_offset_s=-400)  # 400 seconds in the past
    event = json.loads(raw)
    valid, reason = listener.safesignal_check(event, raw, TEST_KEY)
    assert not valid
    assert "event too old" in reason
    print("✓ test_safesignal_old_timestamp")


def test_safesignal_unsupported_version():
    """Events with unknown SafeSignal version are rejected."""
    payload = {"event_type": "test", "source": "pytest", "data": {}}
    raw = _make_event(payload)
    event = json.loads(raw)
    event["safesignal"]["version"] = "99"
    valid, reason = listener.safesignal_check(event, raw, TEST_KEY)
    assert not valid
    assert "unsupported" in reason
    print("✓ test_safesignal_unsupported_version")


# ── Schema Validation Tests ───────────────────────────────────────────────────

def test_validate_payload_valid():
    ok, reason = listener.validate_payload(
        {"event_type": "login", "source": "web", "data": {}}
    )
    assert ok, reason
    print("✓ test_validate_payload_valid")


def test_validate_payload_missing_field():
    ok, reason = listener.validate_payload({"event_type": "login", "data": {}})
    assert not ok
    assert "source" in reason
    print("✓ test_validate_payload_missing_field")


def test_validate_payload_empty_event_type():
    ok, reason = listener.validate_payload(
        {"event_type": "", "source": "web", "data": {}}
    )
    assert not ok
    print("✓ test_validate_payload_empty_event_type")


# ── Confidence / HITL Routing Tests ──────────────────────────────────────────

def test_confidence_normal_event():
    score = listener.compute_confidence(
        {"event_type": "user_login", "source": "web", "data": {}}
    )
    assert score >= listener.HITL_THRESHOLD
    print(f"✓ test_confidence_normal_event  score={score:.3f}")


def test_confidence_risky_event():
    score = listener.compute_confidence(
        {"event_type": "delete", "source": "admin", "data": {}}
    )
    assert score < listener.HITL_THRESHOLD
    print(f"✓ test_confidence_risky_event  score={score:.3f}")


def test_confidence_unknown_source():
    score = listener.compute_confidence(
        {"event_type": "update", "source": "unknown", "data": {}}
    )
    assert score < listener.HITL_THRESHOLD
    print(f"✓ test_confidence_unknown_source  score={score:.3f}")


# ── Full Pipeline Tests ───────────────────────────────────────────────────────

def test_valid_event_goes_to_ledger():
    """A fully valid event must appear in v91_ledger."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_db(db_path)
        inbox = Path(tmpdir) / "inbox"
        inbox.mkdir()

        payload = {"event_type": "user_login", "source": "web", "data": {"uid": "1"}}
        (inbox / "valid.json").write_bytes(_make_event(payload))

        listener.watch_inbox(str(inbox), TEST_KEY, db_path)

        assert _count(db_path, "v91_ledger") == 1
        assert _count(db_path, "v91_quarantine") == 0
        assert _count(db_path, "v91_hitl_queue") == 0
        assert _count(db_path, "v91_audit_log", "action='ledger_accepted'") == 1
        assert not (inbox / "valid.json").exists(), "Processed file must be removed"
    print("✓ test_valid_event_goes_to_ledger")


def test_risky_event_goes_to_hitl():
    """A risky (low-confidence) event must appear in v91_hitl_queue."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_db(db_path)
        inbox = Path(tmpdir) / "inbox"
        inbox.mkdir()

        payload = {"event_type": "delete", "source": "admin", "data": {}}
        (inbox / "risky.json").write_bytes(_make_event(payload))

        listener.watch_inbox(str(inbox), TEST_KEY, db_path)

        assert _count(db_path, "v91_hitl_queue", "status='pending'") == 1
        assert _count(db_path, "v91_ledger") == 0
        assert _count(db_path, "v91_audit_log", "action='hitl_queued'") == 1
    print("✓ test_risky_event_goes_to_hitl")


def test_invalid_signature_quarantined():
    """Event with bad signature must be quarantined."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_db(db_path)
        inbox = Path(tmpdir) / "inbox"
        inbox.mkdir()

        payload = {"event_type": "login", "source": "web", "data": {}}
        raw = _make_event(payload, key=b"different-key")
        (inbox / "badsig.json").write_bytes(raw)

        listener.watch_inbox(str(inbox), TEST_KEY, db_path)

        assert _count(db_path, "v91_quarantine") == 1
        assert _count(db_path, "v91_ledger") == 0
        row = sqlite3.connect(db_path).execute(
            "SELECT reason FROM v91_quarantine"
        ).fetchone()
        assert "signature mismatch" in row[0]
    print("✓ test_invalid_signature_quarantined")


def test_malformed_json_quarantined():
    """A non-JSON file must be quarantined."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_db(db_path)
        inbox = Path(tmpdir) / "inbox"
        inbox.mkdir()

        (inbox / "bad.json").write_bytes(b"{not valid json}")

        listener.watch_inbox(str(inbox), TEST_KEY, db_path)

        assert _count(db_path, "v91_quarantine") == 1
        assert _count(db_path, "v91_ledger") == 0
    print("✓ test_malformed_json_quarantined")


def test_missing_safesignal_quarantined():
    """Event without safesignal envelope must be quarantined."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_db(db_path)
        inbox = Path(tmpdir) / "inbox"
        inbox.mkdir()

        event = {"payload": {"event_type": "x", "source": "y", "data": {}}}
        (inbox / "nosig.json").write_bytes(json.dumps(event).encode())

        listener.watch_inbox(str(inbox), TEST_KEY, db_path)

        assert _count(db_path, "v91_quarantine") == 1
    print("✓ test_missing_safesignal_quarantined")


def test_inbox_empty_no_errors():
    """Empty inbox must not raise and leave all tables empty."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_db(db_path)
        inbox = Path(tmpdir) / "inbox"
        inbox.mkdir()

        listener.watch_inbox(str(inbox), TEST_KEY, db_path)

        assert _count(db_path, "v91_ledger") == 0
    print("✓ test_inbox_empty_no_errors")


def test_multiple_events_processed():
    """Multiple events in inbox are all processed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_db(db_path)
        inbox = Path(tmpdir) / "inbox"
        inbox.mkdir()

        # 3 valid, 1 risky, 1 quarantine
        for i in range(3):
            p = {"event_type": "login", "source": "web", "data": {"i": i}}
            (inbox / f"event_{i}.json").write_bytes(_make_event(p))

        risky = {"event_type": "delete", "source": "admin", "data": {}}
        (inbox / "risky.json").write_bytes(_make_event(risky))

        (inbox / "bad.json").write_bytes(b"not json")

        listener.watch_inbox(str(inbox), TEST_KEY, db_path)

        assert _count(db_path, "v91_ledger") == 3
        assert _count(db_path, "v91_hitl_queue") == 1
        assert _count(db_path, "v91_quarantine") == 1
        assert _count(db_path, "v91_audit_log") == 5
    print("✓ test_multiple_events_processed")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_safesignal_valid()
    test_safesignal_wrong_key()
    test_safesignal_missing_envelope()
    test_safesignal_old_timestamp()
    test_safesignal_unsupported_version()
    test_validate_payload_valid()
    test_validate_payload_missing_field()
    test_validate_payload_empty_event_type()
    test_confidence_normal_event()
    test_confidence_risky_event()
    test_confidence_unknown_source()
    test_valid_event_goes_to_ledger()
    test_risky_event_goes_to_hitl()
    test_invalid_signature_quarantined()
    test_malformed_json_quarantined()
    test_missing_safesignal_quarantined()
    test_inbox_empty_no_errors()
    test_multiple_events_processed()
    print("\n✓ All v91 listener tests passed")
