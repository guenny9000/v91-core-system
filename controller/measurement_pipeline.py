#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Canonical measurement pipeline (Issue #100 consolidation).

Single fail-closed entry point that wires the three existing
measurement modules together instead of duplicating them
(NO_DUPLICATE_SYSTEMS):

- controller/measurement_ingest.py  -> stateless validation
  (VALID / QUARANTINE / REJECTED verdict, never repairs)
- controller/measurement_store.py   -> the authoritative tamper-evident
  HMAC-SHA256 hash-chained ledger for BOTH valid records and
  quarantined raw payloads
- controller/measurement_quarantine.py -> the operational resolution
  workflow (list_open / resolve; append-only, never deletes)

Role contract fixed by this module (was ambiguous before):
- Exactly ONE ledger write per processed measurement, either
  MEASUREMENT_VALID or MEASUREMENT_QUARANTINE in the MeasurementStore.
  The MeasurementQuarantine workflow store is NOT written here; it is
  the separate human/ops resolution tracker over the same incidents.
- REJECTED (non-numeric payloads, booleans, strings) is ALSO persisted
  as a quarantine record: refusal to store is refusal to lose data.
- Warnings do not block storage (documented ingest semantics).

Honest limits: no sensors, no daemon, no network, no background job;
SCRIPTED != INSTALLED; single-process only (store lock is per path);
this pipeline does not prove any real measurement source is live.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Mapping

from controller.measurement_ingest import (
    MeasurementStatus,
    PreviousMeasurement,
    RawMeasurement,
    SensorSpec,
    ValidationResult,
    validate_measurement,
)
from controller.measurement_store import MeasurementStore


class MeasurementPipelineError(Exception):
    """Fail-closed pipeline error."""


class MeasurementPipeline:
    """Validate once, persist exactly one ledger record per measurement."""

    def __init__(self, store: MeasurementStore) -> None:
        if not isinstance(store, MeasurementStore):
            raise MeasurementPipelineError("store must be a MeasurementStore instance")
        self._store = store

    def process(
        self,
        measurement: RawMeasurement,
        specs: Mapping[str, SensorSpec],
        previous: PreviousMeasurement | None = None,
    ) -> ValidationResult:
        """Validate via ingest, then persist the verdict in the store.

        VALID -> MEASUREMENT_VALID record.
        QUARANTINE or REJECTED -> MEASUREMENT_QUARANTINE record with the
        untouched raw payload and the full error list. Never repairs,
        never silently drops.
        """
        result = validate_measurement(measurement, specs, previous)
        if result.status is MeasurementStatus.VALID:
            if result.normalized_value is None or result.timestamp_utc is None:
                # Defensive: ingest guarantees both on VALID; if that
                # contract ever breaks we fail closed instead of storing
                # an incomplete record.
                raise MeasurementPipelineError(
                    "ingest returned VALID without normalized value/timestamp; refusing to store"
                )
            self._store.record_valid(
                sensor_id=measurement.sensor_id,
                metric=measurement.metric,
                normalized_value=result.normalized_value,
                unit=measurement.unit,
                timestamp_utc=result.timestamp_utc,
                source=measurement.source,
            )
            return result

        # QUARANTINE and REJECTED both preserve the raw payload verbatim.
        raw: dict[str, Any] = dataclasses.asdict(result.original)
        reasons = "; ".join(result.errors) if result.errors else f"verdict {result.status.value}"
        self._store.quarantine(
            raw,
            reason=f"{result.status.value}: {reasons}",
            claimed_source_time=result.original.timestamp
            if isinstance(result.original.timestamp, str) else None,
        )
        return result

    def verify_ledger(self) -> bool:
        """Expose the store's chain verification (evidence, not claim)."""
        return self._store.verify_chain()
