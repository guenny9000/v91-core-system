#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Improvement Cycle (MAX-BEST, VIBE-XXXIII): ehrlicher Lebenszyklus fuer
Verbesserungsvorschlaege (Issue #276, Faehigkeit 9: kontinuierliche
Verbesserung - jeder Knoten DARF vorschlagen, aber Veraenderungen
brauchen Autorisierung, Tests, begrenzten Rollout, Rollback und
Nach-aenderungs-Evidenz).

Dieses Modul wertet NUR aus. Es führt NICHTS aus: kein Deployment,
kein Daemon, kein Netz. Der Zyklus hat zwei Tore:

Tor 1: evaluate_proposal
  APPROVED_FOR_BOUNDED_ROLLOUT  (nur wenn ALLE Pflichten vorliegen)
  BLOCKED                       (sonst; mit benannten Problemen)
Pflichten: explizite menschliche Autorisierung mit Referenz, gruen
DOKUMENTIERTE Tests (tests_green + EvidenceBundle), BEGRENZTER Rollout
(betroffene Knoten <= Obergrenze, Beobachtungszeitraum > 0), benannter
Rollback-Zielzustand (ISOLATE_NOT_DESTROY; Versions bleiben erhalten),
und ein vorab definierter Nach-aenderungs-Check.

Tor 2: record_post_change
  ROLLOUT_DONE_EVIDENCED        (Nach-aenderungs-Evidenz gueltig,
                                 keine Regression)
  ROLLBACK_RECOMMENDED          (Regression gefunden: REGRESSION >
                                 Theorie; NICHT als Verbesserung
                                 verzeichnet, Rollback-Ziel benannt)
  BLOCKED                       (Eingabe fehlt/ungueltig; ein nicht
                                 bewerteter Ablauf ist KEINE Wirkung)
Die Nach-aenderungs-Evidenz MUSS das Proposal referenzieren
(reference == proposal_id), sonst zaehlt sie fuer dieses Proposal nicht
(FREMDEVIDENZ != NACHWEIS).

Fail-closed:
- UNKNOWN ist nie PASS; fehlende oder falsch getypte Felder blocken.
- Autorisierung ist ein NEUTRALER Boolescher Eintrag des Menschen, keine
  Selbstautorisierung des Vorschlags (KEINE_AUSNAHME).
- KEINE Erfolgsquoten, KEINE Prozente: nur NACHWEIS-Status, nie
  Zielerreichung ( PROZENT != NACHWEIS ).

REUSE (NO_DUPLICATE_SYSTEMS):
  impact_area_registry  EvidenceBundle + Beleg-Validierung (Import)
  update_promotion      tatsaechliches Rollback behaelt Versionen bei
                        (Durchfuehrung, getrennt; dieses Modul bewertet
                        nur den ZYKLUS, es rollt nichts zurueck)
  governance_gate       Pre-Change-Audit bleibt eigene Schicht
  quorum_execution_gate Ausfuehrungsbewertung bleibt getrennt

Honest limits:
VORSCHLAG != VERBESSERUNG; APPROVED != AUSGEFUEHRT; ROLLOUT != WIRKUNG;
EVIDENZ_VON_LETZTER_HAND != WAHRHEIT (SOURCE != TRUTH); VERBESSERUNG
ORGANISIERT != VERBESSERUNG BEWIESEN.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from controller.impact_area_registry import (
    EvidenceBundle,
    _validate_evidence,
)


class ImprovementCycleError(RuntimeError):
    """Fail-closed: unzulaessiger Zyklus-Zustand."""


VERDICT_APPROVED_FOR_BOUNDED_ROLLOUT = "APPROVED_FOR_BOUNDED_ROLLOUT"
VERDICT_BLOCKED = "BLOCKED"
VERDICT_ROLLOUT_DONE_EVIDENCED = "ROLLOUT_DONE_EVIDENCED"
VERDICT_ROLLBACK_RECOMMENDED = "ROLLBACK_RECOMMENDED"
ALLOWED_VERDICTS: tuple[str, ...] = (
    VERDICT_APPROVED_FOR_BOUNDED_ROLLOUT,
    VERDICT_BLOCKED,
    VERDICT_ROLLOUT_DONE_EVIDENCED,
    VERDICT_ROLLBACK_RECOMMENDED,
)

MAX_AFFECTED_NODES = 10  # begrenzter Rollout: klein, nicht flaechendeckend


HONEST_LIMITS: tuple[str, ...] = (
    "VORSCHLAG != VERBESSERUNG: ein bewilligter Plan ist kein Ergebnis.",
    "APPROVED != AUSGEFUEHRT: dieses Modul deployt nichts.",
    "ROLLOUT != WIRKUNG: bewertete Evidenz ist keine Wirkung.",
    "REGRESSION > Theorie: bei Regressionsnachweis wird der Rollback empfohlen.",
    "UNKNOWN ist nie PASS; fehlende Felder blocken den Zyklus.",
    "Keine Prozente, keine Zielerreichung (PROZENT != NACHWEIS).",
)


@dataclass(frozen=True)
class RolloutPlan:
    """Begrenzter Rollout: kleine Zahl betroffener Knoten, Beobachtung, Rollback."""
    affected_nodes: int
    observation_period_hours: int
    rollback_target: str


