#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Resilience monitors: winter feed balance, aquaculture water quality,
and drinking-water hygiene separation checks.

Pure evaluation of caller-provided measurements, fail-closed:
- non-finite (NaN/Inf) or negative inputs are refused, never silently
  clamped (a refused check must not become a passed check)
- thresholds are explicit named constants, documented as planning
  defaults that must be re-derived from real measurements per site

Honest limits (DOCUMENTED != IMPLEMENTED elsewhere):
- NO sensors, no data acquisition, no storage: the caller measures,
  this module only evaluates numbers it is handed
- WEEKLY_NEED_KG_PER_ANIMAL is a planning assumption for a mixed
  chicken/rabbit flock, not a measured site value; a real feed plan
  needs per-species rations and local winter length
- OPTIMAL/OK verdicts describe the evaluated numbers, not the physical
  farm: without measured inputs there is no verdict at all (UNKNOWN
  != PASS)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Planning defaults (must be re-derived from real site data):
WEEKLY_NEED_KG_PER_ANIMAL = 1.5  # mixed chicken/rabbit planning assumption
O2_MIN_MG_L = 5.0                # aquaculture lower bound (planning default)
NITRITE_MAX_MG_L = 0.2           # aquaculture upper bound (planning default)


def _require_finite_non_negative(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite (NaN/Inf refused, fail-closed)")
    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value}")
    return float(value)


@dataclass(frozen=True)
class WinterFeedStatus:
    sufficient: bool
    grain_reserves_kg: float
    hay_reserves_kg: float
    required_total_kg: float
    status_message: str


def evaluate_winter_feed_balance(grain_kg: float, hay_kg: float,
                                 animal_count: int, winter_weeks: int = 20) -> WinterFeedStatus:
    """Evaluate whether grain+hay reserves cover the planning need.

    Fail-closed: invalid inputs raise ValueError instead of producing
    a verdict; absence of a verdict is never treated as sufficiency.
    """
    grain = _require_finite_non_negative("grain_kg", grain_kg)
    hay = _require_finite_non_negative("hay_kg", hay_kg)
    if type(animal_count) is not int or animal_count < 0:
        raise ValueError("animal_count must be a non-negative int (bool is not accepted)")
    if type(winter_weeks) is not int or winter_weeks < 1:
        raise ValueError("winter_weeks must be a positive int")
    required = animal_count * winter_weeks * WEEKLY_NEED_KG_PER_ANIMAL
    available = grain + hay
    if available < required:
        return WinterFeedStatus(
            sufficient=False, grain_reserves_kg=grain, hay_reserves_kg=hay,
            required_total_kg=required,
            status_message=f"KRITISCH: Reserve unzureichend. Vorhanden {available} kg, "
                           f"Planungsbedarf {required} kg (Annahme "
                           f"{WEEKLY_NEED_KG_PER_ANIMAL} kg/Tier/Woche).")
    return WinterFeedStatus(
        sufficient=True, grain_reserves_kg=grain, hay_reserves_kg=hay,
        required_total_kg=required,
        status_message=f"OK: Planungsbedarf gedeckt ({available} kg >= {required} kg "
                       f"bei {winter_weeks} Winterwochen). Gemessen bewertet, "
                       "keine Betriebsgarantie.")


@dataclass(frozen=True)
class AquacultureWaterStatus:
    o2_safe: bool
    nitrite_safe: bool
    o2_mg_l: float
    nitrit_mg_l: float
    status_message: str


def evaluate_aquaculture_quality(o2_mg_l: float, nitrit_mg_l: float) -> AquacultureWaterStatus:
    """Evaluate measured O2 and nitrite values against planning bounds."""
    o2 = _require_finite_non_negative("o2_mg_l", o2_mg_l)
    nitrite = _require_finite_non_negative("nitrit_mg_l", nitrit_mg_l)
    o2_safe = o2 >= O2_MIN_MG_L
    nitrite_safe = nitrite <= NITRITE_MAX_MG_L
    if not o2_safe or not nitrite_safe:
        return AquacultureWaterStatus(
            o2_safe=o2_safe, nitrite_safe=nitrite_safe, o2_mg_l=o2, nitrit_mg_l=nitrite,
            status_message=f"WARNUNG: O2 {o2} mg/L (min {O2_MIN_MG_L}), "
                           f"Nitrit {nitrite} mg/L (max {NITRITE_MAX_MG_L}).")
    return AquacultureWaterStatus(
        o2_safe=True, nitrite_safe=True, o2_mg_l=o2, nitrit_mg_l=nitrite,
        status_message=f"OK: O2 {o2} mg/L und Nitrit {nitrite} mg/L innerhalb der "
                       "Planungsgrenzen (bewertete Messwerte, kein Dauerzustand).")


@dataclass(frozen=True)
class HygieneSeparationStatus:
    segregated: bool
    cross_contamination_risk: bool
    status_message: str


def evaluate_hygiene_separation(physical_air_gap: bool,
                                 backflow_preventer_active: bool) -> HygieneSeparationStatus:
    """Evaluate the two structural preconditions for hygienic separation.

    Both inputs must be explicit True (verified on site); anything else
    is treated as not separated (fail-closed, UNKNOWN != PASS).
    """
    if physical_air_gap is True and backflow_preventer_active is True:
        return HygieneSeparationStatus(
            segregated=True, cross_contamination_risk=False,
            status_message="OK: Physische Luftstrecke und Rueckflussverhinderer "
                           "laut Angabe verifiziert; Trinkwasser- und "
                           "Nahrstoffkreisläufe gelten als getrennt.")
    return HygieneSeparationStatus(
        segregated=False, cross_contamination_risk=True,
        status_message="KRITISCH: Trennung nicht verifiziert (Luftstrecke: "
                       f"{physical_air_gap}, Rueckflussverhinderer: "
                       f"{backflow_preventer_active}). Fail-closed: unbelegt "
                       "gilt als Risiko, nicht als sicher.")
