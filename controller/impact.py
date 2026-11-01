#!/usr/bin/env python3
"""
Impact measurement from REAL measurements (CSV: timestamp,value,source_type).

No value is invented: the caller supplies measurements and, for CO2, an
explicit emission factor. A claimed saving is only VALID when
  - baseline ends before the after-period starts,
  - enough samples exist,
  - data quality (DQI) >= 0.85,
  - the difference exceeds measurement noise (otherwise NOT_SIGNIFICANT).
Only VALID records count towards verified totals.
"""

import csv
import json
import math
import statistics
import time
from datetime import datetime
from typing import Any

from ledger import HashChainLedger

SOURCE_CONFIDENCE = {
    "direct_sensor": 1.00,
    "calculated": 0.90,
    "estimated": 0.70,
    "manual_entry": 0.60,
}
MIN_SAMPLES = 5
DQI_MIN = 0.85
NOISE_FACTOR = 2.0


def load_csv(path: str) -> list[dict[str, Any]]:
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    return rows


def _parse(rows: list[dict[str, Any]]) -> tuple[list[tuple[datetime, float, str]], int]:
    """Return valid samples and the number of rejected rows."""
    good, bad = [], 0
    for row in rows:
        try:
            ts = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
            value = float(row["value"])
            source = str(row.get("source_type", "")).strip()
            if not math.isfinite(value) or source not in SOURCE_CONFIDENCE:
                raise ValueError
            good.append((ts, value, source))
        except (KeyError, ValueError, TypeError):
            bad += 1
    return good, bad


def _dqi(samples: list, rejected: int) -> float:
    total = len(samples) + rejected
    if not samples:
        return 0.0
    completeness = len(samples) / total
    confidence = statistics.mean(SOURCE_CONFIDENCE[s[2]] for s in samples)
    return round(completeness * confidence, 4)


def compute_impact(
    measure: str,
    baseline_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    unit: str,
    co2_factor_kg_per_unit: float | None = None,
    higher_is_worse: bool = True,
    co2_source: str | None = None,
) -> dict[str, Any]:
    """Compare two real measurement periods. saved > 0 means improvement."""
    if co2_factor_kg_per_unit is not None and not (co2_source and co2_source.strip()):
        raise ValueError("co2_source is required when a CO2 factor is given")
    if co2_factor_kg_per_unit is not None and (
        not math.isfinite(co2_factor_kg_per_unit) or co2_factor_kg_per_unit < 0
    ):
        raise ValueError("co2 factor must be a finite non-negative number")
    base, base_bad = _parse(baseline_rows)
    after, after_bad = _parse(after_rows)
    errors: list[str] = []

    if len(base) < MIN_SAMPLES or len(after) < MIN_SAMPLES:
        errors.append("TOO_FEW_SAMPLES")
    if base and after and max(s[0] for s in base) >= min(s[0] for s in after):
        errors.append("TEMPORAL_ERROR")

    dqi = round(min(_dqi(base, base_bad), _dqi(after, after_bad)), 4)
    if dqi < DQI_MIN:
        errors.append("LOW_DQI")

    result: dict[str, Any] = {
        "measure": measure,
        "unit": unit,
        "n_baseline": len(base),
        "n_after": len(after),
        "rejected_rows": base_bad + after_bad,
        "dqi": dqi,
    }
    if len(base) >= 2 and len(after) >= 2:
        b_vals = [s[1] for s in base]
        a_vals = [s[1] for s in after]
        b_mean, a_mean = statistics.mean(b_vals), statistics.mean(a_vals)
        diff = (b_mean - a_mean) if higher_is_worse else (a_mean - b_mean)
        noise = math.sqrt(
            statistics.variance(b_vals) / len(b_vals) + statistics.variance(a_vals) / len(a_vals)
        )
        result.update(
            baseline_mean=round(b_mean, 6),
            after_mean=round(a_mean, 6),
            saved_per_sample=round(diff, 6),
            noise_stderr=round(noise, 6),
        )
        if abs(diff) <= NOISE_FACTOR * noise:
            errors.append("NOT_SIGNIFICANT")
        if co2_factor_kg_per_unit is not None:
            result["co2_saved_kg_per_sample"] = round(diff * co2_factor_kg_per_unit, 6)
            result["co2_factor_kg_per_unit"] = co2_factor_kg_per_unit
            result["co2_factor_source"] = co2_source.strip()  # type: ignore[union-attr]

    if not errors:
        result["status"] = "VALID" if result["saved_per_sample"] > 0 else "NO_IMPROVEMENT"
    else:
        result["status"] = "QUARANTINE"
    result["flags"] = errors
    return result


def record_impact(ledger: HashChainLedger, impact: dict[str, Any]) -> dict[str, Any]:
    return ledger.append(
        {"type": "impact", **impact}, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )


def verified_summary(ledger_path: str) -> dict[str, Any]:
    """Totals over VALID impacts only (call verify_chain first)."""
    total = valid = 0
    co2 = 0.0
    with open(ledger_path, encoding="utf-8") as fh:
        for line in fh:
            payload = json.loads(line)["payload"]
            if payload.get("type") != "impact":
                continue
            total += 1
            if payload["status"] == "VALID":
                valid += 1
                co2 += payload.get("co2_saved_kg_per_sample", 0.0)
    return {
        "impacts_total": total,
        "impacts_valid": valid,
        "verification_rate": round(valid / total, 4) if total else None,
        "verified_co2_saved_kg_per_sample": round(co2, 6),
    }
