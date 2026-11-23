#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Impact measurement from REAL measurements (CSV: timestamp,value,source_type).

No value is invented: the caller supplies measurements and, for CO2, an
explicit emission factor. A claimed saving is only VALID when
  - timestamps are timezone-aware (naive timestamps are rejected,
    never silently assumed UTC; consistent with measurement_ingest and
    the V91 Resource Savings Verification Protocol),
  - baseline ends before the after-period starts,
  - enough samples exist,
  - data quality (DQI) >= 0.85,
  - the difference exceeds measurement noise (otherwise NOT_SIGNIFICANT).
Only VALID records count towards verified totals. VALID means
calculation-validated; INDEPENDENTLY_VERIFIED requires a separate
reviewer and is never assigned by this module.

Optional evidence_refs bind a result to its raw artifacts by reference
plus SHA-256 digest. A digest proves byte identity only; it never proves
source truth, calibration, or that the artifact is still retrievable
(protocol section 3: a digest without accessible evidence is insufficient
for audit; the raw artifact must remain retrievable to an authorized
reviewer).
"""

import csv
import json
import math
import re
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

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_csv(path: str) -> list[dict[str, Any]]:
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    return rows


def _validate_evidence_refs(evidence_refs: Any) -> list[dict[str, str]]:
    """Fail-closed validation of raw-artifact references (protocol section 3).

    Each entry must be a dict with a non-empty 'raw_artifact_ref' (opaque,
    access-controlled reference string; never a secret or personal data)
    and a lowercase 64-hex 'raw_artifact_sha256'. Anything else raises
    ValueError instead of being silently dropped or auto-repaired.
    """
    if not isinstance(evidence_refs, list) or not evidence_refs:
        raise ValueError("evidence_refs must be a non-empty list when provided")
    validated: list[dict[str, str]] = []
    for entry in evidence_refs:
        if not isinstance(entry, dict):
            raise ValueError("evidence ref must be a dict with raw_artifact_ref and raw_artifact_sha256")
        artifact_ref = entry.get("raw_artifact_ref")
        digest = entry.get("raw_artifact_sha256")
        if not isinstance(artifact_ref, str) or not artifact_ref.strip():
            raise ValueError("raw_artifact_ref must be a non-empty string reference")
        if not isinstance(digest, str) or not _SHA256_RE.match(digest):
            raise ValueError(
                "raw_artifact_sha256 must be a lowercase 64-character hex SHA-256 digest"
            )
        validated.append(
            {"raw_artifact_ref": artifact_ref, "raw_artifact_sha256": digest}
        )
    return validated


def _parse(rows: list[dict[str, Any]]) -> tuple[list[tuple[datetime, float, str]], int]:
    """Return valid samples and the number of rejected rows."""
    good, bad = [], 0
    for row in rows:
        try:
            ts = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
            if ts.tzinfo is None or ts.utcoffset() is None:
                # Timezone-naive timestamps are ambiguous; rejecting is the
                # only fail-closed choice (never guess UTC, never impute).
                raise ValueError
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
    evidence_refs: list[dict[str, Any]] | None = None,
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
    if evidence_refs is not None:
        result["evidence_refs"] = _validate_evidence_refs(evidence_refs)
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
    """Totals over calculation-VALID impacts only (call verify_chain first).

    VALID means the calculation passed its own gates. It does NOT mean
    independently verified: INDEPENDENTLY_VERIFIED requires a separate
    reviewer (protocol section 6) and is never assigned here.
    """
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
    calculation_rate = round(valid / total, 4) if total else None
    return {
        "impacts_total": total,
        "impacts_valid": valid,
        # Explicit name: this is calculation validity, not independent verification.
        "calculation_validity_rate": calculation_rate,
        # Legacy compatibility only; do not interpret this as independent verification.
        "verification_rate": calculation_rate,
        "verified_co2_saved_kg_per_sample": round(co2, 6),
        "valid_impacts_co2_saved_kg_per_sample": round(co2, 6),
        # No independent reviewer evidence is represented by this ledger schema yet.
        "independently_reviewed_impacts_count": 0,
        # Deprecated compatibility alias; same meaning and value, not a verification claim.
        "verified_impacts_count_independently_reviewed": 0,
        "independent_review_rate": None,
        "review_status": "NOT_INDEPENDENTLY_VERIFIED",
    }
