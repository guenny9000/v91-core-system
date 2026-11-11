import hashlib
import hmac
import json
import sqlite3
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from controller.replay_db_unification import (
    ReplayMigrationError,
    V91ReplayDatabaseUnifier,
    VerifiedTaskIngressConnector,
)
from controller.replay_state_provider import ReplayStateProvider
from controller.state_monotonicity import DOMAIN, V91StateMonotonicityGuard, _canonical
from controller.task_ingress_gate import TaskIngressGate


KEY = b"migration-test-provider-secret-at-least-32-bytes"
PROVIDER = "provider-test"


class KeyProvider:
    def get_active_key(self, provider_id):
        return KEY if provider_id == PROVIDER else None


def legacy_db(path, rows):
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE ingress_replay (provider_id TEXT NOT NULL, "
            "task_id TEXT NOT NULL, nonce TEXT NOT NULL, claimed_at INTEGER NOT NULL, "
            "PRIMARY KEY(provider_id, task_id), UNIQUE(provider_id, nonce))"
        )
        conn.executemany("INSERT INTO ingress_replay VALUES (?, ?, ?, ?)", rows)


def test_migration_imports_actual_legacy_schema_and_preserves_source(tmp_path):
    old_db, new_db = tmp_path / "old.sqlite3", tmp_path / "new.sqlite3"
    legacy_db(old_db, [
        (PROVIDER, "T-1", "a" * 32, 1799990000),
        (PROVIDER, "T-2", "b" * 32, 1799990300),
    ])
    provider = ReplayStateProvider(new_db)
    before = old_db.read_bytes()

    assert V91ReplayDatabaseUnifier.migrate_and_unify(old_db, new_db) is True
    assert provider.get_last_logged_sequence() == 2
    assert old_db.read_bytes() == before
    assert provider.claim(PROVIDER, "T-1", "c" * 32) is False
    assert provider.claim(PROVIDER, "T-3", "a" * 32) is False


def test_migration_is_idempotent_for_same_source_snapshot(tmp_path):
    old_db, new_db = tmp_path / "old.sqlite3", tmp_path / "new.sqlite3"
    legacy_db(old_db, [(PROVIDER, "T-1", "a" * 32, 1799990000)])
    provider = ReplayStateProvider(new_db)

    assert V91ReplayDatabaseUnifier.migrate_and_unify(old_db, new_db)
    first_hash = provider.compute_current_state_hash()
    assert V91ReplayDatabaseUnifier.migrate_and_unify(old_db, new_db)
    assert provider.get_last_logged_sequence() == 1
    assert provider.compute_current_state_hash() == first_hash


def test_completed_migration_marker_does_not_hide_missing_destination_rows(tmp_path):
    old_db, new_db = tmp_path / "old.sqlite3", tmp_path / "new.sqlite3"
    legacy_db(old_db, [(PROVIDER, "T-1", "a" * 32, 1799990000)])
    provider = ReplayStateProvider(new_db)
    assert V91ReplayDatabaseUnifier.migrate_and_unify(old_db, new_db)
    with sqlite3.connect(new_db) as conn:
        conn.execute("DELETE FROM replay_store WHERE provider_id=? AND task_id=?",
                     (PROVIDER, "T-1"))
    with pytest.raises(ReplayMigrationError, match="no longer matches"):
        V91ReplayDatabaseUnifier.migrate_and_unify(old_db, new_db)
    assert provider.get_last_logged_sequence() == 0


