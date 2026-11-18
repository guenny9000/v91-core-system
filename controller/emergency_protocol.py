#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Emergency protocol decision support (Notfall- und Eingriffsregeln,
Beschluss 2026-11-01; Issue #70 environment, own systems only).

This module ENCODES the decided crisis rules as testable, deterministic
logic. It DOES NOT act: no actuators, no network, no shutdown, no
process control. Every output is a recommendation plus the explicit
statement which human authorization is still required
(AUTORISIERUNG != BESCHLUSS != DURCHFÜHRUNG).

Encoded rules (from the 2026-11-01 decision):
- Normalfall: prevent damage, isolate causes, transform harmful
  structures where possible -> NO intervention protocol
- Akuter Notfall: if human life is directly threatened, protecting
  life has priority; a necessary, limited intervention MAY be
  proposed, and only with explicit human authorization
- Kleineres Übel: if full damage prevention is impossible, the
  measure with the least expected total harm must be chosen
- Verhältnismäßigkeit: only as far as required (minimal scope)
- Schutz Unbeteiligter: human rights and basic supply stay protected
- Kontrolle: measures must be traceable, time-limited, verifiable
  and recorded in the ledger
- Wiederherstellung: after the danger ends, restrictions must be
  rolled back and damages repaired
- Grundsatz: V91 never autonomously decides over life, death or the
  fate of population groups

Honest limits: DECISION SUPPORT != DECISION; input facts are caller
claims, not verified reality (CLAIM != EVIDENCE); no sensor fusion;
single call, no state, no daemon; ledger recording is the caller's
responsibility, this module only demands it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class EmergencyProtocolError(Exception):
    """Fail-closed protocol error."""


@dataclass(frozen=True)
class CrisisMeasure:
    """One candidate measure, described by the caller (a claim, not a fact)."""
    measure_id: str
    description: str
    expected_lives_saved: int
    expected_total_harm: int          # non-negative scale agreed by the caller
    protects_uninvolved: bool
    time_limited: bool
    reversible: bool
    scope: str                         # "minimal" | "extended"


@dataclass(frozen=True)
class CrisisSituation:
    """Explicitly described crisis. All fields are caller claims."""
    situation_id: str
    description: str
    human_life_directly_threatened: bool
    full_prevention_possible: bool


@dataclass(frozen=True)
class ProtocolDecision:
    protocol: str                      # "NO_INTERVENTION" | "LIFE_PRIORITY_LIMITED_INTERVENTION" | "LEAST_HARM_CHOICE"
    requires_human_authorization: bool
    selected_measure_id: str | None
    rationale: tuple[str, ...]
    required_controls: tuple[str, ...]


_CONTROLS = (
    "Zeitlich begrenzt dokumentieren",
    "Im Ledger protokollieren",
    "Überprüfbare Erfolgskriterien festlegen",
    "Wiederherstellung nach Gefahrenende einplanen",
)


