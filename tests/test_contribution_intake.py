from __future__ import annotations

import copy
import json
from pathlib import Path

from controller.contribution_intake import (
    inspect_contribution,
    validate_contribution,
)


def _valid_contribution() -> dict:
    return {
        "protocol": "V91-CONTRIBUTION-1",
        "contribution_id": "example-2026-11-26-001",
        "origin": {
            "model_or_person": "example contributor",
            "provider": "example provider",
            "session_or_date": "2026-11-26",
        },
        "goal": "Improve a bounded, reviewable capability.",
        "scope": {
            "systems": ["guenny9000/v91-core-system"],
            "allowed_paths": ["controller/example.py", "tests/test_example.py"],
            "excluded_actions": ["merge", "deploy", "delete"],
        },
        "inputs_and_provenance": [
            {
                "reference": "https://example.invalid/spec",
                "description": "Synthetic specification reference.",
                "source": "synthetic fixture",
                "retrieved_at": "2026-11-26T06:00:00Z",
            }
        ],
        "proposed_change": "Add a small, isolated validation improvement.",
        "interfaces": {
            "inputs": ["JSON contribution envelope"],
            "outputs": ["validation verdict"],
        },
        "tests_and_evidence": [
            {
                "reference": "tests/test_example.py",
                "description": "Synthetic fixture test.",
                "status": "DOCUMENTED",
                "scope": "synthetic test data only",
            }
        ],
        "known_limits": ["No identity or source verification."],
        "security_privacy_notes": ["No secrets or personal data included."],
        "status": "RECEIVED",
        "next_action": "Independent triage.",
    }


def test_valid_envelope_is_only_eligible_for_triage():
    verdict = inspect_contribution(_valid_contribution())
    assert verdict["valid"] is True
    assert verdict["eligible_for_triage"] is True
    assert verdict["authorization"] == "NOT_GRANTED"
    assert verdict["execution"] == "NOT_PERFORMED"


def test_missing_required_field_is_rejected():
    payload = _valid_contribution()
    del payload["goal"]
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("goal" in error for error in errors)


def test_unknown_top_level_field_is_rejected():
    payload = _valid_contribution()
    payload["operator_override"] = True
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("unknown fields" in error for error in errors)


def test_wrong_protocol_is_rejected():
    payload = _valid_contribution()
    payload["protocol"] = "V91-COMMS-1"
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("protocol" in error for error in errors)


def test_invalid_contribution_status_is_rejected():
    payload = _valid_contribution()
    payload["status"] = "PASS"
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("workflow status" in error for error in errors)


def test_evidence_status_reuses_comms_status_chain():
    payload = _valid_contribution()
    payload["tests_and_evidence"][0]["status"] = "PASS"
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("V91-COMMS-1" in error for error in errors)


def test_timezone_is_required_for_retrieval_timestamp():
    payload = _valid_contribution()
    payload["inputs_and_provenance"][0]["retrieved_at"] = "2026-11-26T06:00:00"
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("timezone is required" in error for error in errors)


def test_empty_evidence_is_not_misreported_as_present():
    payload = _valid_contribution()
    payload["tests_and_evidence"] = []
    verdict = inspect_contribution(payload)
    assert verdict["valid"] is True
    assert verdict["evidence_present"] is False
    assert verdict["authorization"] == "NOT_GRANTED"


def test_self_reported_integrated_status_grants_no_rights():
    payload = _valid_contribution()
    payload["status"] = "INTEGRATED"
    verdict = inspect_contribution(payload)
    assert verdict["valid"] is True
    assert verdict["claimed_status"] == "INTEGRATED"
    assert verdict["authorization"] == "NOT_GRANTED"
    assert verdict["execution"] == "NOT_PERFORMED"


def test_nested_unknown_fields_are_rejected():
    payload = _valid_contribution()
    payload["origin"]["trusted"] = True
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("origin: unknown fields" in error for error in errors)


def test_document_size_is_bounded():
    payload = _valid_contribution()
    payload["proposed_change"] = "x" * 16384
    payload["known_limits"] = ["y" * 4096] * 64
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("encoded bytes" in error for error in errors)


def test_non_json_values_are_rejected():
    payload = _valid_contribution()
    payload["known_limits"] = [object()]
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("JSON-compatible" in error for error in errors)


def test_validation_does_not_mutate_input():
    payload = _valid_contribution()
    before = copy.deepcopy(payload)
    validate_contribution(payload)
    assert payload == before


def test_schema_required_fields_match_validator_contract():
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "contribution.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["properties"]["protocol"]["const"] == "V91-CONTRIBUTION-1"
    assert set(schema["required"]) == {
        "protocol",
        "contribution_id",
        "origin",
        "goal",
        "scope",
        "inputs_and_provenance",
        "proposed_change",
        "interfaces",
        "tests_and_evidence",
        "known_limits",
        "security_privacy_notes",
        "status",
        "next_action",
    }


def test_unhashable_status_values_are_rejected_without_crashing():
    payload = _valid_contribution()
    payload["status"] = {"unexpected": "object"}
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("workflow status" in error for error in errors)

    payload = _valid_contribution()
    payload["tests_and_evidence"][0]["status"] = ["not", "a", "status"]
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("V91-COMMS-1" in error for error in errors)


def test_license_claim_is_structural_metadata_only():
    payload = _valid_contribution()
    payload["inputs_and_provenance"][0]["license"] = "UNKNOWN"
    valid, errors = validate_contribution(payload)
    assert valid is True
    assert errors == []


def test_non_string_license_claim_is_rejected():
    payload = _valid_contribution()
    payload["inputs_and_provenance"][0]["license"] = False
    valid, errors = validate_contribution(payload)
    assert valid is False
    assert any("license" in error for error in errors)
