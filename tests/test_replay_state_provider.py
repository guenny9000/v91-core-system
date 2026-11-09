import sqlite3

import pytest

from controller.replay_state_provider import ReplayStateProvider


def test_provider_initialization_and_empty_state(tmp_path):
    provider = ReplayStateProvider(tmp_path / "nested" / "replay.sqlite3")
    assert provider.get_database_id()
    assert provider.get_last_logged_sequence() == 0
    assert len(provider.compute_current_state_hash()) == 64


def test_atomic_claim_and_monotonic_sequence(tmp_path):
    provider = ReplayStateProvider(tmp_path / "replay.sqlite3")
    assert provider.claim("p1", "T-99", "a" * 32) is True
    assert provider.get_last_logged_sequence() == 1
    assert provider.get_last_logged_timestamp().utcoffset().total_seconds() == 0
    assert provider.claim("p1", "T-99", "b" * 32) is False
    assert provider.claim("p1", "T-100", "a" * 32) is False
    assert provider.get_last_logged_sequence() == 1


def test_hash_changes_after_append_only_claim(tmp_path):
    provider = ReplayStateProvider(tmp_path / "replay.sqlite3")
    before = provider.compute_current_state_hash()
    provider.claim("p1", "T-1", "c" * 32)
    assert provider.compute_current_state_hash() != before


def test_hash_is_stable_for_unchanged_snapshot(tmp_path):
    provider = ReplayStateProvider(tmp_path / "replay.sqlite3")
    provider.claim("p1", "T-1", "d" * 32)
    assert provider.compute_current_state_hash() == provider.compute_current_state_hash()


def test_corrupt_schema_fails_closed(tmp_path):
    path = tmp_path / "replay.sqlite3"
    provider = ReplayStateProvider(path)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE replay_store")
    with pytest.raises(RuntimeError, match="CRITICAL"):
        provider.get_last_logged_sequence()


def test_caller_cannot_replace_or_rewind_sequence(tmp_path):
    provider = ReplayStateProvider(tmp_path / "replay.sqlite3")
    provider.record_transaction("T-1", "e" * 32, sequence_id=1)
    with pytest.raises(ValueError):
        provider.record_transaction("T-2", "f" * 32, sequence_id=1)
    assert provider.get_last_logged_sequence() == 1
