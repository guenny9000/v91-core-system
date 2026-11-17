"""Fail-closed validation for externally sourced measurements.

This module validates one measurement at a time. It does not connect sensors,
write a ledger, infer missing values, or claim that a source is live.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping


class MeasurementStatus(str, Enum):
    VALID = "VALID"
    QUARANTINE = "QUARANTINE"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class SensorSpec:
    metric: str
    unit: str
    minimum: float
    maximum: float
    max_change_per_hour: float | None = None
    max_gap_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.metric or not self.unit:
            raise ValueError("metric and unit must be non-empty")
        for name, value in (("minimum", self.minimum), ("maximum", self.maximum)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        for name, value in (
            ("max_change_per_hour", self.max_change_per_hour),
            ("max_gap_seconds", self.max_gap_seconds),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be finite and positive when set")


@dataclass(frozen=True)
class RawMeasurement:
    sensor_id: str
    metric: str
    value: object
    unit: str
    timestamp: str
    source: str = "unknown"


@dataclass(frozen=True)
class PreviousMeasurement:
    value: float
    timestamp: str


@dataclass
class ValidationResult:
    status: MeasurementStatus
    original: RawMeasurement
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_value: float | None = None
    timestamp_utc: str | None = None


# Common sentinel values are rejected before range checks. A sensor-specific
# adapter should add vendor-specific codes rather than silently translating them.
KNOWN_ERROR_VALUES = frozenset({-999, -9999, 9999, 99999, 999.9})


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def validate_measurement(
    measurement: RawMeasurement,
    specs: Mapping[str, SensorSpec],
    previous: PreviousMeasurement | None = None,
) -> ValidationResult:
    """Validate raw input; never repair, interpolate, or write it elsewhere."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(measurement, RawMeasurement):
        raise TypeError("measurement must be RawMeasurement")
    if not isinstance(specs, Mapping):
        raise TypeError("specs must be a mapping")

    if not measurement.sensor_id.strip():
        errors.append("sensor_id missing")
    if not measurement.metric.strip():
        errors.append("metric missing")

    spec = specs.get(measurement.metric)
    if spec is None:
        errors.append(f"no sensor specification for metric {measurement.metric!r}")

    timestamp = _parse_timestamp(measurement.timestamp)
    if timestamp is None:
        errors.append("timestamp missing, malformed, or timezone-naive")

    value = measurement.value
    if value is None:
        errors.append("value is None; source failure or missing reading")
    elif isinstance(value, bool) or not isinstance(value, (int, float)):
        return ValidationResult(
            MeasurementStatus.REJECTED,
            measurement,
            errors=errors + ["value must be a numeric int or float; booleans and strings are rejected"],
        )
    else:
        try:
            numeric = float(value)
        except (OverflowError, TypeError, ValueError):
            numeric = math.nan
        if not math.isfinite(numeric):
            errors.append("value is not finite")
        elif numeric in KNOWN_ERROR_VALUES:
            errors.append(f"known sensor error sentinel: {numeric}")
        elif spec is not None:
            if measurement.unit != spec.unit:
                errors.append(f"unit mismatch: received {measurement.unit!r}, expected {spec.unit!r}")
            if numeric < spec.minimum or numeric > spec.maximum:
                errors.append(
                    f"value {numeric} outside [{spec.minimum}, {spec.maximum}] {spec.unit}"
                )

    if previous is not None and timestamp is not None and spec is not None:
        previous_time = _parse_timestamp(previous.timestamp)
        if previous_time is None:
            warnings.append("previous timestamp is invalid; rate and gap checks skipped")
        else:
            elapsed = (timestamp - previous_time).total_seconds()
            if elapsed <= 0:
                errors.append("timestamp is not later than the previous measurement")
            else:
                if spec.max_gap_seconds is not None and elapsed > spec.max_gap_seconds:
                    warnings.append(f"measurement gap: {elapsed:.1f} seconds")
                if (
                    spec.max_change_per_hour is not None
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(float(value))
                ):
                    rate = abs(float(value) - previous.value) / (elapsed / 3600)
                    if rate > spec.max_change_per_hour:
                        warnings.append(
                            f"unusual change rate: {rate:.3f} per hour "
                            f"(configured maximum {spec.max_change_per_hour})"
                        )

    if errors:
        return ValidationResult(MeasurementStatus.QUARANTINE, measurement, errors, warnings)
    return ValidationResult(
        MeasurementStatus.VALID,
        measurement,
        warnings=warnings,
        normalized_value=float(value),
        timestamp_utc=timestamp.isoformat().replace("+00:00", "Z") if timestamp else None,
    )
