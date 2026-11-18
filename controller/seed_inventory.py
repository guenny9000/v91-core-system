#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Seed inventory and seasonal reserve evaluation (Alsfeld runbook items).

Two pure, fail-closed evaluations of caller-verified facts:
- seed batches: open-pollinated (samenfest) status must be explicitly
  True, and germination_rate_pct must come from a REAL germination
  test (Keimprobe) the caller performed; >= MIN_GERMINATION_PCT passes
- seasonal reserves: days of cover versus an explicit minimum target

Honest limits (DOCUMENTED != IMPLEMENTED elsewhere):
- NO storage, NO database, NO labeling workflow: this module evaluates
  numbers and facts the caller hands it; it does not manage inventory
- open_pollinated is an input the caller must verify (breeder document,
  own propagation history); this module cannot test seed genetics
- a germination_rate_pct without a documented test setup (sample size,
  date, conditions) is a claim, not evidence (CLAIM != EVIDENCE)
- thresholds are planning defaults; a real site derives its own from
  its climate, storage conditions and seed age
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MIN_GERMINATION_PCT = 75.0  # planning default for viable seed batches
DEFAULT_RESERVE_DAYS = 180   # planning default: six months of staples


class SeedInventoryError(ValueError):
    """Fail-closed input validation error."""


def _require(name: str, value: float, *, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SeedInventoryError(f"{name} must be a real number, got {type(value).__name__}")
    if not math.isfinite(value) or value < 0 or (maximum is not None and value > maximum):
        bound = f" in [0, {maximum}]" if maximum is not None else " >= 0"
        raise SeedInventoryError(f"{name} must be a finite value{bound}, got {value}")
    return float(value)


@dataclass(frozen=True)
class SeedBatchStatus:
    batch_id: str
    crop_name: str
    open_pollinated: bool
    germination_rate_pct: float
    viable: bool
    status_message: str


def evaluate_seed_batch(*, batch_id: str, crop_name: str,
                        open_pollinated: bool, germination_rate_pct: float) -> SeedBatchStatus:
    """Evaluate one seed batch. Fail-closed on invalid inputs.

    viable is True only if the batch is explicitly samenfest AND the
    germination test result meets the minimum; anything unverified
    counts as not viable (UNKNOWN != PASS).
    """
    if not isinstance(batch_id, str) or not batch_id or len(batch_id) > 64:
        raise SeedInventoryError("batch_id must be a non-empty string of at most 64 chars")
    if not isinstance(crop_name, str) or not crop_name or len(crop_name) > 64:
        raise SeedInventoryError("crop_name must be a non-empty string of at most 64 chars")
    if type(open_pollinated) is not bool:
        raise SeedInventoryError("open_pollinated must be a real boolean (verified fact)")
    rate = _require("germination_rate_pct", germination_rate_pct, maximum=100.0)

    if not open_pollinated:
        return SeedBatchStatus(batch_id, crop_name, False, rate, False,
                               f"ABGELEHNT: Charge {batch_id} ({crop_name}) ist nicht "
                               "verifiziert samenfest (Hybrid/Legacy-Risiko).")
    if rate < MIN_GERMINATION_PCT:
        return SeedBatchStatus(batch_id, crop_name, True, rate, False,
                               f"WARNUNG: Charge {batch_id} ({crop_name}) Keimprobe "
                               f"unter Minimum ({rate}% < {MIN_GERMINATION_PCT}%).")
    return SeedBatchStatus(batch_id, crop_name, True, rate, True,
                           f"OK: Charge {batch_id} ({crop_name}) samenfest und keimfaehig "
                           f"({rate}% laut Keimprobe). Bewertung der Angaben, keine "
                           "Lagergarantie.")


@dataclass(frozen=True)
class SeasonalReserveStatus:
    category: str
    days_assured: int
    minimum_required_days: int
    secure: bool
    status_message: str


def evaluate_seasonal_reserves(*, reserve_days: int,
                              required_days: int = DEFAULT_RESERVE_DAYS,
                              category: str = "Stapelnahrung") -> SeasonalReserveStatus:
    """Evaluate seasonal reserve coverage in days. Fail-closed."""
    if not isinstance(category, str) or not category or len(category) > 64:
        raise SeedInventoryError("category must be a non-empty string of at most 64 chars")
    if type(reserve_days) is not int or reserve_days < 0:
        raise SeedInventoryError("reserve_days must be a non-negative int (bool is not accepted)")
    if type(required_days) is not int or required_days < 1 or required_days > 3650:
        raise SeedInventoryError("required_days must be an int in [1, 3650]")

    if reserve_days < required_days:
        return SeasonalReserveStatus(category, reserve_days, required_days, False,
                                     f"KRITISCH: Vorrat '{category}' unzureichend: "
                                     f"{reserve_days} Tage erreicht, Ziel {required_days} Tage.")
    return SeasonalReserveStatus(category, reserve_days, required_days, True,
                                 f"OK: Vorrat '{category}' erreicht Ziel "
                                 f"({reserve_days} >= {required_days} Tage). "
                                 "Bewertete Angabe, keine Dauerhaftigkeit.")
