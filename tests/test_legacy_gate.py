#!/usr/bin/env python3
"""Tests for V91 legacy transformation release gate."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from legacy_gate import evaluate_record  # noqa: E402


def _base_record():
    return {
        "change_id": "LG-001",
        "scope": "v91-core-system",
        "owner": "ops-team",
        "authorized": True,
        "irreversible": False,
        "baseline": {"cost": "known", "risk": "known"},
        "evidence": {"sources": ["audit-run-223"]},
        "legal_review": {"approved": True},
        "safety_review": {"approved": True, "independent_review": True},
        "tests": {"regression_ok": True},
        "rollback": {"documented": True},
        "seven_questions": {
            "q1": True,
            "q2": True,
            "q3": True,
            "q4": True,
            "q5": True,
            "q6": True,
            "q7": True,
        },
    }


def test_ready_when_all_requirements_are_met():
    result = evaluate_record(_base_record())
    assert result == {"decision": "READY", "reason": "AUTHORIZED_CHANGE_ALLOWED"}


def test_missing_fields_return_unknown():
    record = _base_record()
    del record["rollback"]
    result = evaluate_record(record)
    assert result["decision"] == "UNKNOWN"
    assert result["reason"] == "MISSING_FIELDS"


def test_unauthorized_change_is_rejected():
    record = _base_record()
    record["authorized"] = False
    assert evaluate_record(record) == {"decision": "REJECTED", "reason": "UNAUTHORIZED"}


def test_regression_not_proven_blocks():
    record = _base_record()
    record["tests"]["regression_ok"] = False
    assert evaluate_record(record) == {"decision": "BLOCKED", "reason": "REGRESSION_NOT_PROVEN"}


def test_failed_question_returns_needs_reform():
    record = _base_record()
    record["seven_questions"]["q5"] = False
    result = evaluate_record(record)
    assert result["decision"] == "NEEDS_REFORM"
    assert result["reason"] == "QUESTION_FAILED"
    assert result["failed_questions"] == ["q5"]


def test_irreversible_change_requires_independent_review():
    record = _base_record()
    record["irreversible"] = True
    record["safety_review"]["independent_review"] = False
    assert evaluate_record(record) == {
        "decision": "BLOCKED",
        "reason": "INDEPENDENT_REVIEW_REQUIRED",
    }
