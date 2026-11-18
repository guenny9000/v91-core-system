#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Deterministic local-resilience simulation (scenario model, NOT the
fictional "V91-SIM-7Y real-run" from the chat series).

Implements the four simulation principles from the chat specification
as an honest, stdlib-only scenario engine:
1. nutrient vectors (not "calories"): grain, hay, protein feed tracked
   separately against per-animal weekly rations
2. separate energy balances: electricity, heat and water are three
   distinct stocks with their own draw and refill
3. deterministic technical wear: machinery consumes spare parts per
   operating week; knowledge/tooling prerequisites gate repairs
4. social capacity: work hours and care hours are tracked as a stock
   with weekly burn and explicit rest recovery

Honest limits (MODEL != MEASUREMENT):
- This is a deterministic scenario calculator, NOT a measurement, NOT
  a forecast of any real site, and NOT a running system: identical
  inputs produce identical outputs, nothing is observed
- All parameters are explicit inputs with documented units; nothing
  is calibrated to a real farm because no measured data exists here
  (UNKNOWN != PASS); the caller owns every number
- Untouchable reserves (seed, animal feed base) are never spent by
  the engine, mirroring the project's protection rules
- NO visualization, NO scheduling, NO automatic actions: outputs are
  plain data for a human to read
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any


class SimulationInputError(ValueError):
    """Fail-closed input validation error."""


def _require_non_negative_finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationInputError(f"{name} must be a real number, got {type(value).__name__}")
    if not math.isfinite(value) or value < 0:
        raise SimulationInputError(f"{name} must be finite and non-negative, got {value}")
    return float(value)


@dataclass(frozen=True)
class NutrientVector:
    """Weekly feed stocks in kg. Seed reserve is untouchable (never spent)."""
    grain_kg: float
    hay_kg: float
    protein_feed_kg: float
    animals: int
    ration_grain_kg_per_animal: float = 0.25
    ration_hay_kg_per_animal: float = 0.5
    ration_protein_kg_per_animal: float = 0.1

    def validate(self) -> "NutrientVector":
        for name, value in (("grain_kg", self.grain_kg), ("hay_kg", self.hay_kg),
                            ("protein_feed_kg", self.protein_feed_kg),
                            ("ration_grain_kg_per_animal", self.ration_grain_kg_per_animal),
                            ("ration_hay_kg_per_animal", self.ration_hay_kg_per_animal),
                            ("ration_protein_kg_per_animal", self.ration_protein_kg_per_animal)):
            _require_non_negative_finite(name, value)
        if type(self.animals) is not int or self.animals < 0:
            raise SimulationInputError("animals must be a non-negative int (bool is not accepted)")
        return self


@dataclass(frozen=True)
class EnergyState:
    """Separate stocks: electricity (kWh), heat (kWh), water (m^3)."""
    electricity_kwh: float
    heat_kwh: float
    water_m3: float
    weekly_draw_electricity_kwh: float
    weekly_draw_heat_kwh: float
    weekly_draw_water_m3: float
    weekly_refill_electricity_kwh: float = 0.0
    weekly_refill_heat_kwh: float = 0.0
    weekly_refill_water_m3: float = 0.0

    def validate(self) -> "EnergyState":
        for name, value in vars(self).items():
            _require_non_negative_finite(name, value)
        return self


@dataclass(frozen=True)
class SparePartInventory:
    """Deterministic wear: one part consumed per operating week per machine."""
    spare_parts: int
    operating_machines: int
    tools_available: bool
    repair_knowledge_available: bool

    def validate(self) -> "SparePartInventory":
        if type(self.spare_parts) is not int or self.spare_parts < 0:
            raise SimulationInputError("spare_parts must be a non-negative int")
        if type(self.operating_machines) is not int or self.operating_machines < 0:
            raise SimulationInputError("operating_machines must be a non-negative int")
        if type(self.tools_available) is not bool or type(self.repair_knowledge_available) is not bool:
            raise SimulationInputError("tooling and knowledge flags must be real booleans")
        return self


@dataclass(frozen=True)
class SocialCapacity:
    """Work hours and care hours as a weekly stock (rest recovers capacity)."""
    work_hours_per_week: float
    care_hours_per_week: float
    weekly_work_needed: float
    weekly_care_needed: float
    weekly_rest_recovery_hours: float = 40.0

    def validate(self) -> "SocialCapacity":
        for name, value in vars(self).items():
            _require_non_negative_finite(name, value)
        return self


