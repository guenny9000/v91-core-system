#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Rebound- und Zielkonfliktpruefung (MAX-BEST, VIBE-XXIX).

Dieses Modul verhindert, dass eine Massnahme nur auf ihr Primaerziel
hin bewertet wird (z. B. Importabhaengigkeit senken) und dabei
Nebenwirkungen ueberhoert werden: Emissionen, Umweltbelastung,
soziale Ungleichheit, Ressourcenverbrauch. Eine einseitig
angelegte Massnahme wird NIE als vertraeglich eingestuft.

REUSE (NO_DUPLICATE_SYSTEMS): Statusmodell und Bericht kommen aus
controller/impact_area_registry.py (BELEGT / NICHT_GEPRUEFT /
NICHT_VERFUEGBAR). Wirkungsmessungen bleiben impact.py,
wirkungs_assessment.py und autarky_metrics.py ueberlassen;
dieses Modul ordnet nur ein.

Fuer Max-Best-Regeln kodiert:
- Jede der vier Konfliktdimensionen braucht eine dokumentierte
  Wirkungsrichtung (REDUCES / NEUTRAL / INCREASES) mit Evidenz
  (Quelle, Verfahren, Zeitraum). CLAIM != EVIDENCE.
- INCREASES in einer Dimension -> ZIELKONFLIKT_BELEGT.
- Ungepruefte oder evidenzlose Dimensionen machen die Massnahme
  NICHT_ENTSCHEIDBAR (UNKNOWN != PASS, nie still vertraeglich).
- Effizienzgewinn ohne belegte Netto-Reduktion des Ressourcen-
  einsatzes -> REBOUND_RISIKO_OFFEN (Jevons-Direktrebound).
- Datensatzangaben sind keine geprueften Messwerte
  (DATENSATZANGABE != GEPRUEFTE_MESSUNG; DURCHSCHNITT !=
  BEWEIS_REALER_UNABHAENGIGKEIT; KAPAZITAET != VERFUEGBARE_RESERVE;
  HEIMISCHE_GEWINNUNG != LIEFERKETTENFREIHEIT).

Honest limits: BELEGT ist Beleg-Nachweis, kein Wahrheitsbeweis
(SOURCE != TRUTH); VERTRAEGLICH_BELEGT gilt fuer diesen einen
geprueften Schnitt, nicht fuer die Folgewirkung
(ASSESSMENT != AUTHORIZATION, VERTRAEGLICHKEIT != BESCHLUSS,
SIMULATION != BETRIEB).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional

from controller.impact_area_registry import (
    Area,
    EvidenceBundle,
    IndicatorDefinition,
    MeasurementClaim,
    MeasurementScope,
    registry_report,
)


class ReboundConflictError(RuntimeError):
    """Fail-closed: unzulaessige Nutzung des Pruefmoduls."""


class Direction(str, Enum):
    """Wirkungsrichtung einer Konfliktdimension (keine Werte erfunden)."""
    REDUCES = "REDUCES"
    NEUTRAL = "NEUTRAL"
    INCREASES = "INCREASES"


@dataclass(frozen=True)
class DirectionImpact:
    """Dokumentierte Wirkungsrichtung EINER Dimension, mit Evidenz."""
    direction: Direction
    evidence: EvidenceBundle


@dataclass(frozen=True)
class MeasureProposal:
    """Reine Beschreibung einer Massnahme zur Konfliktpruefung."""
    measure_id: str
    goal: str
    claimed_primary_effect: str
    is_efficiency_gain: bool = False
    secondary_impacts: Mapping[str, Optional[DirectionImpact]] = None

    def __post_init__(self) -> None:
        if self.secondary_impacts is None:
            object.__setattr__(self, "secondary_impacts", {})


