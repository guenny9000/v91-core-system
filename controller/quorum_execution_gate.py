#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Quorum Execution Gate (MAX-BEST, VIBE-XXXII): die GETRENNTE Bruecke von
der Quorum-ENTSCHIEDUNG zur (hier: nur bewerteten) Ausfuehrungs-
Freigabe. Issue #167 Punkt 7: "Separate decision from execution".

Dieses Modul FUEHRT NICHTS AUS. Es enthaelt keinen Subprozess-, Netz-,
Datei- oder Betriebsteil. Es beantwortet nur EINE Frage:

  Duerfen zwei unabhaengige Quorum-Stimmen diese konkrete Aktion
  innerhalb einer BESTEHENDEN, vorab erklaerten Freigabe freigeben?

Antworten (nie vermischbar):
  EXECUTION_PERMITTED     Aktion ist vorab deklariert, risikoarm,
                           reversibel, lokal; Entscheidung ACCEPT;
                           Faehigkeit, Policy und Zustand stimmen.
                           (Trotzdem bleibt: FREIGABE != AUSGEFUEHRT.)
  HUMAN_APPROVAL_REQUIRED Externe Wirkung, irreversible oder
                           sensiblere Kategorien brauchen explizite
                           menschliche Freigabe. Dieses Modul gibt
                           dafuer NIE ein PERMITTED (KEIN UMGEHUNG).
  BLOCKED                 Kein Quorum, keine vorab erklaerte
                           Freigabe, Receiver-Recheck negativ oder
                           Eingabe ungueltig (fail-closed).

Regeln (fail-closed):
- QUORUM ERWEITERT NIE BERECHTIGUNGEN: Eine Stimmmehrheit kann nur eine
  Aktion innerhalb einer VORAB deklarierten Freigabe ermoeglichen; sie
  kann keine neue Freigabe erzeugen (ACCEPT != ERLAUBNIS).
- Receiver-Recheck: capability_ok, policy_ok und state_ok muessen
  UNMITTELBAR VOR Ausfuehrung vom Ausfuehrenden geprueft worden sein;
  fehlt eine, dann BLOCKED (GATE != ZEITPUNKT). Ein Recheck-Fehler
  blockt auch den Human-Approval-Pfad (BLOCKED ist staerker).
- Kategorien mit externer/irreversibler Wirkung (destructive, credential,
  financial, legal, public_communication, safety_critical, privilege,
  external_side_effect) sind NIE PERMITTED, immer HUMAN_APPROVAL_REQUIRED.
- UNKNOWN ist nie PASS; fehlende oder falsch getypte Eingaben werden
  verweigert, nie geraten.

