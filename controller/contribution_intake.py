"""Validate transport-neutral V91 contribution envelopes.

This module validates structure only. It does not authenticate an origin,
verify evidence, grant authorization, store submissions, or execute content.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

PROTOCOL = "V91-CONTRIBUTION-1"
MAX_DOCUMENT_BYTES = 65536
MAX_ITEMS = 64
MAX_TEXT = 4096
MAX_CHANGE = 16384

CONTRIBUTION_STATUSES = frozenset({
    "RECEIVED",
    "TRIAGED",
    "TESTING",
    "ACCEPTED",
    "INTEGRATED",
    "REJECTED",
    "DEFERRED",
})
EVIDENCE_STATUSES = frozenset({
    "UNKNOWN",
    "DOCUMENTED",
    "IMPLEMENTED",
    "TESTED",
    "VERIFIED",
    "AUDITED",
    "PRODUCTION",
})

_REQUIRED = frozenset({
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
})
_ALLOWED = _REQUIRED


def _object(
    value: Any,
    path: str,
    allowed: set[str] | frozenset[str],
    required: set[str] | frozenset[str],
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return None
    if any(not isinstance(key, str) for key in value):
        errors.append(f"{path}: object keys must be strings")
    missing = sorted(required - set(value))
    unknown = sorted(str(key) for key in set(value) - set(allowed))
    if missing:
        errors.append(f"{path}: missing fields {missing}")
    if unknown:
        errors.append(f"{path}: unknown fields {unknown}")
    return value


def _text(
    value: Any,
    path: str,
    errors: list[str],
    maximum: int = MAX_TEXT,
) -> None:
    if not isinstance(value, str):
        errors.append(f"{path}: must be a string")
    elif not value.strip():
        errors.append(f"{path}: must not be empty")
    elif len(value) > maximum:
        errors.append(f"{path}: exceeds {maximum} characters")


def _string_list(
    value: Any,
    path: str,
    errors: list[str],
    *,
    maximum_items: int = MAX_ITEMS,
) -> None:
    if not isinstance(value, list):
        errors.append(f"{path}: must be a list")
        return
    if len(value) > maximum_items:
        errors.append(f"{path}: exceeds {maximum_items} items")
    for index, item in enumerate(value):
        _text(item, f"{path}[{index}]", errors)


def _timestamp(value: Any, path: str, errors: list[str]) -> None:
    _text(value, path, errors, maximum=64)
    if not isinstance(value, str) or not value.strip():
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{path}: must be an ISO-8601 timestamp")
        return
    if parsed.tzinfo is None:
        errors.append(f"{path}: timezone is required")


def validate_contribution(payload: Any) -> tuple[bool, list[str]]:
    """Validate one envelope; a valid result means eligible for triage only."""
    errors: list[str] = []
    root = _object(payload, "root", _ALLOWED, _REQUIRED, errors)
    if root is None:
        return False, errors

    if root.get("protocol") != PROTOCOL:
        errors.append(f"protocol: must equal {PROTOCOL!r}")
    _text(root.get("contribution_id"), "contribution_id", errors, maximum=128)
    _text(root.get("goal"), "goal", errors)
    _text(root.get("proposed_change"), "proposed_change", errors, maximum=MAX_CHANGE)
    _text(root.get("next_action"), "next_action", errors)

    origin = _object(
        root.get("origin"),
        "origin",
        {"model_or_person", "provider", "session_or_date"},
        {"model_or_person"},
        errors,
    )
    if origin is not None:
        _text(origin.get("model_or_person"), "origin.model_or_person", errors)
        for key in ("provider", "session_or_date"):
            if key in origin:
                _text(origin[key], f"origin.{key}", errors)

    scope = _object(
        root.get("scope"),
        "scope",
        {"systems", "allowed_paths", "excluded_actions"},
        {"systems"},
        errors,
    )
    if scope is not None:
        _string_list(scope.get("systems"), "scope.systems", errors)
        for key in ("allowed_paths", "excluded_actions"):
            if key in scope:
                _string_list(scope[key], f"scope.{key}", errors)

    provenance = root.get("inputs_and_provenance")
    if not isinstance(provenance, list):
        errors.append("inputs_and_provenance: must be a list")
    else:
        if len(provenance) > MAX_ITEMS:
            errors.append(f"inputs_and_provenance: exceeds {MAX_ITEMS} items")
        for index, item in enumerate(provenance):
            path = f"inputs_and_provenance[{index}]"
            entry = _object(
                item,
                path,
                {"reference", "description", "source", "retrieved_at"},
                {"reference", "description"},
                errors,
            )
            if entry is not None:
                _text(entry.get("reference"), f"{path}.reference", errors)
                _text(entry.get("description"), f"{path}.description", errors)
                if "source" in entry:
                    _text(entry["source"], f"{path}.source", errors)
                if "retrieved_at" in entry:
                    _timestamp(entry["retrieved_at"], f"{path}.retrieved_at", errors)

    interfaces = _object(
        root.get("interfaces"),
        "interfaces",
        {"inputs", "outputs"},
        {"inputs", "outputs"},
        errors,
    )
    if interfaces is not None:
        _string_list(interfaces.get("inputs"), "interfaces.inputs", errors)
        _string_list(interfaces.get("outputs"), "interfaces.outputs", errors)

    evidence = root.get("tests_and_evidence")
    if not isinstance(evidence, list):
        errors.append("tests_and_evidence: must be a list")
    else:
        if len(evidence) > MAX_ITEMS:
            errors.append(f"tests_and_evidence: exceeds {MAX_ITEMS} items")
        for index, item in enumerate(evidence):
            path = f"tests_and_evidence[{index}]"
            entry = _object(
                item,
                path,
                {"reference", "description", "status", "scope"},
                {"reference", "description", "status"},
                errors,
            )
            if entry is not None:
                _text(entry.get("reference"), f"{path}.reference", errors)
                _text(entry.get("description"), f"{path}.description", errors)
                if entry.get("status") not in EVIDENCE_STATUSES:
                    errors.append(
                        f"{path}.status: must use the V91-COMMS-1 evidence status chain"
                    )
                if "scope" in entry:
                    _text(entry["scope"], f"{path}.scope", errors)

    _string_list(root.get("known_limits"), "known_limits", errors)
    _string_list(
        root.get("security_privacy_notes"),
        "security_privacy_notes",
        errors,
    )

    if root.get("status") not in CONTRIBUTION_STATUSES:
        errors.append("status: unsupported contribution workflow status")

    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        errors.append("root: must contain JSON-compatible values")
    else:
        if len(encoded) > MAX_DOCUMENT_BYTES:
            errors.append(f"root: exceeds {MAX_DOCUMENT_BYTES} encoded bytes")

    return not errors, errors


def inspect_contribution(payload: Any) -> dict[str, Any]:
    """Return a bounded intake verdict without promoting claims or granting rights."""
    valid, errors = validate_contribution(payload)
    is_object = isinstance(payload, dict)
    evidence = payload.get("tests_and_evidence") if is_object else None
    return {
        "valid": valid,
        "eligible_for_triage": valid,
        "contribution_id": payload.get("contribution_id") if is_object else None,
        "claimed_status": payload.get("status") if is_object else None,
        "evidence_present": isinstance(evidence, list) and bool(evidence),
        "authorization": "NOT_GRANTED",
        "execution": "NOT_PERFORMED",
        "errors": errors,
    }
