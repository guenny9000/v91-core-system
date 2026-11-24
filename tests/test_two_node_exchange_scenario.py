"""
Tests fuer controller.two_node_exchange_scenario (Issue #47 Stage 4).

Zwei isolierte In-Process-Knoten: Faehigkeits- und Aufgaben-Metadaten
ueber die echte Foederations-Wire (Signatur, Replay-Schutz, Quarantaene),
Capability-Intake gegen die Trust-Registry, Lease-Fencing gegen spaete
Schreiber. Ehrliche Grenze: SIMULATION_IN_PROCESS != DEPLOYED_MULTI_NODE.
"""
import io
import json
from contextlib import redirect_stderr, redirect_stdout

import pytest

from controller.two_node_exchange_scenario import (
    LIMITS,
    STATUS_COMPLETE,
    STATUS_FAILED,
    ScenarioError,
    main,
    run_two_node_exchange,
)

NOW_ISO = "2026-11-24T12:00:00+00:00"


def test_healthy_exchange_completes(tmp_path):
    record = run_two_node_exchange(tmp_path / "run", now_iso=NOW_ISO)
    assert record["status"] == STATUS_COMPLETE
    assert all(record["checks"].values())
    assert record["checks"]["capability_envelope_accepted"]
    assert record["checks"]["capability_admitted"]
    assert record["checks"]["task_offer_accepted"]
    assert record["checks"]["lease_acquired"]
    assert record["checks"]["replay_rejected"]
    assert record["checks"]["stale_fencing_token_rejected"]
    assert record["checks"]["producer_survives_absent_verifier"]


def test_capability_from_producer_reaches_verifier(tmp_path):
    record = run_two_node_exchange(tmp_path / "run", now_iso=NOW_ISO)
    assert record["evidence"]["capability_verdict"]["contributions"] == {
        "compute": True, "verification": False,
        "encrypted_storage": False, "metadata_index": True}


def test_counters_are_honest(tmp_path):
    record = run_two_node_exchange(tmp_path / "run", now_iso=NOW_ISO)
    counts = record["evidence"]["envelopes"]
    assert counts["producer_accepted_by_verifier"] == 2
    assert counts["producer_rejected_by_verifier"] == 1


def test_fencing_token_is_monotonic(tmp_path):
    record = run_two_node_exchange(tmp_path / "run", now_iso=NOW_ISO)
    assert record["evidence"]["lease"]["fencing_token"] >= 1


def test_limits_are_stated(tmp_path):
    record = run_two_node_exchange(tmp_path / "run", now_iso=NOW_ISO)
    assert record["limits"] == list(LIMITS)
    assert "SIMULATION_IN_PROCESS != DEPLOYED_MULTI_NODE" in record["limits"]


def test_naive_iso_now_is_rejected(tmp_path):
    with pytest.raises(ScenarioError, match='timezone'):
        run_two_node_exchange(tmp_path / "run", now_iso="2026-11-24T12:00:00")


def test_garbage_now_is_rejected(tmp_path):
    with pytest.raises(ScenarioError):
        run_two_node_exchange(tmp_path / "run", now_iso="not-a-date")


def test_revoked_producer_fails_scenario_no_silent_pass(tmp_path):
    record = run_two_node_exchange(
        tmp_path / "run", now_iso=NOW_ISO, revoke_producer=True)
    assert record["status"] == STATUS_FAILED
    # Die Wire akzeptiert die Envelope (gueltige Signatur), aber der
    # Intake lehnt ab: WIRE_ACCEPTED != TRUST_ACCEPTED.
    assert record["checks"]["capability_envelope_accepted"] is True
    assert record["checks"]["capability_admitted"] is False
    assert record["evidence"]["capability_verdict"]["state"] == "REJECTED"


def test_failed_run_reports_exactly_failing_checks(tmp_path):
    record = run_two_node_exchange(
        tmp_path / "run", now_iso=NOW_ISO, revoke_producer=True)
    assert [name for name, ok in record["checks"].items() if not ok] == [
        "capability_admitted"]


def test_cli_complete_exits_zero(tmp_path):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(['--workspace', str(tmp_path / 'cli'), '--now', NOW_ISO])
    assert rc == 0, err.getvalue()
    assert json.loads(out.getvalue())['status'] == STATUS_COMPLETE


def test_cli_naive_now_exits_two(tmp_path):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(['--workspace', str(tmp_path / 'cli2'),
                   '--now', '2026-11-24T12:00:00'])
    assert rc == 2
    assert 'timezone' in err.getvalue()
