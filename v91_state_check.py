"""Fail-closed validation for V91 status and evidence claims.

A valid entry means its structure passed these checks; it does not independently
prove that the referenced evidence exists or that the claimed state is true.
"""
from __future__ import annotations

import re
from typing import Any

ALLOWED_STATES = {
    "UNBEKANNT",
    "DOKUMENTIERT",
    "IMPLEMENTIERT",
    "VERIFIZIERT",
    "PRODUKTIV",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_telemetry_entry(entry: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return False, ["entry must be a JSON object"]

    state = entry.get("state")
    if state not in ALLOWED_STATES:
        errors.append(f"invalid state: {state!r}")

    evidence_id = entry.get("evidence_log_id")
    if state in {"VERIFIZIERT", "PRODUKTIV"} and (
        not isinstance(evidence_id, str) or not evidence_id.strip()
    ):
        errors.append(f"{state} requires a non-empty evidence_log_id")

    storage_type = entry.get("storage_type")
    if storage_type == "WORM":
        anchor = entry.get("external_anchor")
        if not isinstance(anchor, dict) or not all(
            isinstance(anchor.get(k), str) and anchor[k].strip()
            for k in ("provider", "reference", "verification_method")
        ):
            errors.append(
                "WORM requires external_anchor with provider, reference, "
                "and verification_method; a hash alone is not WORM proof"
            )

    claimed_hash = entry.get("guideline_hash_sha256")
    if claimed_hash is not None and (
        not isinstance(claimed_hash, str) or not SHA256_RE.fullmatch(claimed_hash)
    ):
        errors.append("guideline_hash_sha256 must be 64 lowercase hexadecimal characters")

    if entry.get("eco_impact_data") == "MEASURED":
        measurements = entry.get("ecological_measurements")
        if not isinstance(measurements, list) or not measurements:
            errors.append("MEASURED eco impact requires a non-empty measurement list")
        else:
            for index, measurement in enumerate(measurements):
                if not isinstance(measurement, dict) or not all(
                    isinstance(measurement.get(k), str) and measurement[k].strip()
                    for k in ("metric", "value", "unit", "source", "timestamp_utc")
                ):
                    errors.append(
                        f"ecological_measurements[{index}] requires metric, value, "
                        "unit, source, and timestamp_utc strings"
                    )

    return not errors, errors