@dataclass(frozen=True)
class WeekReport:
    week: int
    ok: bool
    deficits: tuple[str, ...]
    state: dict[str, Any]

    def __repr__(self) -> str:  # pragma: no cover
        return f"WeekReport(week={self.week}, ok={self.ok}, deficits={self.deficits})"


def _step_nutrients(n: NutrientVector) -> tuple[NutrientVector, list[str]]:
    deficits: list[str] = []
    grain = n.grain_kg - n.animals * n.ration_grain_kg_per_animal
    hay = n.hay_kg - n.animals * n.ration_hay_kg_per_animal
    protein = n.protein_feed_kg - n.animals * n.ration_protein_kg_per_animal
    if grain < 0:
        deficits.append("grain")
    if hay < 0:
        deficits.append("hay")
    if protein < 0:
        deficits.append("protein_feed")
    return replace(n, grain_kg=max(grain, 0.0), hay_kg=max(hay, 0.0),
                   protein_feed_kg=max(protein, 0.0)), deficits


def _step_energy(e: EnergyState) -> tuple[EnergyState, list[str]]:
    deficits: list[str] = []
    elec = e.electricity_kwh - e.weekly_draw_electricity_kwh + e.weekly_refill_electricity_kwh
    heat = e.heat_kwh - e.weekly_draw_heat_kwh + e.weekly_refill_heat_kwh
    water = e.water_m3 - e.weekly_draw_water_m3 + e.weekly_refill_water_m3
    if elec < 0:
        deficits.append("electricity")
    if heat < 0:
        deficits.append("heat")
    if water < 0:
        deficits.append("water")
    return replace(e, electricity_kwh=max(elec, 0.0), heat_kwh=max(heat, 0.0),
                   water_m3=max(water, 0.0)), deficits


def _step_spares(s: SparePartInventory) -> tuple[SparePartInventory, list[str]]:
    deficits: list[str] = []
    consumed = s.operating_machines  # one part per machine per operating week
    remaining = s.spare_parts - consumed
    if remaining < 0:
        deficits.append("spare_parts")
        remaining = 0
    if s.operating_machines > 0 and not (s.tools_available and s.repair_knowledge_available):
        deficits.append("repair_prerequisites_missing")
    return replace(s, spare_parts=remaining), deficits


def _step_social(c: SocialCapacity) -> tuple[SocialCapacity, list[str]]:
    deficits: list[str] = []
    work = c.work_hours_per_week - c.weekly_work_needed
    care = c.care_hours_per_week - c.weekly_care_needed
    if work < 0:
        deficits.append("work_hours")
    if care < 0:
        deficits.append("care_hours")
    # Rest recovery tops the stock back up to a sane ceiling (60h/week).
    return replace(c, work_hours_per_week=min(max(work, 0.0) + c.weekly_rest_recovery_hours, 60.0),
                   care_hours_per_week=min(max(care, 0.0) + c.weekly_rest_recovery_hours, 60.0)), deficits


def simulate_weeks(nutrients: NutrientVector, energy: EnergyState,
                   spares: SparePartInventory, social: SocialCapacity,
                   weeks: int) -> list[WeekReport]:
    """Run a deterministic scenario for the given weeks.

    Determinism: no randomness, no wall clock, no I/O; the same inputs
    always yield the same reports. Outputs describe the SCENARIO, never
    a real site (MODEL != MEASUREMENT).
    """
    n, e, s, c = nutrients.validate(), energy.validate(), spares.validate(), social.validate()
    if type(weeks) is not int or weeks < 1 or weeks > 520:
        raise SimulationInputError("weeks must be an int in [1, 520]")
    reports: list[WeekReport] = []
    for week in range(1, weeks + 1):
        n, d1 = _step_nutrients(n)
        e, d2 = _step_energy(e)
        s, d3 = _step_spares(s)
        c, d4 = _step_social(c)
        deficits = tuple(d1 + d2 + d3 + d4)
        reports.append(WeekReport(
            week=week, ok=not deficits, deficits=deficits,
            state={"grain_kg": round(n.grain_kg, 3), "hay_kg": round(n.hay_kg, 3),
                   "protein_feed_kg": round(n.protein_feed_kg, 3),
                   "electricity_kwh": round(e.electricity_kwh, 3),
                   "heat_kwh": round(e.heat_kwh, 3), "water_m3": round(e.water_m3, 3),
                   "spare_parts": s.spare_parts,
                   "work_hours_per_week": round(c.work_hours_per_week, 3),
                   "care_hours_per_week": round(c.care_hours_per_week, 3)}))
    return reports
