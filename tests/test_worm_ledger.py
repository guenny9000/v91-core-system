import sqlite3

import pytest

from controller.worm_ledger import LedgerIntegrityError, V91WormLedger


@pytest.fixture
def ledger(tmp_path):
    return V91WormLedger(tmp_path / "resource_worm.sqlite3")


def test_genesis_and_append_verify(ledger):
    assert ledger.verify_ledger_chain()
    ledger.append_resource_flow("WATER", 150.0, "CRITICAL_SUPPLY_PROTECTION")
    assert ledger.verify_ledger_chain()


def test_restricted_purpose_is_rejected(ledger):
    with pytest.raises(PermissionError):
        ledger.append_resource_flow("ENERGY", 5000.0, "WEAPONS_DEVELOPMENT")


def test_unknown_purpose_fails_closed(ledger):
    with pytest.raises(ValueError):
        ledger.append_resource_flow("ENERGY", 5.0, "HUMANITARIANNN")


def test_non_finite_and_negative_values_rejected(ledger):
    with pytest.raises(ValueError):
        ledger.append_resource_flow("WATER", float("nan"), "HUMANITARIAN")
    with pytest.raises(ValueError):
        ledger.append_resource_flow("WATER", -1, "HUMANITARIAN")


def test_sql_update_and_delete_are_blocked_by_triggers(ledger):
    with sqlite3.connect(ledger.ledger_path) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE resource_blocks SET value=4 WHERE block_index=0")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM resource_blocks WHERE block_index=0")


def test_tampering_is_detected_even_at_genesis(ledger):
    ledger.append_resource_flow("WATER", 150.0, "CRITICAL_SUPPLY_PROTECTION")
    with sqlite3.connect(ledger.ledger_path) as db:
        db.execute("DROP TRIGGER resource_blocks_no_update")
        db.execute("UPDATE resource_blocks SET value=999999.0 WHERE block_index=1")
    assert not ledger.verify_ledger_chain()


def test_genesis_tampering_is_detected(ledger):
    with sqlite3.connect(ledger.ledger_path) as db:
        db.execute("DROP TRIGGER resource_blocks_no_update")
        db.execute("UPDATE resource_blocks SET value=1.0 WHERE block_index=0")
    assert not ledger.verify_ledger_chain()


def test_missing_genesis_is_not_a_valid_chain(tmp_path):
    path = tmp_path / "empty.sqlite3"
    ledger = V91WormLedger(path)
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER resource_blocks_no_delete")
        db.execute("DELETE FROM resource_blocks WHERE block_index=0")
    assert not ledger.verify_ledger_chain()
