"""Evidence-first, read-only monitoring for disarmament and space security.

This package evaluates supplied public-source records. It does not fetch data,
identify operational targets, control weapons, access military networks, or
issue commands to satellites or other infrastructure.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
import re

CATEGORIES = frozenset({
    "nuclear", "chemical", "biological", "conventional",
    "autonomous_weapons", "space_security", "arms_transfers",
    "military_expenditure", "military_production", "demining",
})
OBJECT_CLASSES = frozenset({"civilian", "dual_use", "military", "unknown"})
SOURCE_TYPES = frozenset({
    "state_party", "international_body", "independent_research",
    "civil_society", "media",
})
SOURCE_ROLES = frozenset({"primary_record", "independent_verifier", "corroborating"})
VERIFICATION_METHODS = frozenset({
    "none", "public_document_review", "authenticated_inventory_reconciliation",
    "treaty_verification_regime", "independent_on_site_inspection",
    "certified_destruction_record", "independently_attested_deorbit",
})
STRONG_METHODS = frozenset({
    "authenticated_inventory_reconciliation", "treaty_verification_regime",
    "independent_on_site_inspection", "certified_destruction_record",
    "independently_attested_deorbit",
})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _iso_datetime(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc


def _validate_source(source: Any, index: int) -> None:
    if not isinstance(source, dict):
        raise ValueError(f"sources[{index}] must be an object")
    required = ("url", "publisher", "source_type", "role", "retrieved_at", "sha256")
    missing = [field for field in required if not source.get(field)]
    if missing:
        raise ValueError(f"sources[{index}] missing: {', '.join(missing)}")
    parsed = urlparse(source["url"])
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"sources[{index}].url must be an HTTPS URL")
    if source["source_type"] not in SOURCE_TYPES:
        raise ValueError(f"sources[{index}].source_type is not recognized")
    if source["role"] not in SOURCE_ROLES:
        raise ValueError(f"sources[{index}].role is not recognized")
    if not isinstance(source["publisher"], str) or len(source["publisher"]) > 160:
        raise ValueError(f"sources[{index}].publisher is invalid")
    _iso_datetime(source["retrieved_at"], f"sources[{index}].retrieved_at")
    if not isinstance(source["sha256"], str) or not SHA256_RE.fullmatch(source["sha256"]):
        raise ValueError(f"sources[{index}].sha256 must be a lowercase SHA-256 hex digest")


def evaluate_record(record: Any) -> dict[str, Any]:
    """Validate one public-source record and assign a conservative evidence grade."""
    if not isinstance(record, dict):
        raise ValueError("record must be an object")
    for field in ("record_id", "category", "claim", "scope", "observed_at"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if record["category"] not in CATEGORIES:
        raise ValueError("category is not recognized")
    if len(record["claim"]) > 2000 or len(record["scope"]) > 300:
        raise ValueError("claim or scope exceeds the permitted length")
    _iso_datetime(record["observed_at"], "observed_at")

    object_class = record.get("space_object_class", "unknown")
    if object_class not in OBJECT_CLASSES:
        raise ValueError("space_object_class is not recognized")
    method = record.get("verification_method", "none")
    if method not in VERIFICATION_METHODS:
        raise ValueError("verification_method is not recognized")

    sources = record.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources must be a list")
    for index, source in enumerate(sources):
        _validate_source(source, index)

    publishers = {source["publisher"].strip().casefold() for source in sources}
    roles = {source["role"] for source in sources}
    hashes_present = all(bool(source.get("sha256")) for source in sources)
    if not sources:
        grade = "UNKNOWN"
    elif (
        method in STRONG_METHODS
        and len(publishers) >= 2
        and "primary_record" in roles
        and "independent_verifier" in roles
        and hashes_present
    ):
        grade = "VERIFIED"
    elif len(publishers) >= 2:
        grade = "CORROBORATED"
    else:
        grade = "DOCUMENTED"

    return {
        "record_id": record["record_id"],
        "category": record["category"],
        "scope": record["scope"],
        "evidence_grade": grade,
        "source_count": len(sources),
        "independent_publishers": len(publishers),
        "verification_method": method,
        "space_object_class": object_class,
        "global_claim_permitted": False,
        "operational_action": "NONE",
        "limitations": [
            "A source hash protects the recorded bytes, not the truth of the claim.",
            "A record-level grade is not proof of worldwide compliance or disarmament.",
            "No weapon, military network, satellite, or third-party system is controlled.",
        ],
    }


def evaluate_dataset(payload: Any) -> dict[str, Any]:
    """Evaluate a local JSON-compatible dataset without network access."""
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("dataset must be an object containing a records list")
    results = [evaluate_record(record) for record in payload["records"]]
    counts = Counter(item["evidence_grade"] for item in results)
    return {
        "status": "OBSERVED" if results else "UNKNOWN",
        "scope": "supplied_records_only",
        "record_count": len(results),
        "evidence_counts": {grade: counts.get(grade, 0)
                            for grade in ("VERIFIED", "CORROBORATED", "DOCUMENTED", "UNKNOWN")},
        "global_disarmament_status": "UNKNOWN",
        "global_inventory_total": None,
        "records": results,
        "network_access": False,
        "operational_controls": False,
    }
