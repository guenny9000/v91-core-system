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
        if not isinstance(self.metric, str) or not self.metric.strip():
            raise ValueError("metric must be a non-empty string")
        if not isinstance(self.unit, str) or not self.unit.strip():
            raise ValueError("unit must be a non-empty string")
        minimum = _as_finite_float(self.minimum)
        maximum = _as_finite_float(self.maximum)
        if minimum is None:
            raise ValueError("minimum must be finite")
        if maximum is None:
            raise ValueError("maximum must be finite")
        if minimum > maximum:
            raise ValueError("minimum must not exceed maximum")
        for name, value in (
            ("max_change_per_hour", self.max_change_per_hour),
            ("max_gap_seconds", self.max_gap_seconds),
        ):
            if value is not None:
                finite_value = _as_finite_float(value)
                if finite_value is None or finite_value <= 0:
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


def _as_finite_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


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

    if not isinstance(measurement.sensor_id, str) or not measurement.sensor_id.strip():
        errors.append("sensor_id missing or invalid")
    if not isinstance(measurement.metric, str) or not measurement.metric.strip():
        errors.append("metric missing or invalid")

    spec = specs.get(measurement.metric) if isinstance(measurement.metric, str) else None
    if not isinstance(spec, SensorSpec):
        spec = None
        errors.append(f"no valid sensor specification for metric {measurement.metric!r}")
    if previous is not None and not isinstance(previous, PreviousMeasurement):
        raise TypeError("previous must be PreviousMeasurement or None")

    timestamp = _parse_timestamp(measurement.timestamp)
    if timestamp is None:
        errors.append("timestamp missing, malformed, or timezone-naive")

    value = measurement.value
    numeric = _as_finite_float(value)
    if value is None:
        errors.append("value is None; source failure or missing reading")
    elif isinstance(value, bool) or not isinstance(value, (int, float)):
        return ValidationResult(
            MeasurementStatus.REJECTED,
            measurement,
            errors=errors + ["value must be a numeric int or float; booleans and strings are rejected"],
        )
    elif numeric is None:
        errors.append("value is not finite or cannot be represented safely")
    elif numeric in KNOWN_ERROR_VALUES:
        errors.append(f"known sensor error sentinel: {numeric}")
    elif spec is not None:
        if measurement.unit != spec.unit:
            errors.append(f"unit mismatch: received {measurement.unit!r}, expected {spec.unit!r}")
        minimum = _as_finite_float(spec.minimum)
        maximum = _as_finite_float(spec.maximum)
        if minimum is None or maximum is None:
            errors.append("sensor specification limits are invalid")
        elif numeric < minimum or numeric > maximum:
            errors.append(
                f"value {numeric} outside [{minimum}, {maximum}] {spec.unit}"
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
                    and numeric is not None
                    and _as_finite_float(previous.value) is not None
                ):
                    rate = abs(numeric - float(previous.value)) / (elapsed / 3600)
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
        normalized_value=numeric,
        timestamp_utc=timestamp.isoformat().replace("+00:00", "Z") if timestamp else None,
    )
