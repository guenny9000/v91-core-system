"""Isolated tests for the evidence-only global status snapshot.

These tests validate the artifact's claims; they do not measure global or local
system state and must never be treated as a production health check.
"""
import json
from pathlib import Path


def test_global_status_fails_closed_without_evidence():
    status = json.loads(
        Path("global-status.json").read_text(encoding="utf-8")
    )
    assert status["schema_version"] == 1
    assert status["status"] == "UNKNOWN"
    assert status["valid"] is False
    assert status["evidence"] == []
    assert status["timestamp_utc"] is None


def test_unmeasured_global_claims_remain_unknown():
    status = json.loads(
        Path("global-status.json").read_text(encoding="utf-8")
    )
    claims = status["claims"]
    assert claims
    assert all(value == "UNKNOWN" for value in claims.values())


def test_status_artifact_explicitly_disclaims_global_or_production_certification():
    status = json.loads(
        Path("global-status.json").read_text(encoding="utf-8")
    )
    reason = status["reason"].lower()
    assert "unknown is not zero" in reason
    assert "does not certify global, local, or production state" in reason