CONFLICT_DIMENSIONS: tuple[IndicatorDefinition, ...] = (
    IndicatorDefinition("conflict_emissions_assessed", Area.KLIMA,
                        "Treibhausgas- und Schadstoffwirkung der Massnahme geprueft",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("conflict_environmental_burden_assessed", Area.KLIMA,
                        "Umweltbelastung (Flaeche, Wasser, Abfall, Biodiversitaet) geprueft",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("conflict_social_equity_assessed", Area.GEMEINWOHL,
                        "Wirkung auf soziale Ungleichheit und Betroffene geprueft",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("conflict_resource_use_assessed", Area.AUTARKIE,
                        "Netto-Ressourcen- und Energieverbrauch geprueft",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
)

DIMENSION_KEYS: tuple[str, ...] = tuple(d.key for d in CONFLICT_DIMENSIONS)

VERDICT_ZIELKONFLIKT = "ZIELKONFLIKT_BELEGT"
VERDICT_NICHT_ENTSCHEIDBAR = "NICHT_ENTSCHEIDBAR"
VERDICT_VERTRAEGLICH = "VERTRAEGLICH_BELEGT"


def _proposal_ok(proposal: MeasureProposal) -> None:
    if not isinstance(proposal, MeasureProposal):
        raise ReboundConflictError("proposal must be a MeasureProposal")
    if not isinstance(proposal.measure_id, str) or not proposal.measure_id.strip():
        raise ReboundConflictError("measure_id missing")
    if not isinstance(proposal.goal, str) or not proposal.goal.strip():
        raise ReboundConflictError("goal missing")
    if not isinstance(proposal.claimed_primary_effect, str) \
            or not proposal.claimed_primary_effect.strip():
        raise ReboundConflictError("claimed_primary_effect missing")
    if not isinstance(proposal.is_efficiency_gain, bool):
        raise ReboundConflictError("is_efficiency_gain must be a boolean")
    if not isinstance(proposal.secondary_impacts, Mapping):
        raise ReboundConflictError("secondary_impacts must be a mapping")
    for key, impact in proposal.secondary_impacts.items():
        if key not in DIMENSION_KEYS:
            raise ReboundConflictError("unknown conflict dimension: %s" % key)
        if impact is not None and not isinstance(impact, DirectionImpact):
            raise ReboundConflictError(
                "dimension %s must be None or a DirectionImpact" % key)


def rebound_risk(proposal: MeasureProposal) -> bool:
    """Direktrebound-Risiko: Effizienzgewinn ohne Netto-Ressourcennachweis.

    Ein Effizienzgewinn ist solange offen, bis die Ressourcen-Dimension
    mit REDUCES belegt ist (Jevons: Effizienz kann Mehrverbrauch loesen).
    """
    _proposal_ok(proposal)
    if not proposal.is_efficiency_gain:
        return False
    impact = proposal.secondary_impacts.get("conflict_resource_use_assessed")
    if not isinstance(impact, DirectionImpact):
        return True
    return impact.direction != Direction.REDUCES


def assess_conflicts(proposal: MeasureProposal) -> dict:
    """Konfliktmatrix mit Verdict. Fail-closed, ohne erfundene Zahlen.

    - INCREASES  -> ZIELKONFLIKT_BELEGT (Dimension benannt)
    - ungeprueft -> NICHT_ENTSCHEIDBAR (UNKNOWN != PASS)
    - alle belegt ohne INCREASES -> VERTRAEGLICH_BELEGT
    Evidenzlose Wirkungsrichtungen werden auf NICHT_GEPRUEFT
    herabgestuft, nie als BELEGT gelogen (CLAIM != EVIDENCE).
    """
    _proposal_ok(proposal)
    submissions: dict[str, object] = {}
    directions: dict[str, Optional[str]] = {}
    evidence_problems: dict[str, list[str]] = {}
    for key in DIMENSION_KEYS:
        impact = proposal.secondary_impacts.get(key)
        if not isinstance(impact, DirectionImpact):
            submissions[key] = None
            directions[key] = None
            continue
        evidence = impact.evidence
        if not isinstance(evidence, EvidenceBundle):
            evidence_problems[key] = ["evidence bundle missing"]
            submissions[key] = None
            directions[key] = None
            continue
        source_ok = isinstance(evidence.source, str) and evidence.source.strip()
        method_ok = isinstance(evidence.method, str) and evidence.method.strip()
        if not (source_ok and method_ok):
            evidence_problems[key] = ["source or method missing (CLAIM != EVIDENCE)"]
            submissions[key] = None
            directions[key] = None
            continue
        submissions[key] = MeasurementClaim(1.0, "boolean", evidence)
        directions[key] = impact.direction.value

    report = registry_report(list(CONFLICT_DIMENSIONS), submissions)

    adverse = [key for key in DIMENSION_KEYS if directions[key] == Direction.INCREASES.value]
    unknown = [key for key in DIMENSION_KEYS if directions[key] is None]

    problems: list[str] = []
    for key in adverse:
        problems.append("ZIELKONFLIKT in %s: Wirkungsrichtung INCREASES belegt" % key)
    for key in unknown:
        problems.append("Dimension %s nicht geprueft (UNKNOWN != PASS)" % key)
    for key, probs in evidence_problems.items():
        problems.extend("Dimension %s: %s" % (key, p) for p in probs)

    if rebound_risk(proposal):
        problems.append(
            "REBOUND_RISIKO_OFFEN: Effizienzgewinn ohne belegte "
            "Netto-Reduktion des Ressourceneinsatzes")

    if adverse:
        verdict = VERDICT_ZIELKONFLIKT
    elif unknown:
        verdict = VERDICT_NICHT_ENTSCHEIDBAR
    else:
        verdict = VERDICT_VERTRAEGLICH

    result = dict(report)
    result["schema"] = "v91.rebound_conflict_check.v1"
    result["proposal"] = {
        "measure_id": proposal.measure_id.strip(),
        "goal": proposal.goal.strip(),
        "claimed_primary_effect": proposal.claimed_primary_effect.strip(),
        "is_efficiency_gain": proposal.is_efficiency_gain,
    }
    result["directions"] = directions
    result["rebound_risk_open"] = rebound_risk(proposal)
    result["verdict"] = verdict
    result["problems"] = problems
    result["honest_limits"] = report["honest_limits"] + (
        "DATENSATZANGABE != GEPRUEFTE_MESSUNG: Vorgabewerte sind keine Messungen.",
        "DURCHSCHNITT != BEWEIS_REALER_UNABHAENGIGKEIT (z. B. rechnerische Selbstversorgungsgrade).",
        "KAPAZITAET != VERFUEGBARE_RESERVE (technisches Volumen ist kein Verfuegbarkeitsnachweis).",
        "HEIMISCHE_GEWINNUNG != LIEFERKETTENFREIHEIT (Pumpen, Ersatzteile, Energie, Aufbereitung).",
        "VERTRAEGLICH_BELEGT gilt nur fuer die hier geprueften Dimensionen (PRUEFUNG != FOLGEWIRKUNG).",
    )
    return result
