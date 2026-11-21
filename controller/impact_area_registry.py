#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schoepfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Impact-Area-Registry (MAX-BEST, VIBE-XXVII): einheitliches, ueberpruefbares
Statusmodell fuer fuenf Wirkungsbereiche (Klima, Frieden, Autarkie,
Determinismus, Gemeinwohl).

Dieses Modul erfindet KEINE Messwerte, KEINE Messverfahren und KEINE
Fortschrittsprozente. Es klassifiziert Indikatoren und ihre Belege in
genau drei Statuswerte:
  BELEGT           Messwert + Quelle + Verfahren + Zeitraum liegen vor.
  NICHT_GEPRUEFT   Es liegen noch keine ausreichenden Messdaten vor.
  NICHT_VERFUEGBAR Die noetigen Daten oder Moeglichkeiten fehlen.

REUSE (NO_DUPLICATE_SYSTEMS): Messverfahren bleiben bestehenden Modulen
ueberlassen; dieses Modul ordnet nur ein:
  impact.py             Wirkungsvergleich aus realen CSV-Messreihen
  wirkungs_assessment.py Initiativ-Bewertung hinter vier Prueftoren
  autarky_metrics.py    lokale Autarkie-Kennzahlen (Issue #83)
  measurement_core.py   Host-Messungen und Hash-Chain-Ledger
REGISTRY != MESSGERAET; STATUS != MESSWERT; BEREICH != WELT.

Honest limits:
- EXTERNAL_WORLD-Indikatoren (globale Kriege, globale Emissionen) sind
  ohne vertrauenswuerdige externe Quellen NICHT_VERFUEGBAR; ein lokales
  System ist keine Weltmessstelle (LOCAL != GLOBAL).
- BELEGT ist ein Beleg-Nachweis, kein Wahrheitsbeweis
  (SIGNATUR != WAHRHEIT; SOURCE != TRUTH).
- Fortschrittsprozente werden NIE ausgegeben; Fortschritt entsteht nur
  aus Messwerten in wirkungs_assessment.py, nie hier ( PERCENT != PROOF ).
- ASSESSMENT != AUTHORIZATION: Diese Klassifikation berechtigt zu nichts;
  reale Interventionen brauchen rechtliche Grundlage und menschliche
  Freigabe (EVALUATION != AUTHORIZATION, UNKNOWN != PASS).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Mapping, Optional, Sequence


class ImpactAreaRegistryError(RuntimeError):
    """Fail-closed: unzulaessige Registernutzung."""


class Area(str, Enum):
    KLIMA = "KLIMA"
    FRIEDEN = "FRIEDEN"
    AUTARKIE = "AUTARKIE"
    DETERMINISMUS = "DETERMINISMUS"
    GEMEINWOHL = "GEMEINWOHL"


class IndicatorStatus(str, Enum):
    BELEGT = "BELEGT"
    NICHT_GEPRUEFT = "NICHT_GEPRUEFT"
    NICHT_VERFUEGBAR = "NICHT_VERFUEGBAR"
    TEILWEISE_VERFUEGBAR = "TEILWEISE_VERFUEGBAR"


class MeasurementScope(str, Enum):
    LOCAL_HOST = "LOCAL_HOST"
    LOCAL_ENVIRONMENT = "LOCAL_ENVIRONMENT"
    EXTERNAL_WORLD = "EXTERNAL_WORLD"


@dataclass(frozen=True)
class IndicatorDefinition:
    key: str
    area: Area
    question: str
    unit: str
    scope: MeasurementScope


@dataclass(frozen=True)
class EvidenceBundle:
    source: str
    method: str
    period_start: str
    period_end: str
    reference: str = ""


@dataclass(frozen=True)
class MeasurementClaim:
    """Antrag auf BELEGT: ein Messwert plus vollstaendige Belege."""
    value: float
    unit: str
    evidence: EvidenceBundle


@dataclass(frozen=True)
class UnavailableClaim:
    """Antrag auf NICHT_VERFUEGBAR: ehrliche Fehlanzeige mit Begruendung."""
    reason: str


def _valid_period(period_start: str, period_end: str) -> bool:
    try:
        start = datetime.fromisoformat(str(period_start).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(period_end).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if start.tzinfo is None or end.tzinfo is None:
        return False
    return start <= end


def _validate_evidence(evidence: EvidenceBundle) -> list[str]:
    problems: list[str] = []
    if not isinstance(evidence.source, str) or not evidence.source.strip():
        problems.append("source missing")
    if not isinstance(evidence.method, str) or not evidence.method.strip():
        problems.append("method missing")
    if not _valid_period(evidence.period_start, evidence.period_end):
        problems.append("period invalid (two ISO-8601 timestamps, start <= end)")
    if not isinstance(evidence.reference, str):
        problems.append("reference must be a string (may be empty)")
    return problems


def assess_indicator(definition: IndicatorDefinition,
                     submission) -> dict:
    """Klassifiziere EINEN Indikator. Fail-closed, deterministisch.

    - None (kein Antrag)            -> NICHT_GEPRUEFT
    - UnavailableClaim mit Grund    -> NICHT_VERFUEGBAR
    - MeasurementClaim nur mit vollstaendiger Evidenz und endlichen,
      nicht-negativen Zahlenwerten in der definierenden Einheit -> BELEGT
    - ungueltiger Antrag            -> NICHT_GEPRUEFT (nie BELEGT gelogen)
    """
    if not isinstance(definition, IndicatorDefinition):
        raise ImpactAreaRegistryError("definition must be an IndicatorDefinition")
    base = {
        "key": definition.key,
        "area": definition.area.value,
        "unit": definition.unit,
        "scope": definition.scope.value,
    }
    if submission is None:
        return {**base, "status": IndicatorStatus.NICHT_GEPRUEFT,
                "problems": ["no measurement submitted"]}
    if isinstance(submission, UnavailableClaim):
        if not isinstance(submission.reason, str) or not submission.reason.strip():
            return {**base, "status": IndicatorStatus.NICHT_GEPRUEFT,
                    "problems": ["unavailable claim without reason"]}
        return {**base, "status": IndicatorStatus.NICHT_VERFUEGBAR,
                "reason": submission.reason.strip(), "problems": []}
    if isinstance(submission, MeasurementClaim):
        problems = []
        if not isinstance(submission.evidence, EvidenceBundle):
            problems.append("evidence bundle missing")
        else:
            problems.extend(_validate_evidence(submission.evidence))
        value = submission.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problems.append("value must be numeric")
        else:
            value_f = float(value)
            if not math.isfinite(value_f) or value_f < 0:
                problems.append("value must be finite and non-negative")
        if submission.unit != definition.unit:
            problems.append("unit mismatch with definition")
        if problems:
            return {**base, "status": IndicatorStatus.NICHT_GEPRUEFT,
                    "problems": problems}
        result = {**base, "status": IndicatorStatus.BELEGT,
                  "value": float(value), "problems": []}
        for field_name in ("source", "method", "period_start", "period_end"):
            result[field_name] = getattr(submission.evidence, field_name)
        result["reference"] = submission.evidence.reference
        return result
    raise ImpactAreaRegistryError(
        "submission must be None, UnavailableClaim or MeasurementClaim")


def _area_status(counts: Mapping[str, int]) -> str:
    belegt = counts.get("BELEGT", 0)
    offen = counts.get("NICHT_GEPRUEFT", 0)
    fehlend = counts.get("NICHT_VERFUEGBAR", 0)
    if belegt + offen + fehlend == 0:
        raise ImpactAreaRegistryError("area has no indicators")
    if offen:
        return IndicatorStatus.NICHT_GEPRUEFT.value
    if fehlend == 0:
        return IndicatorStatus.BELEGT.value
    if belegt == 0:
        return IndicatorStatus.NICHT_VERFUEGBAR.value
    return IndicatorStatus.TEILWEISE_VERFUEGBAR.value


def registry_report(registry: Sequence[IndicatorDefinition],
                    submissions: Mapping[str, object]) -> dict:
    """Vollstaendiger Bericht. Enthaelt NIE Prozente oder Zielerreichung.

    Ein Bereich ist nur BELEGT, wenn JEDER seiner Indikatoren BELEGT ist;
    sonst verschachtelt NICHT_GEPRUEFT; reine Fehlanzeigen werden ehrlich
    als NICHT_VERFUEGBAR bzw. TEILWEISE_VERFUEGBAR ausgewiesen.
    """
    if not isinstance(registry, (list, tuple)) or not registry:
        raise ImpactAreaRegistryError("registry must be a non-empty sequence")
    if not isinstance(submissions, Mapping):
        raise ImpactAreaRegistryError("submissions must be a mapping")
    keys = [definition.key for definition in registry]
    if len(set(keys)) != len(keys):
        raise ImpactAreaRegistryError("duplicate indicator keys in registry")
    for key in submissions:
        if key not in keys:
            raise ImpactAreaRegistryError(f"submission for unknown indicator: {key}")

    areas: dict[str, dict[str, int]] = {area.value: {"BELEGT": 0, "NICHT_GEPRUEFT": 0, "NICHT_VERFUEGBAR": 0} for area in Area}
    indicators = {}
    for definition in registry:
        result = assess_indicator(definition, submissions.get(definition.key))
        indicators[definition.key] = result
        areas[result["area"]][result["status"]] += 1

    per_area = {}
    for area_name, counts in areas.items():
        if sum(counts.values()) == 0:
            continue
        per_area[area_name] = {
            "counts": dict(counts),
            "status": _area_status(counts),
        }
    total = {status: sum(counts[status] for counts in areas.values())
             for status in ("BELEGT", "NICHT_GEPRUEFT", "NICHT_VERFUEGBAR")}
    return {
        "schema": "v91.impact_area_registry.v1",
        "indicators": indicators,
        "areas": per_area,
        "overall_counts": total,
        "overall_status": (
            IndicatorStatus.NICHT_GEPRUEFT.value
            if total["NICHT_GEPRUEFT"] else
            IndicatorStatus.BELEGT.value
            if total["NICHT_VERFUEGBAR"] == 0 else
            IndicatorStatus.TEILWEISE_VERFUEGBAR.value
            if total["BELEGT"] else
            IndicatorStatus.NICHT_VERFUEGBAR.value),
        "honest_limits": (
            "BELEGT ist Beleg-Nachweis, kein Wahrheitsbeweis (SOURCE != TRUTH).",
            "EXTERNAL_WORLD-Indikatoren brauchen vertrauenswuerdige externe Quellen (LOCAL != GLOBAL).",
            "Keine Fortschrittsprozente: Fortschritt nur aus Messwerten (PERCENT != PROOF).",
            "ASSESSMENT != AUTHORIZATION; reale Interventionen brauchen Freigabe.",
            "UNKNOWN ist nie PASS.",
        ),
    }


def verify_determinism(func: Callable[..., object], inputs: Sequence[object]) -> bool:
    """Determinismus-Nachweis-Helfer: gleiche Eingaben, gleiches Ergebnis.

    Zwei Laeufe, kanonischer JSON-Vergleich. Kein Zeit-, Zufalls- oder
    Umgebungszugriff in func erlaubt (Aufrufer verantwortet die Reinheit).
    """
    if not callable(func) or not isinstance(inputs, (list, tuple)):
        raise ImpactAreaRegistryError("func must be callable and inputs a sequence")
    try:
        first = [func(item) for item in inputs]
        second = [func(item) for item in inputs]
    except Exception:
        raise ImpactAreaRegistryError("deterministic evaluation raised; fail-closed")
    canonical = lambda results: json.dumps(
        results, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False, default=str)
    return canonical(first) == canonical(second)


DEFAULT_REGISTRY: tuple[IndicatorDefinition, ...] = (
    IndicatorDefinition("climate_emission_reduction_vs_base_year", Area.KLIMA,
                        "Treibhausgas-Reduktion gegenueber einem festen Basisjahr",
                        "tCO2e", MeasurementScope.EXTERNAL_WORLD),
    IndicatorDefinition("aviation_emissions_share", Area.KLIMA,
                        "Anteil des Luftverkehrs an den Gesamtemissionen",
                        "%", MeasurementScope.EXTERNAL_WORLD),
    IndicatorDefinition("active_armed_conflicts", Area.FRIEDEN,
                        "Zahl aktiver bewaffneter Konflikte im Zeitraum",
                        "conflicts", MeasurementScope.EXTERNAL_WORLD),
    IndicatorDefinition("civilian_casualties", Area.FRIEDEN,
                        "Zivile Todesopfer und Verletzte im Zeitraum",
                        "persons", MeasurementScope.EXTERNAL_WORLD),
    IndicatorDefinition("energy_self_sufficiency_share", Area.AUTARKIE,
                        "Lokaler Anteil eigener Energieversorgung (vgl. autarky_metrics)",
                        "share_0_1", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("critical_provider_dependency_count", Area.AUTARKIE,
                        "Anzahl unabhaengiger kritischer Einzelanbieter",
                        "providers", MeasurementScope.LOCAL_HOST),
    IndicatorDefinition("measurement_reproducibility", Area.DETERMINISMUS,
                        "Gleiche Eingaben und Version ergeben gleiche Ergebnisse",
                        "boolean", MeasurementScope.LOCAL_HOST),
    IndicatorDefinition("unknown_handling_defined", Area.DETERMINISMUS,
                        "Undefinierte Daten fuehren zu UNKNOWN, nie zu PASS",
                        "boolean", MeasurementScope.LOCAL_HOST),
    IndicatorDefinition("essential_supply_coverage", Area.GEMEINWOHL,
                        "Versorgungsgrad mit existentiellen Guetern im Wirkungskreis",
                        "share_0_1", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("distribution_fairness_index", Area.GEMEINWOHL,
                        "Messbare Verteilungsgerechtigkeit im Wirkungskreis",
                        "index", MeasurementScope.LOCAL_ENVIRONMENT),
)
