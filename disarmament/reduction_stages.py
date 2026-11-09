"""Evidence model for lawful, independently verified weapons reduction.

This module validates records only. It does not handle weapons, inventories,
facilities, military systems, or physical dismantlement procedures.
"""
from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any
from urllib.parse import urlparse

STAGES = (
    "ANNOUNCED",
    "FUNDED",
    "CONTRACTED",
    "DECOMMISSIONING_STARTED",
    "DISMANTLED",
    "CERTIFIED_DESTROYED",
    "INDEPENDENTLY_VERIFIED",
)
CATEGORIES = frozenset({
    "nuclear", "chemical", "biological", "conventional",
    "ammunition", "autonomous_weapons", "military_production",
})
SOURCE_ROLES = frozenset({"primary_record", "independent_verifier", "corroborating"})
VERIFICATION_METHODS = frozenset({
    "treaty_verification_regime",
    "independent_on_site_inspection",
    "certified_destruction_record",
    "authenticated_inventory_reconciliation",
})


def _timestamp(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")


def _quantity(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite non-negative number")
    number = float(value)
    if not isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a finite non-negative number")
    return number


def validate_reduction_record(record: Any) -> dict[str, Any]:
    """Validate a public, non-operational reduction record without upgrading evidence."""
    if not isinstance(record, dict):
        raise ValueError("record must be an object")

    required = (
        "record_id", "category", "jurisdiction", "responsible_authority",
        "stage", "observed_at", "unit", "sources",
    )
    for field in required:
        if not isinstance(record.get(field), str if field != "sources" else list):
            raise ValueError(f"{field} has an invalid or missing type")
        if field != "sources" and not record[field].strip():
            raise ValueError(f"{field} must not be empty")

    if record["category"] not in CATEGORIES:
        raise ValueError("category is not recognized")
    if record["stage"] not in STAGES:
        raise ValueError("stage is not recognized")
    _timestamp(record["observed_at"], "observed_at")

    baseline_present = "baseline_quantity" in record
    remaining_present = "remaining_quantity" in record
    if baseline_present != remaining_present:
        raise ValueError("baseline_quantity and remaining_quantity must be supplied together")

    reduction = None
    if baseline_present:
        baseline = _quantity(record["baseline_quantity"], "baseline_quantity")
        remaining = _quantity(record["remaining_quantity"], "remaining_quantity")
        if remaining > baseline:
            raise ValueError("remaining_quantity cannot exceed baseline_quantity")
        reduction = baseline - remaining
    elif record["stage"] in {"DISMANTLED", "CERTIFIED_DESTROYED", "INDEPENDENTLY_VERIFIED"}:
        raise ValueError("completed or verified stages require a comparable baseline")

    if record["stage"] == "CERTIFIED_DESTROYED" and (
        not remaining_present or float(record["remaining_quantity"]) != 0.0
    ):
        raise ValueError("CERTIFIED_DESTROYED requires remaining_quantity equal to zero")

    sources = record["sources"]
    if not sources:
        raise ValueError("at least one public evidence source is required")
    publishers: set[str] = set()
    roles: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"sources[{index}] must be an object")
        for field in ("url", "publisher", "role"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                raise ValueError(f"sources[{index}].{field} is required")
        parsed = urlparse(source["url"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"sources[{index}].url must be HTTPS")
        if source["role"] not in SOURCE_ROLES:
            raise ValueError(f"sources[{index}].role is not recognized")
        publishers.add(source["publisher"].strip().casefold())
        roles.add(source["role"])

    if record["stage"] == "INDEPENDENTLY_VERIFIED":
        method = record.get("verification_method")
        if method not in VERIFICATION_METHODS:
            raise ValueError("independent verification requires an approved verification_method")
        if len(publishers) < 2:
            raise ValueError("independent verification requires distinct publishers")
        if not {"primary_record", "independent_verifier"}.issubset(roles):
            raise ValueError("independent verification requires primary and independent-verifier sources")
        primary_publishers = {
            item["publisher"].strip().casefold()
            for item in sources if item["role"] == "primary_record"
        }
        verifier_publishers = {
            item["publisher"].strip().casefold()
            for item in sources if item["role"] == "independent_verifier"
        }
        if primary_publishers.intersection(verifier_publishers):
            raise ValueError("the independent verifier must be a distinct publisher")

    return {
        "record_id": record["record_id"],
        "category": record["category"],
        "jurisdiction": record["jurisdiction"],
        "stage": record["stage"],
        "observed_at": record["observed_at"],
        "unit": record["unit"],
        "baseline_quantity": record.get("baseline_quantity"),
        "remaining_quantity": record.get("remaining_quantity"),
        "reduction_quantity": reduction,
        "evidence_status": (
            "INDEPENDENTLY_VERIFIED"
            if record["stage"] == "INDEPENDENTLY_VERIFIED"
            else "DOCUMENTED"
        ),
        "global_disarmament_claim_permitted": False,
        "operational_action": "NONE",
        "limitations": [
            "A validated record is not proof of worldwide disarmament or treaty compliance.",
            "A declaration, funding decision, contract, or storage move is not completed destruction.",
            "Dismantled does not mean destroyed; certified destruction requires a zero remaining quantity.",
            "Source URLs and publisher labels are provenance fields, not independent authentication.",
            "Physical handling and dismantlement remain with legally authorized, licensed specialists.",
        ],
    }
