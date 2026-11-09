"""Conservative, auditable metrics for environmental and resource outcomes.

Evaluates caller-supplied measurements only. It does not fetch data, verify
publishers, authorize interventions, or claim global impact.
"""
from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any
from urllib.parse import urlparse

DOMAINS = frozenset({
    "biodiversity", "ecosystem_restoration", "peatland", "water",
    "energy", "materials", "waste", "emissions", "land_use",
})
DIRECTIONS = frozenset({"lower_is_better", "higher_is_better"})
IMPLEMENTATION_STATES = frozenset({"PLANNED", "IN_PROGRESS", "COMPLETED", "UNKNOWN"})


def _timestamp(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def evaluate_measurement(record: Any) -> dict[str, Any]:
    """Evaluate one measurement without upgrading claims into verified impact."""
    if not isinstance(record, dict):
        raise ValueError("record must be an object")
    required = ("metric_id", "domain", "indicator", "unit", "location",
                "baseline_at", "measured_at", "direction")
    for field in required:
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if record["domain"] not in DOMAINS:
        raise ValueError("domain is not recognized")
    if record["direction"] not in DIRECTIONS:
        raise ValueError("direction is not recognized")
    if len(record["indicator"]) > 240 or len(record["location"]) > 240:
        raise ValueError("indicator or location exceeds the permitted length")

    _timestamp(record["baseline_at"], "baseline_at")
    _timestamp(record["measured_at"], "measured_at")
    baseline = _number(record.get("baseline"), "baseline")
    measured = _number(record.get("measured"), "measured")
    if baseline < 0 or measured < 0:
        raise ValueError("baseline and measured values must be non-negative")

    implementation = record.get("implementation_status", "UNKNOWN")
    if implementation not in IMPLEMENTATION_STATES:
        raise ValueError("implementation_status is not recognized")

    sources = record.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources must be a list")
    publishers: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"sources[{index}] must be an object")
        publisher, url = source.get("publisher"), source.get("url")
        if not isinstance(publisher, str) or not publisher.strip():
            raise ValueError(f"sources[{index}].publisher is required")
        parsed = urlparse(url) if isinstance(url, str) else None
        if parsed is None or parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"sources[{index}].url must be HTTPS")
        publishers.add(publisher.strip().casefold())

    absolute_change = measured - baseline
    if baseline == 0:
        improvement_percent = None
    elif record["direction"] == "lower_is_better":
        improvement_percent = (baseline - measured) / baseline * 100.0
    else:
        improvement_percent = (measured - baseline) / baseline * 100.0

    if improvement_percent is None:
        outcome = "UNKNOWN"
    elif improvement_percent > 0:
        outcome = "IMPROVED"
    elif improvement_percent < 0:
        outcome = "DEGRADED"
    else:
        outcome = "NO_CHANGE"

    verification_method = record.get("verification_method")
    # Caller-provided flags and descriptions are claims, not independent proof.
    # This evaluator has no verifier identity, signature trust store, or review channel.
    verification_claim_received = record.get("independently_verified") is True
    evidence_status = (
        "CORROBORATED" if len(publishers) >= 2
        else "DOCUMENTED" if sources
        else "UNKNOWN"
    )

    return {
        "metric_id": record["metric_id"],
        "domain": record["domain"],
        "indicator": record["indicator"],
        "unit": record["unit"],
        "location": record["location"],
        "baseline": baseline,
        "measured": measured,
        "absolute_change": absolute_change,
        "improvement_percent": improvement_percent,
        "outcome": outcome,
        "implementation_status": implementation,
        "evidence_status": evidence_status,
        "verification_claim_received": verification_claim_received,
        "source_count": len(sources),
        "independent_publishers": len(publishers),
        "global_impact_claim_permitted": False,
        "limitations": [
            "A measurement is limited to its stated location, period, indicator, and unit.",
            "A URL or publisher count does not establish source authenticity or truth.",
            "Independent verification is not performed by this evaluator; caller flags and method labels remain unverified claims.",
            "No intervention, funding, restoration, or operational action is performed by this evaluator.",
        ],
    }


def evaluate_dataset(payload: Any) -> dict[str, Any]:
    """Evaluate supplied measurements; empty data remains UNKNOWN, never zero impact."""
    if not isinstance(payload, dict) or not isinstance(payload.get("measurements"), list):
        raise ValueError("dataset must contain a measurements list")
    results = [evaluate_measurement(item) for item in payload["measurements"]]
    return {
        "status": "OBSERVED" if results else "UNKNOWN",
        "scope": "supplied_measurements_only",
        "measurement_count": len(results),
        "evidence_status_counts": {
            status: sum(item["evidence_status"] == status for item in results)
            for status in ("CORROBORATED", "DOCUMENTED", "UNKNOWN")
        },
        "improved_count": sum(item["outcome"] == "IMPROVED" for item in results),
        "degraded_count": sum(item["outcome"] == "DEGRADED" for item in results),
        "global_impact_status": "UNKNOWN",
        "global_impact_total": None,
        "measurements": results,
        "network_access": False,
        "operational_actions": False,
    }
