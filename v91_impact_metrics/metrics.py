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


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc
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

    baseline_at = _timestamp(record["baseline_at"], "baseline_at")
    measured_at = _timestamp(record["measured_at"], "measured_at")
    if measured_at < baseline_at:
        raise ValueError("measured_at must not precede baseline_at")

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
    if improvement_percent is not None and not isfinite(improvement_percent):
        raise ValueError("improvement percentage exceeds the supported finite range")

    if improvement_percent is None:
        outcome = "UNKNOWN"
    elif improvement_percent > 0:
        outcome = "IMPROVED"
    elif improvement_percent < 0:
        outcome = "DEGRADED"
    else:
        outcome = "NO_CHANGE"

    # Caller-provided flags and descriptions are claims, not independent proof.
    # This evaluator has no verifier identity, signature trust store, or review channel.
    verification_claim_received = record.get("independently_verified") is True
    # Distinct caller-supplied publisher labels are metadata, not proof of
    # independent sources. Without source authentication or an external review,
    # supplied references can be documented but cannot be marked corroborated.
    evidence_status = "DOCUMENTED" if sources else "UNKNOWN"

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
            "A URL or publisher-label count does not establish source authenticity, publisher independence, or truth.",
            "The independent_publishers field counts distinct caller-supplied labels only; it does not verify independent publisher identities.",
            "Independent verification is not performed by this evaluator; caller flags and method labels remain unverified claims.",
            "No intervention, funding, restoration, or operational action is performed by this evaluator.",
        ],
    }


# ---------------------------------------------------------------------------
# Messmatrix v1.0 (Global Impact Engine, standard agreed 2026-11-20):
# every initiative needs per indicator a baseline, target, measurement
# period, method, responsible verifier, uncertainty band and, for Wirkung
# indicators, a comparison with a suitable alternative. Matrix metadata are
# claims until independently checked; a target value is not an outcome.
# ---------------------------------------------------------------------------
WATCHERS = frozenset({
    "wasser", "energie", "ernaehrung", "gesundheit", "natur", "frieden",
    "technologie",
})
MATURITY_LEVELS = frozenset({
    "R0", "R1", "R2", "R3", "R4", "R5", "R6",
})
INDICATOR_ROLES = frozenset({"WIRKUNG", "KOSTEN", "RESILIENZ"})


def _non_empty_string(value: Any, field: str, limit: int = 240) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    if len(value) > limit:
        raise ValueError(f"{field} exceeds the permitted length")
    return value


def evaluate_messmatrix(record: Any) -> dict[str, Any]:
    """Validate a Messmatrix v1.0 record (claims only, never proof of impact).

    A record describes one initiative: watcher domain, maturity R0-R6 and
    at least one WIRKUNG, one KOSTEN and one RESILIENZ indicator, each with
    baseline, target, period, method, verifier, uncertainty and (WIRKUNG)
    an alternative comparison. Fail-closed on any missing obligation.
    """
    if not isinstance(record, dict):
        raise ValueError("record must be an object")
    _non_empty_string(record.get("initiative_id"), "initiative_id")
    _non_empty_string(record.get("description"), "description")
    watcher = record.get("watcher")
    if watcher not in WATCHERS:
        raise ValueError("watcher is not recognized")
    maturity = record.get("maturity")
    if maturity not in MATURITY_LEVELS:
        raise ValueError("maturity must be one of R0-R6")

    indicators = record.get("indicators")
    if not isinstance(indicators, list) or not indicators:
        raise ValueError("indicators must be a non-empty list")
    seen_roles: set[str] = set()
    for index, entry in enumerate(indicators):
        prefix = f"indicators[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{prefix} must be an object")
        role = entry.get("role")
        if role not in INDICATOR_ROLES:
            raise ValueError(f"{prefix}.role must be WIRKUNG, KOSTEN or RESILIENZ")
        seen_roles.add(role)
        _non_empty_string(entry.get("name"), f"{prefix}.name")
        _non_empty_string(entry.get("unit"), f"{prefix}.unit")
        _number(entry.get("baseline"), f"{prefix}.baseline")
        _number(entry.get("target"), f"{prefix}.target")
        if entry["baseline"] < 0 or entry["target"] < 0:
            raise ValueError(f"{prefix}.baseline and target must be non-negative")
        period = entry.get("period")
        if not isinstance(period, dict):
            raise ValueError(f"{prefix}.period must be an object")
        baseline_at = _timestamp(period.get("baseline_at"), f"{prefix}.period.baseline_at")
        target_at = _timestamp(period.get("target_at"), f"{prefix}.period.target_at")
        if target_at < baseline_at:
            raise ValueError(f"{prefix}.period.target_at must not precede baseline_at")
        _non_empty_string(entry.get("method"), f"{prefix}.method")
        _non_empty_string(entry.get("verifier"), f"{prefix}.verifier")
        uncertainty = _number(entry.get("uncertainty"), f"{prefix}.uncertainty")
        if uncertainty < 0:
            raise ValueError(f"{prefix}.uncertainty must be non-negative")
        if role == "WIRKUNG":
            _non_empty_string(entry.get("alternative_comparison"),
                              f"{prefix}.alternative_comparison")

    missing_roles = sorted(INDICATOR_ROLES - seen_roles)
    if missing_roles:
        raise ValueError(
            "Messmatrix v1.0 requires at least one WIRKUNG, KOSTEN and "
            f"RESILIENZ indicator; missing: {missing_roles}")

    multiplier = None
    multiplier_input = record.get("multiplier")
    if multiplier_input is not None:
        if not isinstance(multiplier_input, dict):
            raise ValueError("multiplier must be an object")
        added_benefit = _number(multiplier_input.get("added_benefit"),
                                "multiplier.added_benefit")
        added_effort = _number(multiplier_input.get("added_effort"),
                               "multiplier.added_effort")
        if added_benefit < 0 or added_effort <= 0:
            raise ValueError(
                "multiplier.added_benefit must be non-negative and "
                "multiplier.added_effort must be positive")
        multiplier = added_benefit / added_effort
        if not isfinite(multiplier):
            raise ValueError("multiplier exceeds the supported finite range")

    return {
        "initiative_id": record["initiative_id"],
        "watcher": watcher,
        "maturity": maturity,
        "indicator_count": len(indicators),
        "roles_covered": sorted(seen_roles),
        "multiplier": multiplier,
        "multiplier_status": "MODELED" if multiplier is not None else "UNKNOWN",
        "matrix_status": "MASSE_BESCHRIEBEN",
        "impact_claim_permitted": False,
        "limitations": [
            "MATRIZ != WIRKUNG; an indicator definition is not a measured outcome.",
            "ZIELWERT != ERGEBNIS; targets are obligations, never results.",
            "Method and verifier labels are caller-supplied claims, not verified identities.",
            "A multiplier is a modeled ratio, not evidence of achieved benefit.",
            "UNKNOWN stays UNKNOWN; this evaluator performs independent verification nowhere.",
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
