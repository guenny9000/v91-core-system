#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Operator measurement entry (Issue #101 operator tooling; builds on
measurement_ingest.py and measurement_store.py, Issues #100/#113).

Purpose: let the operator record real measurements WITHOUT editing
code (zero-code entry), and import measurement files from other
nodes. Every entry - manual or imported - goes through the SAME
fail-closed validation and the SAME hash-chained, HMAC-signed
append-only store as sensor feeds.

Reuse (NO_DUPLICATE_SYSTEMS): there is no second register, no second
validation path and no parallel JSON store here. Validation is
delegated to measurement_ingest.validate_measurement; persistence is
delegated to MeasurementStore.record_valid / MeasurementStore.quarantine.

Fail-closed rules:
- the operator must declare the plausibility window (minimum/maximum)
  and unit per call; ranges are never guessed
- timestamps are timezone-aware; an undeclared source time falls back
  to receive time in UTC (recorded as such, never backdated silently)
- invalid input is quarantined verbatim (raw payload preserved,
  reason recorded); nothing is discarded, repaired or interpolated
- a corrupt store chain refuses further appends (delegated fail-closed)

Honest limits: IMPORTED != VERIFIED_ORIGIN - importing another node's
file validates structure and plausibility but cannot prove who
produced the data; origin authentication is separate signed-heartbeat
work (Issue #37). SOURCE != WITNESS. This module is a library, not an
interactive menu and not a network client.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from controller.measurement_ingest import (
    MeasurementStatus,
    RawMeasurement,
    SensorSpec,
    validate_measurement,
)
from controller.measurement_store import MeasurementStore

DEFAULT_SOURCE = "operator-manual"


class OperatorEntryError(ValueError):
    """Fail-closed operator-entry error (bad call or unusable import file)."""


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _raw_payload(measurement: RawMeasurement) -> dict[str, Any]:
    return {
        "sensor_id": measurement.sensor_id,
        "metric": measurement.metric,
        "value": measurement.value,
        "unit": measurement.unit,
        "timestamp": measurement.timestamp,
        "source": measurement.source,
    }


def record_measurement(
    *,
    store: MeasurementStore,
    sensor_id: str,
    metric: str,
    value: Any,
    unit: str,
    minimum: float,
    maximum: float,
    timestamp: str | None = None,
    source: str = DEFAULT_SOURCE,
) -> dict[str, Any]:
    """Validate one measurement and persist it in the shared store.

    Returns a status dict. Valid input is recorded as MEASUREMENT_VALID;
    every other outcome is quarantined verbatim with the failure reason.
    Nothing is executed, uploaded or inferred here.
    """
    spec = SensorSpec(metric=metric, unit=unit, minimum=minimum, maximum=maximum)
    claimed = timestamp.strip() if isinstance(timestamp, str) and timestamp.strip() else None
    raw = RawMeasurement(
        sensor_id=sensor_id if isinstance(sensor_id, str) else "",
        metric=metric if isinstance(metric, str) else "",
        value=value,
        unit=unit if isinstance(unit, str) else "",
        timestamp=claimed if claimed is not None else _now_utc_iso(),
        source=source if isinstance(source, str) and source.strip() else DEFAULT_SOURCE,
    )
    verdict = validate_measurement(raw, {raw.metric if isinstance(metric, str) else "": spec})

    if verdict.status is MeasurementStatus.VALID and verdict.normalized_value is not None:
        record = store.record_valid(
            sensor_id=raw.sensor_id,
            metric=raw.metric,
            normalized_value=verdict.normalized_value,
            unit=raw.unit,
            timestamp_utc=verdict.timestamp_utc or raw.timestamp,
            source=raw.source,
        )
        return {
            "status": "RECORDED",
            "seq": record["seq"],
            "entry_hash": record["entry_hash"],
            "source_time_utc": record["source_time_utc"],
            "warnings": list(verdict.warnings),
        }

    reason = "; ".join(verdict.errors) if verdict.errors else "validation failed"
    quarantine = store.quarantine(
        _raw_payload(raw),
        reason=f"operator-entry: {reason}",
        claimed_source_time=claimed,
    )
    return {
        "status": "QUARANTINED",
        "seq": quarantine["seq"],
        "entry_hash": quarantine["entry_hash"],
        "reason": reason,
    }


def import_foreign_file(
    *,
    store: MeasurementStore,
    path: Path | str,
    metric: str,
    unit: str,
    minimum: float,
    maximum: float,
    source_tag: str,
) -> dict[str, Any]:
    """Import another node's measurement file through the shared gate.

    Every item is validated with the SAME rules as manual entry, using
    the operator-declared plausibility window for the declared metric.
    Items that do not match the declared metric/unit are quarantined,
    not skipped. IMPORTED != VERIFIED_ORIGIN: the file's bytes are
    unauthenticated; provenance is recorded as import provenance only.
    """
    if not isinstance(source_tag, str) or not source_tag.strip():
        raise OperatorEntryError("source_tag must be a non-empty string")
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OperatorEntryError(f"import file unreadable: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OperatorEntryError(f"import file is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise OperatorEntryError("import file must contain a JSON list of entries")

    import_source = f"import:{source_tag.strip()}"
    recorded = 0
    quarantined = 0
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            quarantined += 1
            store.quarantine(
                {"import_index": index, "item": item, "import_file": file_path.name},
                reason="operator-entry import: item is not a JSON object",
                claimed_source_time=None,
            )
            continue
        result = record_measurement(
            store=store,
            sensor_id=item.get("sensor_id") if isinstance(item.get("sensor_id"), str) else "",
            metric=metric,
            value=item.get("value"),
            unit=unit,
            minimum=minimum,
            maximum=maximum,
            timestamp=item.get("timestamp") if isinstance(item.get("timestamp"), str) else None,
            source=import_source,
        )
        if result["status"] == "RECORDED":
            recorded += 1
        else:
            quarantined += 1
    return {
        "status": "IMPORT_COMPLETE",
        "file": file_path.name,
        "entries": len(data),
        "recorded": recorded,
        "quarantined": quarantined,
    }


__all__ = [
    "OperatorEntryError",
    "record_measurement",
    "import_foreign_file",
    "DEFAULT_SOURCE",
]
