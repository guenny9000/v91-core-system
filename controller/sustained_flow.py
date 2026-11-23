#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Deterministic sustained-flow (Dauerfluss/Grundlast) detection.

A DETECTION is never an authorization to act (DETECTION !=
AUTHORIZATION) and never proof of real-world causation. This module
only marks windows in which a value stays strictly above an explicit
threshold for at least min_consecutive consecutive samples.

Fail-closed rules:
- every timestamp must be timezone-aware (naive is rejected, never
  silently assumed UTC - consistent with controller/impact.py);
- every value must be a finite plain number (bool is rejected);
- duplicate timestamps are ambiguous and rejected;
- threshold must be a finite number, min_consecutive an int >= 1;
- input order never matters: samples are sorted by timestamp before
  evaluation and the report hash is computed over the sorted,
  canonical event list (determinism by construction).
"""

import hashlib
import json
from datetime import datetime
from math import fsum, isfinite


class SustainedFlowError(ValueError):
    """Raised when the sample series or parameters are not admissible."""


def _checked(sample):
    if not isinstance(sample, tuple) or len(sample) != 2:
        raise SustainedFlowError(
            "samples: (timestamp, value) tuples required")
    ts, value = sample
    if not isinstance(ts, datetime):
        raise SustainedFlowError("timestamp: datetime required")
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise SustainedFlowError(
            "timestamp: timezone-aware required (naive is ambiguous;"
            " never silently assumed UTC)")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SustainedFlowError(
            "value: finite number required (UNKNOWN never imputed)")
    if not isfinite(float(value)):
        raise SustainedFlowError("value: must be finite")
    return sample


def detect_sustained_flow(samples, threshold, min_consecutive):
    """Mark windows above threshold for >= min_consecutive samples.

    Returns a deterministic report with a canonical SHA-256 over the
    event list. No heuristic, no randomness, no wall clock reads.
    """
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise SustainedFlowError("threshold: finite number required")
    if not isfinite(float(threshold)):
        raise SustainedFlowError("threshold: must be finite")
    if (isinstance(min_consecutive, bool)
            or not isinstance(min_consecutive, int) or min_consecutive < 1):
        raise SustainedFlowError("min_consecutive: int >= 1 required")
    if not isinstance(samples, (list, tuple)):
        raise SustainedFlowError("samples: sequence required")

    checked = [_checked(s) for s in samples]
    seen = set()
    for ts, _ in checked:
        if ts in seen:
            raise SustainedFlowError("duplicate timestamp: " + ts.isoformat())
        seen.add(ts)
    ordered = sorted(checked, key=lambda s: s[0])

    events = []
    streak = []

    def close_streak():
        if len(streak) >= min_consecutive:
            values = [value for _, value in streak]
            events.append({
                "start_utc": streak[0][0].isoformat(),
                "end_utc": streak[-1][0].isoformat(),
                "window_count": len(streak),
                "peak_value": max(values),
                "average_value": round(fsum(values) / len(values), 6),
            })

    for sample in ordered:
        if float(sample[1]) > float(threshold):
            streak.append(sample)
        else:
            close_streak()
            streak = []
    close_streak()

    canonical = json.dumps(
        events, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        "event_count": len(events),
        "events": events,
        "report_sha256": hashlib.sha256(
            canonical.encode("utf-8")).hexdigest(),
        "review_status": "DETECTION_ONLY",
    }
