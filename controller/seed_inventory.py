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
- Feinabstimmung (19.11.): a documented germination test (sample size,
  counted germinated seeds, timezone-aware date, conditions note) can
  be supplied; the claimed rate must then match the counted evidence,
  otherwise the evaluation is refused (CLAIM != EVIDENCE, fail-closed).

Honest limits (DOCUMENTED != IMPLEMENTED elsewhere):
- NO storage, NO database, NO labeling workflow: this module evaluates
  numbers and facts the caller hands it; it does not manage inventory
- open_pollinated is an input the caller must verify (breeder document,
  own propagation history); this module cannot test seed genetics
- a germination_rate_pct without a documented test setup (sample size,
  date, conditions) is a claim, not evidence (CLAIM != EVIDENCE);
  without a GerminationTest the evaluation stays an evaluation of the
  CALLER'S claim, never a proof
- thresholds are planning defaults; a real site derives its own from
  its climate, storage conditions and seed age
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

MIN_GERMINATION_PCT = 75.0  # planning default for viable seed batches
DEFAULT_RESERVE_DAYS = 180   # planning default: six months of staples
MIN_SAMPLE_SIZE = 20          # planning default: smallest meaningful Keimprobe


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
class GerminationTest:
    """Dokumentierte Keimprobe: gezählte Evidenz statt bloßer Angabe.

    Fail-closed bei der Erzeugung: Stichprobengröße >= MIN_SAMPLE_SIZE,
    0 <= gekeimt <= Stichprobe, zeitzonen-bewusstes Datum, Bedingungen
    als nicht-leerer Text. Eine Keimprobe ist ein Nachweis über die
    gezählten Werte, nicht über die Wahrheit der Saatgut-Charge selbst.
    """
    sample_size: int
    germinated_count: int
    tested_at: str
    conditions: str

    def __post_init__(self) -> None:
        if type(self.sample_size) is not int or self.sample_size < MIN_SAMPLE_SIZE:
            raise SeedInventoryError(
                f"sample_size must be an int >= {MIN_SAMPLE_SIZE} (bool not accepted)")
        if type(self.germinated_count) is not int or self.germinated_count < 0:
            raise SeedInventoryError("germinated_count must be a non-negative int")
        if self.germinated_count > self.sample_size:
            raise SeedInventoryError("germinated_count cannot exceed sample_size")
        if not isinstance(self.tested_at, str) or not self.tested_at.strip():
            raise SeedInventoryError("tested_at fehlt (ISO-8601, zeitzonen-bewusst)")
        try:
            parsed = datetime.fromisoformat(self.tested_at)
        except ValueError as exc:
            raise SeedInventoryError(f"tested_at ist kein ISO-8601-Zeitstempel: {self.tested_at!r}") from exc
        if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
            raise SeedInventoryError("tested_at muss zeitzonen-bewusst sein (naive verworfen)")
        if not isinstance(self.conditions, str) or not self.conditions.strip():
            raise SeedInventoryError("conditions muss der dokumentierte Prüfaufbau sein (nicht leer)")

    def computed_rate_pct(self) -> float:
        return round(self.germinated_count / self.sample_size * 100.0, 4)



@dataclass(frozen=True)
class SeedBatchStatus:
    batch_id: str
    crop_name: str
    open_pollinated: bool
    germination_rate_pct: float
    viable: bool
    status_message: str


def evaluate_seed_batch(*, batch_id: str, crop_name: str,
                        open_pollinated: bool, germination_rate_pct: float,
                        germination_test: "GerminationTest | None" = None) -> SeedBatchStatus:
    """Evaluate one seed batch. Fail-closed on invalid inputs.

    viable is True only if the batch is explicitly samenfest AND the
    germination test result meets the minimum; anything unverified
    counts as not viable (UNKNOWN != PASS).

    Feinabstimmung: wird eine GerminationTest übergeben, muss die
    behauptete Rate zur gezählten Evidenz passen (Toleranz 0.01
    Prozentpunkte, Rundungsrest); sonst Verweigerung. Ohne Keimprobe
    bleibt alles eine Bewertung der Angabe des Aufrufers.
    """
    if not isinstance(batch_id, str) or not batch_id or len(batch_id) > 64:
        raise SeedInventoryError("batch_id must be a non-empty string of at most 64 chars")
    if not isinstance(crop_name, str) or not crop_name or len(crop_name) > 64:
        raise SeedInventoryError("crop_name must be a non-empty string of at most 64 chars")
    if type(open_pollinated) is not bool:
        raise SeedInventoryError("open_pollinated must be a real boolean (verified fact)")
    rate = _require("germination_rate_pct", germination_rate_pct, maximum=100.0)

    evidence_note = "Bewertung der Angaben, keine"
    if germination_test is not None:
        if abs(germination_test.computed_rate_pct() - rate) > 0.01:
            raise SeedInventoryError(
                f"CLAIM != EVIDENCE: behauptete Keimrate {rate}% passt nicht zur gezählten "
                f"Keimprobe ({germination_test.germinated_count}/"
                f"{germination_test.sample_size} = "
                f"{germination_test.computed_rate_pct()}%). Verweigert."
            )
        evidence_note = (
            f"mit dokumentierter Keimprobe ({germination_test.germinated_count}/"
            f"{germination_test.sample_size}, {germination_test.tested_at}, "
            f"{germination_test.conditions});"
        )

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
                           f"({rate}% laut Keimprobe). {evidence_note} "
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