def evaluate_crisis(
    situation: CrisisSituation,
    measures: list[CrisisMeasure],
) -> ProtocolDecision:
    """Deterministically apply the decided emergency rules.

    Fail-closed: malformed input raises instead of guessing.
    This function never executes anything and never authorizes by
    itself; every intervention decision requires a human.
    """
    _validate_situation(situation)
    if not isinstance(measures, list):
        raise EmergencyProtocolError("measures must be a list of CrisisMeasure")
    for m in measures:
        _validate_measure(m)

    rationale: list[str] = []

    if not situation.human_life_directly_threatened:
        rationale.append("Keine direkte Lebensbedrohung beschrieben -> Normalfall-Regeln")
        return ProtocolDecision(
            protocol="NO_INTERVENTION",
            requires_human_authorization=False,
            selected_measure_id=None,
            rationale=tuple(rationale),
            required_controls=("Schäden verhindern, Ursachen isolieren, Strukturen transformieren",),
        )

    rationale.append("Direkte Lebensbedrohung beschrieben -> Menschenschutz > Optimierung")
    if not measures:
        rationale.append(
            "Keine Maßnahme beschrieben: Protokoll erlaubt notwendigen begrenzten "
            "Eingriff, erfindet aber keine Maßnahme; menschliche Entscheidung erforderlich")
        return ProtocolDecision(
            protocol="LIFE_PRIORITY_LIMITED_INTERVENTION",
            requires_human_authorization=True,
            selected_measure_id=None,
            rationale=tuple(rationale),
            required_controls=_CONTROLS,
        )

    admissible = [
        m for m in measures
        if m.protects_uninvolved and m.time_limited and m.reversible and m.scope == "minimal"
    ]
    rejected = [m for m in measures if m not in admissible]
    if rejected:
        rationale.append(
            f"{len(rejected)} Maßnahme(n) verworfen: Schutz Unbeteiligter, "
            "Begrenztheit, Umkehrbarkeit oder minimaler Umfang nicht erfüllt")
    if not admissible:
        rationale.append(
            "Keine zulässige Maßnahme nach Schutzregeln: FAIL-CLOSED, kein Vorschlag; "
            "menschliche Entscheidung erforderlich")
        return ProtocolDecision(
            protocol="LIFE_PRIORITY_LIMITED_INTERVENTION",
            requires_human_authorization=True,
            selected_measure_id=None,
            rationale=tuple(rationale),
            required_controls=_CONTROLS,
        )

    if situation.full_prevention_possible:
        chosen = min(admissible, key=lambda m: (m.expected_total_harm, -m.expected_lives_saved, m.measure_id))
        rationale.append("Vollständige Schadensvermeidung möglich -> Verhältnismäßigkeit: minimale Maßnahme")
        return ProtocolDecision(
            protocol="LIFE_PRIORITY_LIMITED_INTERVENTION",
            requires_human_authorization=True,
            selected_measure_id=chosen.measure_id,
            rationale=tuple(rationale),
            required_controls=_CONTROLS,
        )

    chosen = min(admissible, key=lambda m: (m.expected_total_harm, -m.expected_lives_saved, m.measure_id))
    rationale.append("Vollständige Vermeidung unmöglich -> Kleineres-Übel-Regel: geringster erwartbarer Gesamtschaden")
    rationale.append("Grundsatz gewahrt: keine eigenmächtige Entscheidung, Ausführung nur nach menschlicher Freigabe")
    return ProtocolDecision(
        protocol="LEAST_HARM_CHOICE",
        requires_human_authorization=True,
        selected_measure_id=chosen.measure_id,
        rationale=tuple(rationale),
        required_controls=_CONTROLS,
    )


def _validate_situation(s: Any) -> None:
    if not isinstance(s, CrisisSituation):
        raise EmergencyProtocolError("situation must be a CrisisSituation")
    if not isinstance(s.situation_id, str) or not s.situation_id or len(s.situation_id) > 64:
        raise EmergencyProtocolError("situation_id must be a non-empty string (<= 64 chars)")
    if not isinstance(s.description, str) or not s.description.strip():
        raise EmergencyProtocolError("a non-empty situation description is required")
    if type(s.human_life_directly_threatened) is not bool:
        raise EmergencyProtocolError("human_life_directly_threatened must be a bool")
    if type(s.full_prevention_possible) is not bool:
        raise EmergencyProtocolError("full_prevention_possible must be a bool")


def _validate_measure(m: Any) -> None:
    if not isinstance(m, CrisisMeasure):
        raise EmergencyProtocolError("each measure must be a CrisisMeasure")
    if not isinstance(m.measure_id, str) or not m.measure_id:
        raise EmergencyProtocolError("measure_id must be a non-empty string")
    if not isinstance(m.description, str) or not m.description.strip():
        raise EmergencyProtocolError("a non-empty measure description is required")
    for name in ("expected_lives_saved", "expected_total_harm"):
        value = getattr(m, name)
        if type(value) is not int or value < 0:
            raise EmergencyProtocolError(f"{name} must be a non-negative int")
    for name in ("protects_uninvolved", "time_limited", "reversible"):
        if type(getattr(m, name)) is not bool:
            raise EmergencyProtocolError(f"{name} must be a bool")
    if m.scope not in ("minimal", "extended"):
        raise EmergencyProtocolError("scope must be 'minimal' or 'extended'")
