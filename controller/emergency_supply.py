#!/usr/bin/env python3
"""
V91 emergency supply and communications readiness assessment.

This module evaluates operator-supplied evidence as REPORTED, never as
independently verified inventory. It is read-only: no actuator, shutdown,
network, webhook, ledger, or third-party notification is invoked.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "v91.emergency_supply.v1"
DEFAULT_REQUIRED_ITEMS = ("water", "food", "medical_kit", "comms_backup")
MAX_MANIFEST_BYTES = 1_048_576
DEFAULT_MAX_AGE_SECONDS = 86_400
ITEM_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
ALLOWED_STATES = {"available", "missing", "unavailable", "failed", "unknown"}


class ManifestError(ValueError):
    """Manifest or assessment configuration is invalid."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ManifestError("non_finite_json_number:" + value)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _safe_label(value: Any, limit: int = 120) -> str:
    if not isinstance(value, str):
        return "UNKNOWN"
    cleaned = " ".join("".join(
        char if char >= " " and char != "\x7f" else " " for char in value
    ).split())
    return cleaned[:limit] if cleaned else "UNKNOWN"


def _valid_item_name(value: Any) -> bool:
    return isinstance(value, str) and ITEM_NAME_RE.fullmatch(value) is not None


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load a bounded JSON manifest without following symlinks."""
    manifest_path = Path(path)
    if manifest_path.is_symlink():
        raise ManifestError("manifest_symlink_rejected")
    try:
        if not manifest_path.is_file():
            raise ManifestError("manifest_missing_or_not_regular_file")
        size = manifest_path.stat().st_size
        if size > MAX_MANIFEST_BYTES:
            raise ManifestError("manifest_too_large")
        raw = manifest_path.read_bytes()
        if len(raw) > MAX_MANIFEST_BYTES:
            raise ManifestError("manifest_too_large")
        data = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except ManifestError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError("manifest_unreadable_or_invalid:" + type(exc).__name__) from exc
    if not isinstance(data, dict):
        raise ManifestError("manifest_root_must_be_object")
    return data


def _evaluate_item(
    name: str,
    entry: Any,
    now_utc: datetime,
    max_age: timedelta,
    future_skew: timedelta,
) -> dict[str, Any]:
    base = {
        "item": name,
        "state": "UNKNOWN",
        "evidence_class": "UNKNOWN",
        "reason": "entry_missing_or_invalid",
        "source": "UNKNOWN",
        "evidence_ref": "UNKNOWN",
        "observed_at_utc": "UNKNOWN",
    }
    if not isinstance(entry, dict):
        return base

    status = entry.get("status")
    if not isinstance(status, str) or status.strip().lower() not in ALLOWED_STATES:
        return {**base, "reason": "invalid_or_unknown_status"}

    observed = _parse_timestamp(entry.get("observed_at_utc"))
    source = _safe_label(entry.get("source"), 80)
    evidence_ref = _safe_label(entry.get("evidence_ref"), 160)
    if observed is None or source == "UNKNOWN" or evidence_ref == "UNKNOWN":
        return {**base, "reason": "provenance_or_timezone_missing"}

    if observed > now_utc + future_skew:
        return {**base, "reason": "observation_in_future"}
    if now_utc - observed > max_age:
        return {**base, "reason": "observation_stale"}

    result = {
        **base,
        "evidence_class": "REPORTED",
        "source": source,
        "evidence_ref": evidence_ref,
        "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
    }
    normalized_status = status.strip().lower()
    if normalized_status == "unknown":
        return {**result, "reason": "source_reports_unknown"}

    quantity = entry.get("quantity")
    minimum = entry.get("minimum_quantity")
    if quantity is not None or minimum is not None:
        unit = entry.get("unit")
        valid_numbers = (
            isinstance(quantity, (int, float)) and not isinstance(quantity, bool)
            and math.isfinite(float(quantity)) and quantity >= 0
            and isinstance(minimum, (int, float)) and not isinstance(minimum, bool)
            and math.isfinite(float(minimum)) and minimum >= 0
            and isinstance(unit, str) and bool(unit.strip())
        )
        if not valid_numbers:
            return {**result, "reason": "quantity_minimum_or_unit_invalid"}
        if quantity < minimum:
            return {**result, "state": "MISSING", "reason": "below_reported_minimum"}

    if normalized_status in {"missing", "unavailable", "failed"}:
        return {**result, "state": "MISSING", "reason": "source_reports_missing"}
    return {**result, "state": "REPORTED_AVAILABLE", "reason": "fresh_source_report"}


def evaluate_manifest(
    manifest: dict[str, Any],
    required_items: tuple[str, ...] | list[str] = DEFAULT_REQUIRED_ITEMS,
    *,
    now: datetime | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    future_skew_seconds: int = 300,
) -> dict[str, Any]:
    """Return a deterministic, evidence-qualified readiness report."""
    if not isinstance(manifest, dict):
        raise ManifestError("manifest_root_must_be_object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError("unsupported_schema_version")
    items = manifest.get("items")
    if not isinstance(items, dict):
        raise ManifestError("items_must_be_object")
    if not isinstance(required_items, (tuple, list)) or not required_items:
        raise ManifestError("required_items_must_be_nonempty_list")
    if any(not _valid_item_name(item) for item in required_items):
        raise ManifestError("invalid_required_item_name")
    if len(set(required_items)) != len(required_items):
        raise ManifestError("duplicate_required_item")
    if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, int) or max_age_seconds < 1:
        raise ManifestError("max_age_seconds_must_be_positive_integer")
    if isinstance(future_skew_seconds, bool) or not isinstance(future_skew_seconds, int) or future_skew_seconds < 0:
        raise ManifestError("future_skew_seconds_must_be_nonnegative_integer")

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ManifestError("assessment_clock_must_be_timezone_aware")
    current = current.astimezone(timezone.utc)
    max_age = timedelta(seconds=max_age_seconds)
    future_skew = timedelta(seconds=future_skew_seconds)

    results = [
        _evaluate_item(item, items.get(item), current, max_age, future_skew)
        for item in required_items
    ]
    states = {item["state"] for item in results}
    if "MISSING" in states:
        overall = "REPORTED_MISSING"
    elif "UNKNOWN" in states:
        overall = "UNKNOWN"
    else:
        overall = "REPORTED_AVAILABLE"

    return {
        "schema_version": SCHEMA_VERSION,
        "overall_status": overall,
        "evidence_class": "REPORTED_ONLY",
        "independent_verification": "NOT_PERFORMED",
        "checked_at_utc": current.isoformat().replace("+00:00", "Z"),
        "required_count": len(results),
        "reported_available_count": sum(x["state"] == "REPORTED_AVAILABLE" for x in results),
        "missing_count": sum(x["state"] == "MISSING" for x in results),
        "unknown_count": sum(x["state"] == "UNKNOWN" for x in results),
        "items": results,
        "limitations": [
            "MANIFEST_ENTRY_IS_A_REPORT_NOT_A_PHYSICAL_SENSOR_READING",
            "REPORTED_AVAILABLE_IS_NOT_INDEPENDENTLY_VERIFIED",
            "NO_ACTUATION_NO_SHUTDOWN_NO_NETWORK_NO_WEBHOOK",
            "NO_LEDGER_WRITE_OR_WORM_CLAIM",
        ],
    }


def _parse_required(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return DEFAULT_REQUIRED_ITEMS
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not values:
        raise ManifestError("required_items_empty")
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default=os.environ.get("EMERGENCY_MANIFEST", "config/emergency_manifest.json"),
    )
    parser.add_argument(
        "--required",
        default=os.environ.get("EMERGENCY_REQUIRED_ITEMS"),
        help="Comma-separated item identifiers; defaults to water,food,medical_kit,comms_backup.",
    )
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        report = evaluate_manifest(
            manifest,
            _parse_required(args.required),
            max_age_seconds=args.max_age_seconds,
        )
    except (ManifestError, OSError) as exc:
        print(json.dumps({
            "overall_status": "UNKNOWN",
            "error": str(exc),
            "independent_verification": "NOT_PERFORMED",
        }, sort_keys=True))
        return 2

    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    return 0 if report["overall_status"] == "REPORTED_AVAILABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