def test_exact_existing_claim_is_accepted_but_conflicting_mapping_rolls_back(tmp_path):
    old_db, new_db = tmp_path / "old.sqlite3", tmp_path / "new.sqlite3"
    legacy_db(old_db, [
        (PROVIDER, "T-1", "a" * 32, 1799990000),
        (PROVIDER, "T-2", "b" * 32, 1799990300),
    ])
    provider = ReplayStateProvider(new_db)
    with sqlite3.connect(new_db) as conn:
        conn.execute(
            "INSERT INTO replay_store(provider_id, task_id, nonce, timestamp_utc) "
            "VALUES (?, ?, ?, ?)",
            (PROVIDER, "T-1", "a" * 32,
             datetime.fromtimestamp(1799990000, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")),
        )
        conn.execute(
            "INSERT INTO replay_store(provider_id, task_id, nonce, timestamp_utc) "
            "VALUES (?, ?, ?, ?)",
            (PROVIDER, "T-existing", "b" * 32,
             datetime.fromtimestamp(1799990300, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")),
        )
    before_sequence = provider.get_last_logged_sequence()

    with pytest.raises(ReplayMigrationError, match="identity conflict"):
        V91ReplayDatabaseUnifier.migrate_and_unify(old_db, new_db)
    assert provider.get_last_logged_sequence() == before_sequence


def test_missing_legacy_table_fails_closed(tmp_path):
    old_db, new_db = tmp_path / "old.sqlite3", tmp_path / "new.sqlite3"
    sqlite3.connect(old_db).close()
    ReplayStateProvider(new_db)
    with pytest.raises(ReplayMigrationError, match="table is missing"):
        V91ReplayDatabaseUnifier.migrate_and_unify(old_db, new_db)


def _signed_heartbeat(private, challenge, database_id, sequence, root):
    payload = {
        "schema_version": 1,
        "database_id": database_id,
        "epoch": 1,
        "sequence": sequence,
        "state_root_hash": root,
        "issued_at_utc": datetime.now(timezone.utc).isoformat(),
        "challenge": challenge,
    }
    return {
        "algorithm": "Ed25519",
        "key_id": "witness-1",
        "payload": payload,
        "signature": private.sign(DOMAIN + _canonical(payload)).hex(),
    }


def test_connector_checks_witness_before_ingress_and_keeps_execution_unauthorized(tmp_path):
    db = tmp_path / "replay.sqlite3"
    provider = ReplayStateProvider(db)
    private = Ed25519PrivateKey.generate()
    challenge = "c" * 64
    guard = V91StateMonotonicityGuard(provider, {"witness-1": private.public_key()})
    gate = TaskIngressGate(KeyProvider(), provider, clock=lambda: 1800000000)
    connector = VerifiedTaskIngressConnector(gate, guard, "witness-1")
    heartbeat = _signed_heartbeat(
        private, challenge, provider.get_database_id(),
        provider.get_last_logged_sequence(), provider.compute_current_state_hash(),
    )
    payload = {
        "task_id": "T-1", "provider_id": PROVIDER, "timestamp": 1800000000,
        "nonce": "d" * 32,
        "purpose": {"classification": "EDUCATION", "sector": "OTHER"},
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(KEY, body, hashlib.sha256).hexdigest()

    result = connector.handle_incoming_task(
        payload, body, signature, heartbeat, expected_challenge=challenge
    )
    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["execution_authorized"] is False


def test_connector_closes_gate_on_witness_failure_without_claiming_task(tmp_path):
    db = tmp_path / "replay.sqlite3"
    provider = ReplayStateProvider(db)
    private = Ed25519PrivateKey.generate()
    challenge = "e" * 64
    guard = V91StateMonotonicityGuard(provider, {"witness-1": private.public_key()})
    gate = TaskIngressGate(KeyProvider(), provider, clock=lambda: 1800000000)
    connector = VerifiedTaskIngressConnector(gate, guard, "witness-1")
    heartbeat = _signed_heartbeat(
        private, challenge, provider.get_database_id(), 0,
        provider.compute_current_state_hash(),
    )
    payload = {
        "task_id": "T-2", "provider_id": PROVIDER, "timestamp": 1800000000,
        "nonce": "f" * 32,
        "purpose": {"classification": "EDUCATION", "sector": "OTHER"},
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(KEY, body, hashlib.sha256).hexdigest()

    result = connector.handle_incoming_task(
        payload, body, signature, heartbeat, expected_challenge="0" * 64
    )
    assert result["decision"] == "GATE_CLOSED"
    assert provider.get_last_logged_sequence() == 0
