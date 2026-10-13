import pytest

from v91_state_check import validate_telemetry_entry


def test_documented_local_entry_can_pass_structural_validation():
    ok, errors = validate_telemetry_entry({
        "state": "DOKUMENTIERT",
        "storage_type": "LOCAL_GIT",
        "eco_impact_data": "UNKNOWN",
    })
    assert ok is True
    assert errors == []


@pytest.mark.parametrize("state", ["VERIFIZIERT", "PRODUKTIV"])
def test_verified_or_productive_requires_evidence_id(state):
    ok, errors = validate_telemetry_entry({"state": state})
    assert ok is False
    assert any("evidence_log_id" in error for error in errors)


def test_worm_without_external_anchor_fails_closed():
    ok, errors = validate_telemetry_entry({
        "state": "DOKUMENTIERT",
        "storage_type": "WORM",
        "guideline_hash_sha256": "a" * 64,
    })
    assert ok is False
    assert any("WORM requires external_anchor" in error for error in errors)


def test_hash_shape_is_checked_but_not_treated_as_worm_proof():
    ok, errors = validate_telemetry_entry({
        "state": "DOKUMENTIERT",
        "storage_type": "LOCAL_GIT",
        "guideline_hash_sha256": "not-a-sha256",
    })
    assert ok is False
    assert any("64 lowercase hexadecimal" in error for error in errors)


def test_measured_ecology_requires_traceable_measurements():
    ok, errors = validate_telemetry_entry({
        "state": "VERIFIZIERT",
        "evidence_log_id": "run-123",
        "eco_impact_data": "MEASURED",
        "ecological_measurements": [],
    })
    assert ok is False
    assert any("measurement list" in error for error in errors)


def test_hash_alone_does_not_block_unknown_ecology():
    ok, errors = validate_telemetry_entry({
        "state": "DOKUMENTIERT",
        "storage_type": "LOCAL_GIT",
        "guideline_hash_sha256": "a" * 64,
        "eco_impact_data": "UNKNOWN",
    })
    assert ok is True
    assert errors == []


def test_non_object_fails_closed():
    ok, errors = validate_telemetry_entry([])
    assert ok is False
    assert errors == ["entry must be a JSON object"]
