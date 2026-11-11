import hashlib
import hmac
import os

import pytest

from controller.emergency_stop import (
    ACTIVATE_DOMAIN,
    RESET_DOMAIN,
    EmergencyStopError,
    LocalEmergencyStop,
    _confirmation,
)

KEY = b"test-emergency-key-at-least-32-bytes!!"


def make_stop(tmp_path, key=KEY):
    return LocalEmergencyStop(
        tmp_path / "stop.flag", tmp_path / "stop_ledger.jsonl", key=key
    )


def test_activate_sets_flag_and_ledger_entry(tmp_path):
    stop = make_stop(tmp_path)
    reason = "isolated local incident"
    entry = stop.activate(reason, _confirmation(KEY, ACTIVATE_DOMAIN, reason))
    assert entry["seq"] == 1 and entry["action"] == "ACTIVATE"
    assert stop.is_stopped() == (True, "STOPPED_FLAG_PRESENT")
    assert stop.verify_ledger() is True


def test_wrong_confirmation_never_sets_flag(tmp_path):
    stop = make_stop(tmp_path)
    with pytest.raises(EmergencyStopError, match="confirmation invalid"):
        stop.activate("reason", "0" * 64)
    assert stop.is_stopped() == (False, "RUNNING_NO_FLAG")
    assert stop.verify_ledger() is True  # no ledger entry was written


def test_confirmation_is_bound_to_reason(tmp_path):
    stop = make_stop(tmp_path)
    with pytest.raises(EmergencyStopError):
        stop.activate("other reason", _confirmation(KEY, ACTIVATE_DOMAIN, "original reason"))
    assert stop.is_stopped() == (False, "RUNNING_NO_FLAG")


def test_reset_requires_valid_chain_and_own_confirmation(tmp_path):
    stop = make_stop(tmp_path)
    reason = "incident contained"
    stop.activate("incident", _confirmation(KEY, ACTIVATE_DOMAIN, "incident"))
    with pytest.raises(EmergencyStopError, match="confirmation invalid"):
        stop.reset(reason, _confirmation(KEY, ACTIVATE_DOMAIN, reason))  # wrong domain
    entry = stop.reset(reason, _confirmation(KEY, RESET_DOMAIN, reason))
    assert entry["action"] == "RESET" and entry["seq"] == 2
    assert stop.is_stopped() == (False, "RUNNING_NO_FLAG")
    assert stop.verify_ledger() is True


def test_reset_refused_when_ledger_tampered(tmp_path):
    stop = make_stop(tmp_path)
    stop.activate("incident", _confirmation(KEY, ACTIVATE_DOMAIN, "incident"))
    ledger = tmp_path / "stop_ledger.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    tampered = lines[0].replace("incident", "harmless")
    ledger.write_text(tampered + "\n", encoding="utf-8")
    assert stop.verify_ledger() is False
    with pytest.raises(EmergencyStopError, match="reset refused"):
        stop.reset("ok", _confirmation(KEY, RESET_DOMAIN, "ok"))
    assert stop.is_stopped() == (True, "STOPPED_FLAG_PRESENT")


def test_missing_or_short_key_fails_closed(tmp_path):
    with pytest.raises(EmergencyStopError, match="32 bytes"):
        make_stop(tmp_path, key=None)  # env unset in test process
    with pytest.raises(EmergencyStopError, match="32 bytes"):
        make_stop(tmp_path, key=b"short")


def test_unreadable_flag_counts_as_stopped(tmp_path):
    stop = make_stop(tmp_path)
    flag = tmp_path / "stop.flag"
    flag.write_text("x", encoding="utf-8")
    os.chmod(flag, 0o000)
    try:
        assert stop.is_stopped()[0] is True
    finally:
        os.chmod(flag, 0o644)


def test_activation_is_idempotent_safe_and_ledger_grows(tmp_path):
    stop = make_stop(tmp_path)
    reason = "halt"
    stop.activate(reason, _confirmation(KEY, ACTIVATE_DOMAIN, reason))
    stop.activate(reason, _confirmation(KEY, ACTIVATE_DOMAIN, reason))
    assert stop.is_stopped() == (True, "STOPPED_FLAG_PRESENT")
    assert stop.verify_ledger() is True


def test_env_key_is_used_when_provided(tmp_path, monkeypatch):
    monkeypatch.setenv("V91_EMERGENCY_KEY", "env-provided-emergency-key-32-bytes!")
    stop = LocalEmergencyStop(tmp_path / "f", tmp_path / "l")
    reason = "env test"
    env_key = "env-provided-emergency-key-32-bytes!".encode()
    stop.activate(reason, hmac.new(env_key, ACTIVATE_DOMAIN + reason.encode(), hashlib.sha256).hexdigest())
    assert stop.is_stopped()[0] is True
