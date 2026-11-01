#!/usr/bin/env python3
"""V91 legacy transformation release gate (documentation/evidence checker)."""

import json
from typing import Any

REQUIRED_QUESTIONS = ("q1", "q2", "q3", "q4", "q5", "q6", "q7")


def _missing(container: dict[str, Any], required: tuple[str, ...]) -> list[str]:
    return [k for k in required if k not in container]


def evaluate_record(record: dict[str, Any]) -> dict[str, Any]:
    """Evaluate whether a change record is complete enough for authorized change."""
    missing_top = _missing(
        record,
        (
            "change_id",
            "scope",
            "owner",
            "authorized",
            "irreversible",
            "baseline",
            "evidence",
            "legal_review",
            "safety_review",
            "tests",
            "rollback",
            "seven_questions",
        ),
    )
    if missing_top:
        return {
            "decision": "UNKNOWN",
            "reason": "MISSING_FIELDS",
            "missing_fields": missing_top,
        }

    questions = record["seven_questions"]
    if not isinstance(questions, dict):
        return {
            "decision": "UNKNOWN",
            "reason": "INVALID_QUESTIONS",
            "missing_fields": list(REQUIRED_QUESTIONS),
        }
    missing_questions = _missing(questions, REQUIRED_QUESTIONS)
    if missing_questions:
        return {
            "decision": "UNKNOWN",
            "reason": "MISSING_QUESTIONS",
            "missing_fields": missing_questions,
        }

    if record["authorized"] is not True:
        return {"decision": "REJECTED", "reason": "UNAUTHORIZED"}

    tests = record["tests"]
    if not isinstance(tests, dict) or tests.get("regression_ok") is not True:
        return {"decision": "BLOCKED", "reason": "REGRESSION_NOT_PROVEN"}

    legal = record["legal_review"]
    safety = record["safety_review"]
    rollback = record["rollback"]
    if not isinstance(legal, dict) or legal.get("approved") is not True:
        return {"decision": "BLOCKED", "reason": "LEGAL_REVIEW_MISSING"}
    if not isinstance(safety, dict) or safety.get("approved") is not True:
        return {"decision": "BLOCKED", "reason": "SAFETY_REVIEW_MISSING"}
    if not isinstance(rollback, dict) or rollback.get("documented") is not True:
        return {"decision": "BLOCKED", "reason": "ROLLBACK_MISSING"}

    if record["irreversible"] is True and safety.get("independent_review") is not True:
        return {"decision": "BLOCKED", "reason": "INDEPENDENT_REVIEW_REQUIRED"}

    failed_questions = [q for q in REQUIRED_QUESTIONS if questions.get(q) is not True]
    if failed_questions:
        return {
            "decision": "NEEDS_REFORM",
            "reason": "QUESTION_FAILED",
            "failed_questions": failed_questions,
        }

    return {"decision": "READY", "reason": "AUTHORIZED_CHANGE_ALLOWED"}


def load_record(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("record must be a JSON object")
    return data