REUSE (NO_DUPLICATE_SYSTEMS):
  agent_consensus.Decision   Entscheidungs-Enum (Import, kein Duplikat)
  quorum_decision            ENTSCHEIDUNG != AUSFUEHRUNG; dieses Modul
                             ist die getrennte Ausfuehrungs-Seite (#181).
  update_gate / use_policy   bestehende Policy-Gates bleiben
                             unberuehrt und sind getrennte Schichten.
  stewardship / emergency    Notfallpfade sind bewusst NICHT hier.

Honest limits:
GATE != AUSFUEHRUNG; FREIGABE != AUSGEFUEHRT; QUORUM != GEWISSEN
(Zustimmung beweist keine Richtigkeit, vgl. SIGNATUR != WAHRHEIT);
VORAB ERKLAERT != VORAB GEPRUEFT; SCRIPTED != INSTALLED; ein Tor auf
Papier schuetzt niemanden.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from controller.agent_consensus import Decision


class QuorumExecutionGateError(RuntimeError):
    """Fail-closed: unzulaessige Gate-Anfrage."""


VERDICT_EXECUTION_PERMITTED = "EXECUTION_PERMITTED"
VERDICT_HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
VERDICT_BLOCKED = "BLOCKED"
ALLOWED_VERDICTS = (VERDICT_EXECUTION_PERMITTED,
                    VERDICT_HUMAN_APPROVAL_REQUIRED,
                    VERDICT_BLOCKED)

SCOPE_LOCAL = "LOCAL"
LOW_RISK_CATEGORIES: tuple[str, ...] = (
    "report_draft", "ledger_append_local", "test_run", "inventory_read",
)
HUMAN_APPROVAL_CATEGORIES: tuple[str, ...] = (
    "external_side_effect", "destructive", "credential", "financial",
    "legal", "public_communication", "safety_critical", "privilege",
)
ALL_CATEGORIES = frozenset(LOW_RISK_CATEGORIES + HUMAN_APPROVAL_CATEGORIES)

HONEST_LIMITS: tuple[str, ...] =(
    "GATE != AUSFUEHRUNG: dieses Modul fuehrt nichts aus.",
    "FREIGABE != AUSGEFUEHRT: PERMITTED ist kein Ausfuehrungs-Nachweis.",
    "QUORUM != GEWISSEN: Zustimmung beweist keine Richtigkeit.",
    "Quorum erweitert nie Berechtigungen (ACCEPT != ERLAUBNIS).",
    "UNKNOWN ist nie PASS; ungueltige Anfragen werden verweigert.",
)


@dataclass(frozen=True)
class ActionGrant:
    """Vorab deklarierte Freigabe: risikoarm, reversibel, lokal."""
    action_id: str
    category: str
    scope: str = SCOPE_LOCAL
    reversible: bool = True


@dataclass(frozen=True)
class GateRequest:
    """Anfrage ans Tor. Entscheidung + vorab deklarierte Freigabe + Recheck."""
    decision: Decision
    grant: ActionGrant
    capability_ok: bool
    policy_ok: bool
    state_ok: bool
    revoked: bool = False


@dataclass(frozen=True)
class GateResult:
    verdict: str
    reasons: tuple
    honest_limits: tuple = HONEST_LIMITS


def validate_grant(grant: object) -> list[str]:
    """Fail-closed Pruefung einer vorab deklarierten Freigabe."""
    if not isinstance(grant, ActionGrant):
        raise QuorumExecutionGateError("grant must be an ActionGrant")
    problems: list[str] = []
    if not isinstance(grant.action_id, str) or not grant.action_id.strip():
        problems.append("action_id missing")
    if grant.category not in ALL_CATEGORIES:
        problems.append("unknown category: " + str(grant.category))
    if grant.scope != SCOPE_LOCAL:
        problems.append("scope must be LOCAL")
    if grant.reversible is not True:
        problems.append("grant must be reversible")
    return problems


def gate_execution(request: GateRequest,
                   predeclared: Sequence[ActionGrant]) -> GateResult:
    """Bewerte EINE Ausfuehrungs-Anfrage. Deterministisch, fail-closed.

    predeclared: die vom Betreiber VORAB (ausserhalb des Quorums)
    erklaerten Freigaben. Ein Quorum kann sie nicht erweitern.
    """
    if not isinstance(request, GateRequest):
        raise QuorumExecutionGateError("request must be a GateRequest")
    if not isinstance(predeclared, (list, tuple)):
        raise QuorumExecutionGateError("predeclared must be a list or tuple")

    reasons: list[str] = []

    if request.decision is not Decision.ACCEPT:
        reasons.append("decision is not ACCEPT: " + str(
            getattr(request.decision, "value", request.decision)))
        return GateResult(VERDICT_BLOCKED, tuple(sorted(reasons)))

    grant_problems = validate_grant(request.grant)
    if grant_problems:
        reasons.extend(grant_problems)
        return GateResult(VERDICT_BLOCKED, tuple(sorted(reasons)))

    if not _grant_is_predeclared(request.grant, predeclared):
        reasons.append("grant is not predeclared (quorum cannot expand "
                       "permissions)")
        return GateResult(VERDICT_BLOCKED, tuple(sorted(reasons)))

    if request.revoked is not False:
        reasons.append("grant revoked")
        return GateResult(VERDICT_BLOCKED, tuple(sorted(reasons)))

    rechecks = (
        ("capability_ok", request.capability_ok),
        ("policy_ok", request.policy_ok),
        ("state_ok", request.state_ok),
    )
    blocking_rechecks = [name for name, value in rechecks
                         if value is not True]
    if blocking_rechecks:
        reasons.append("receiver recheck failed: "
                       + ", ".join(blocking_rechecks))
        return GateResult(VERDICT_BLOCKED, tuple(sorted(reasons)))

    if request.grant.category in HUMAN_APPROVAL_CATEGORIES:
        reasons.append("category requires explicit human approval: "
                       + request.grant.category)
        return GateResult(VERDICT_HUMAN_APPROVAL_REQUIRED,
                          tuple(sorted(reasons)))

    reasons.append("predeclared low-risk reversible local grant; "
                   "decision ACCEPT; receiver rechecks passed")
    return GateResult(VERDICT_EXECUTION_PERMITTED, tuple(sorted(reasons)))


def _grant_is_predeclared(grant: ActionGrant,
                          predeclared: Sequence[ActionGrant]) -> bool:
    matched = False
    for declared in predeclared:
        if not isinstance(declared, ActionGrant):
            raise QuorumExecutionGateError(
                "predeclared entries must be ActionGrant objects")
        if declared == grant:
            matched = True
    return matched
