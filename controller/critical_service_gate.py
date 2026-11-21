#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schoepfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Critical Service Gate (MAX-BEST, VIBE-XXXIV): Continuity-Nachweis-Pflicht
fuer Veraenderungen an kritischen Diensten BEFORE sie stattfinden
(Issue #167 Betriebsteile; bereichert Faehigkeit 9 von Issue #276):
Waehrend einer Veraenderung eines kritischen Dienstes muss belegt
bleiben, dass Erreichbarkeit und Funktion des Dienstes dokumentiert
sind. Ohne gueltigen Nachweis ist die Veraenderung NICHT_ENTSCHEIDBAR.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from controller.impact_area_registry import (
    EvidenceBundle,
    _validate_evidence,
)


class CriticalServiceGateError(RuntimeError):
    """Fail-closed: unzulaessiger Gate-Zustand."""


VERDICT_CONTINUITY_BELEGT = "CONTINUITY_BELEGT"
VERDICT_UNDECIDABLE = "NICHT_ENTSCHEIDBAR"
VERDICT_BLOCKED = "BLOCKED"
ALLOWED_VERDICTS: tuple[str, ...] = (
    VERDICT_CONTINUITY_BELEGT,
    VERDICT_UNDECIDABLE,
    VERDICT_BLOCKED,
)

CRITICAL_SERVICE_KEYS: tuple[str, ...] = (
    "emergency",
    "accessibility",
    "healthcare",
    "energy",
    "transport",
    "payment",
)

HONEST_LIMITS: tuple[str, ...] = (
    "EVIDENZ != KONTINUITAET_WIRKLICH: dokumentiert ist nicht gewaehrleistet.",
    "BELEGT != STOERFREIHEIT: ein Nachweis ist keine Messreihe waehrend des Betriebs.",
    "UNKNOWN ist nie PASS: fehlende Evidenz blockt.",
    "Keine Prozente, keine Verfuegbarkeitsquoten (PROZENT != NACHWEIS).",
    "ASSESSMENT != AUTORISIERUNG: dieses Modul genehmigt nichts.",
)


@dataclass(frozen=True)
class ContinuityCheck:
    """Continuity-Antrag fuer EINE Veraenderung an EINEM Dienst."""
    service_key: str
    change_description: str
    responsible: str
    method: str
    evidence: Optional[EvidenceBundle]


def evaluate_continuity(check: ContinuityCheck) -> dict:
    """Tor: Bewertung eines Continuity-Antrags. Fail-closed.

    - Strukturfehler (unbekannter Dienst, fehlende Pflichtfelder)
      -> BLOCKED
    - fehlende/ungueltige/uneindeutige Evidenz -> NICHT_ENTSCHEIDBAR
    - gueltige Evidenz mit Continuity-Bezug und Referenz
      -> CONTINUITY_BELEGT
    """
    if not isinstance(check, ContinuityCheck):
        raise CriticalServiceGateError("check must be a ContinuityCheck")

    problems: list[str] = []
    if check.service_key not in CRITICAL_SERVICE_KEYS:
        problems.append("service_key unknown or not critical")
    if not isinstance(check.change_description, str) or not check.change_description.strip():
        problems.append("change_description missing")
    if not isinstance(check.responsible, str) or not check.responsible.strip():
        problems.append("responsible missing")
    if not isinstance(check.method, str) or not check.method.strip():
        problems.append("method missing")
    if not isinstance(check.evidence, EvidenceBundle):
        problems.append("continuity evidence missing")
    if problems:
        return {"schema": "v91.critical_service_gate.v1",
                "service_key": check.service_key,
                "verdict": VERDICT_BLOCKED,
                "problems": tuple(sorted(problems)),
                "honest_limits": HONEST_LIMITS}

    evid_problems = list(_validate_evidence(check.evidence))
    if not check.evidence.reference.strip():
        evid_problems.append("evidence reference missing (FREMDEVIDENZ != NACHWEIS)")
    method_lower = check.evidence.method.strip().lower()
    if ("continuit" not in method_lower
            and "kontinuitaet" not in method_lower
            and "erreichbarkeit" not in method_lower):
        evid_problems.append("evidence method does not address continuity")
    if (isinstance(check.change_description, str)
            and check.change_description.strip()
            and check.evidence.reference.strip()
            and check.evidence.reference.strip() == "verkettet"):
        evid_problems.append("placeholder reference refused")
    if evid_problems:
        return {"schema": "v91.critical_service_gate.v1",
                "service_key": check.service_key,
                "verdict": VERDICT_UNDECIDABLE,
                "problems": tuple(sorted(evid_problems)),
                "honest_limits": HONEST_LIMITS}

    return {"schema": "v91.critical_service_gate.v1",
            "service_key": check.service_key,
            "verdict": VERDICT_CONTINUITY_BELEGT,
            "problems": (),
            "evidence_source": check.evidence.source,
            "evidence_method": check.evidence.method,
            "honest_limits": HONEST_LIMITS}


def gate_report(checks) -> dict:
    """Sammelbericht: ALLE muessen BELEGT sein, sonst kein Gesamt-BELEGT.

    Ein einziger NICHT_ENTSCHEIDBAR macht den Gesamtbefund
    NICHT_ENTSCHEIDBAR; ein einziger BLOCKED macht ihn BLOCKED
    (MINDESTENS_EINS != ALLE; UNKNOWN != PASS).
    """
    if not isinstance(checks, (list, tuple)) or not checks:
        raise CriticalServiceGateError("checks must be a non-empty sequence")
    results = []
    worst = VERDICT_CONTINUITY_BELEGT
    for item in checks:
        result = evaluate_continuity(item)
        results.append(result)
        v = result["verdict"]
        if v == VERDICT_BLOCKED:
            worst = VERDICT_BLOCKED
            break
        if v == VERDICT_UNDECIDABLE and worst != VERDICT_BLOCKED:
            worst = VERDICT_UNDECIDABLE
    return {"schema": "v91.critical_service_gate.v1",
            "overall_verdict": worst,
            "results": tuple(results),
            "honest_limits": HONEST_LIMITS}