@dataclass(frozen=True)
class ImprovementProposal:
    """Ein Verbesserungsvorschlag mit allen Pflicht-Feldern des Zyklus."""
    proposal_id: str
    description: str
    owner: str
    human_authorized: bool
    authorization_reference: str
    tests_green: bool
    test_evidence: Optional[EvidenceBundle]
    rollout: RolloutPlan
    post_change_check: str


def _int_or_problem(value: object, minimum: int,
                    problems: list[str], label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        problems.append(label + " must be an integer")
    elif value < minimum:
        problems.append(label + f" must be >= {minimum}")


def evaluate_proposal(proposal: ImprovementProposal) -> dict:
    """Tor 1: Bewertung EINES Vorschlags. Deterministisch, fail-closed."""
    if not isinstance(proposal, ImprovementProposal):
        raise ImprovementCycleError("proposal must be an ImprovementProposal")

    problems: list[str] = []
    if not isinstance(proposal.proposal_id, str) or not proposal.proposal_id.strip():
        problems.append("proposal_id missing")
    if not isinstance(proposal.description, str) or not proposal.description.strip():
        problems.append("description missing")
    if not isinstance(proposal.owner, str) or not proposal.owner.strip():
        problems.append("owner missing")

    if proposal.human_authorized is not True:
        problems.append("human authorization missing (REQUEST != AUTHORIZATION)")
    elif (not isinstance(proposal.authorization_reference, str)
          or not proposal.authorization_reference.strip()):
        problems.append("authorization reference missing")

    if proposal.tests_green is not True:
        problems.append("tests not documented green (SCRIPTED != TESTED)")
    elif not isinstance(proposal.test_evidence, EvidenceBundle):
        problems.append("test evidence bundle missing")
    else:
        problems.extend("test evidence: " + p
                        for p in _validate_evidence(proposal.test_evidence))

    if not isinstance(proposal.rollout, RolloutPlan):
        problems.append("rollout plan missing or malformed")
    else:
        _int_or_problem(proposal.rollout.affected_nodes, 1,
                        problems, "rollout affected_nodes")
        if (not isinstance(proposal.rollout.affected_nodes, bool)
                and isinstance(proposal.rollout.affected_nodes, int)
                and proposal.rollout.affected_nodes > MAX_AFFECTED_NODES):
            problems.append(
                "rollout not bounded: affected_nodes > "
                + str(MAX_AFFECTED_NODES))
        _int_or_problem(proposal.rollout.observation_period_hours, 1,
                        problems, "rollout observation_period_hours")
        if (not isinstance(proposal.rollout.rollback_target, str)
                or not proposal.rollout.rollback_target.strip()):
            problems.append("rollback target missing (ISOLATE_NOT_DESTROY)")

    if (not isinstance(proposal.post_change_check, str)
            or not proposal.post_change_check.strip()):
        problems.append("post-change check not defined")

    if problems:
        return {"schema": "v91.improvement_cycle.v1",
                "proposal_id": proposal.proposal_id,
                "verdict": VERDICT_BLOCKED,
                "problems": tuple(sorted(problems)),
                "honest_limits": HONEST_LIMITS}
    return {"schema": "v91.improvement_cycle.v1",
            "proposal_id": proposal.proposal_id,
            "verdict": VERDICT_APPROVED_FOR_BOUNDED_ROLLOUT,
            "problems": (),
            "honest_limits": HONEST_LIMITS}


def record_post_change(proposal: ImprovementProposal,
                       post_evidence: EvidenceBundle,
                       regression_found: bool) -> dict:
    """Tor 2: Nach-aenderungs-Bewertung. Fail-closed, nie Erfolgsquote.

    post_evidence.reference MUSS proposal_id sein: Evidenz ohne
    Rueckbezug zaehlt als FREMDEVIDENZ, nicht als Nachweis.
    """
    if not isinstance(proposal, ImprovementProposal):
        raise ImprovementCycleError("proposal must be an ImprovementProposal")
    approve = evaluate_proposal(proposal)
    base = {"schema": "v91.improvement_cycle.v1",
            "proposal_id": proposal.proposal_id,
            "honest_limits": HONEST_LIMITS}
    if approve["verdict"] != VERDICT_APPROVED_FOR_BOUNDED_ROLLOUT:
        return {**base, "verdict": VERDICT_BLOCKED,
                "problems": ("approval gate not passed: "
                              + "; ".join(approve["problems"]),)}
    if not isinstance(post_evidence, EvidenceBundle):
        raise ImprovementCycleError("post_evidence must be an EvidenceBundle")
    if regression_found is not True and regression_found is not False:
        raise ImprovementCycleError("regression_found must be a boolean")
    evid_problems = _validate_evidence(post_evidence)
    if post_evidence.reference != proposal.proposal_id:
        evid_problems.append("reference mismatch: evidence does not name "
                             "this proposal (FREMDEVIDENZ != NACHWEIS)")
    if evid_problems:
        return {**base, "verdict": VERDICT_BLOCKED,
                "problems": ("post-change evidence: "
                              + "; ".join(evid_problems),)}
    if regression_found is True:
        return {**base, "verdict": VERDICT_ROLLBACK_RECOMMENDED,
                "problems": (),
                "rollback_target": proposal.rollout.rollback_target,
                "regression_found": True}
    return {**base, "verdict": VERDICT_ROLLOUT_DONE_EVIDENCED,
            "problems": (),
            "regression_found": False,
            "post_evidence_source": post_evidence.source,
            "post_evidence_method": post_evidence.method}
