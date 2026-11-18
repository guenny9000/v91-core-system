#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Measurement monitoring for the measurement ledger (Issue #100).

Evaluates a MeasurementStore JSONL ledger at call time:
- per-sensor freshness (FRESH / STALE / UNKNOWN, never guessed)
- per-sensor interval gaps against an EXPLICIT expected interval
- quarantine counts per sensor
- integrity indicators: unparseable lines, records with unusable
  timestamps, and chain verification (only with a provided key;
  without key the chain status is UNKNOWN, not claimed intact)

Honest limits:
- NO daemon, NO timers, NO notifications: this is an on-demand,
  read-only evaluation. A stale finding is only as current as the
  moment of the call.
- MONITOR FINDING != SENSOR REALITY: a FRESH ledger entry proves the
  ledger received data, not that a physical sensor is healthy.
- Does not modify anything; fail-closed inputs are rejected.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from controller.measurement_store import MeasurementStore


class MeasurementMonitorError(Exception):
    """Fail-closed monitor error."""


def _parse_utc(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp; return None if unusable (UNKNOWN, not guess)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class SensorStatus:
    sensor_id: str
    valid_count: int
    quarantine_count: int
    last_source_time_utc: str | None
    staleness: str  # "FRESH" | "STALE" | "UNKNOWN"
    gap_count: int  # intervals > 2x the expected interval
    unusable_timestamp_records: int


@dataclass(frozen=True)
class MonitorReport:
    now_utc: str
    staleness_seconds: int
    expected_interval_seconds: int
    chain_verified: str  # "VERIFIED" | "FAILED" | "UNKNOWN" (no key provided)
    sensors: dict[str, SensorStatus] = field(default_factory=dict)
    total_records: int = 0
    unparseable_lines: int = 0
    integrity_alerts: tuple[str, ...] = ()


class MeasurementMonitor:
    """Read-only, on-demand evaluator of the measurement ledger."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def evaluate(
        self,
        *,
        now_utc: str,
        staleness_seconds: int,
        expected_interval_seconds: int,
        key: bytes | None = None,
    ) -> MonitorReport:
        if not isinstance(now_utc, str):
            raise MeasurementMonitorError("now_utc must be an ISO-8601 string")
        now = _parse_utc(now_utc)
        if now is None:
            raise MeasurementMonitorError("now_utc must be a tz-aware ISO-8601 timestamp")
        for name, value in (("staleness_seconds", staleness_seconds),
                            ("expected_interval_seconds", expected_interval_seconds)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise MeasurementMonitorError(f"{name} must be a positive int")

        valid_times: dict[str, list[datetime]] = {}
        counts: dict[str, dict[str, int]] = {}
        last_times: dict[str, str | None] = {}
        unusable: dict[str, int] = {}
        unparseable_lines = 0
        total = 0
        alerts: list[str] = []

        if self._path.exists():
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                total += 1
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    unparseable_lines += 1
                    continue
                if not isinstance(entry, dict) or not isinstance(entry.get("record_type"), str):
                    unparseable_lines += 1
                    continue
                sensor_id = self._sensor_of(entry)
                if sensor_id is None:
                    alerts.append(f"record without usable sensor identity at position {total}")
                    continue
                bucket = counts.setdefault(sensor_id, {"valid": 0, "quarantine": 0})
                if entry["record_type"] == "MEASUREMENT_VALID":
                    parsed = _parse_utc(entry.get("source_time_utc"))
                    if parsed is None:
                        unusable[sensor_id] = unusable.get(sensor_id, 0) + 1
                        continue
                    bucket["valid"] += 1
                    valid_times.setdefault(sensor_id, []).append(parsed)
                    last_times[sensor_id] = entry.get("source_time_utc")
                elif entry["record_type"] == "MEASUREMENT_QUARANTINE":
                    bucket["quarantine"] += 1
                else:
                    alerts.append(f"unknown record_type at position {total}: {entry['record_type']!r}")

        if unparseable_lines:
            alerts.append(f"{unparseable_lines} unparseable ledger line(s)")

        sensors: dict[str, SensorStatus] = {}
        for sensor_id in sorted(set(counts) | set(valid_times)):
            times = sorted(valid_times.get(sensor_id, []))
            gaps = 0
            for prev, cur in zip(times, times[1:]):
                delta = (cur - prev).total_seconds()
                if delta > 2 * expected_interval_seconds:
                    gaps += 1
            if times:
                age = (now - times[-1]).total_seconds()
                staleness = "FRESH" if age <= staleness_seconds else "STALE"
            else:
                staleness = "UNKNOWN"
            sensors[sensor_id] = SensorStatus(
                sensor_id=sensor_id,
                valid_count=counts.get(sensor_id, {}).get("valid", 0),
                quarantine_count=counts.get(sensor_id, {}).get("quarantine", 0),
                last_source_time_utc=last_times.get(sensor_id),
                staleness=staleness,
                gap_count=gaps,
                unusable_timestamp_records=unusable.get(sensor_id, 0),
            )

        if key is None:
            chain_verified = "UNKNOWN"
        else:
            store = MeasurementStore(self._path, key=key)
            chain_verified = "VERIFIED" if store.verify_chain() else "FAILED"

        return MonitorReport(
            now_utc=now_utc,
            staleness_seconds=staleness_seconds,
            expected_interval_seconds=expected_interval_seconds,
            sensors=sensors,
            total_records=total,
            unparseable_lines=unparseable_lines,
            chain_verified=chain_verified,
            integrity_alerts=tuple(alerts),
        )

    @staticmethod
    def _sensor_of(entry: dict[str, Any]) -> str | None:
        sensor_id = entry.get("sensor_id")
        if isinstance(sensor_id, str) and sensor_id:
            return sensor_id
        raw = entry.get("raw_payload")
        if isinstance(raw, dict):
            inner = raw.get("sensor_id")
            if isinstance(inner, str) and inner:
                return inner
        return None
