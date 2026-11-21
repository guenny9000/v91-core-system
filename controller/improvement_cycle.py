#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schoepfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Continuous improvement cycle (Issue #276, Faehigkeit 9, VIBE-XXXI).

Zweck: Jeder V91-Knoten und jede freiwillig teilnehmende Stelle darf
Verbesserungen PROAKTIV vorschlagen. Dieses Modul ordnet ein, ob ein
Vorschlag so dokumentiert ist, dass eine befugte menschliche Stelle
ihn autorisieren KANN. Es autorisiert selbst NIE
(ASSESSMENT != AUTHORIZATION; PROPOSAL != AUTHORIZATION).

REUSE (NO_DUPLICATE_SYSTEMS):
- Evidenz-Objekte: controller.impact_area_registry.EvidenceBundle.
- Zielkonflikt-/Rebound-Verdicts: Werte aus
  controller.rebound_conflict_check (ZIELKONFLIKT_BELEGT,
  NICHT_ENTSCHEIDBAR, VERTRAEGLICH_BELEGT) werden nur uebernommen,
  nie neu berechnet.
- Update-Staging/Promotion/Rollback der Artefakte bleibt
  controller/update_gate.py und controller/update_promotion.py.
- Vollstaendigkeit von Aenderungs-Entscheidungen im Betrieb bleibt
  controller/legacy_gate.py.

Fail-closed-Regeln:
- REQUEST != AUTHORIZATION; ein Vorschlag ohne gueltige
  Autorisierung bleibt VORSCHLAG, nie Freigabe.
- Autorisierung braucht eine ANDERE Identitaet als den Vorschlagenden
  (KEINE SELBSTAUTORISIERUNG) und muss denselben proposal_id nennen
  (falscher Umfang blockt).
- Regressionstests muessen als bestanden dokumentiert sein; ein
  nicht bestandener oder fehlender Test blockt
  (TESTS = PFLICHT; UNKNOWN != PASS).
- Rollout muss begrenzt sein: mindestens zwei aufsteigende Stufen,
  erste Stufe hoechstens 10 Prozent, Summe hoechstens 100 Prozent.
- Rollback-Plan und gepruefter Rollback sind Pflicht; IRREVERSIBEL
  wird immer geblockt (ISOLATE_NOT_DESTROY).
- Kritische Dienste (Notruf, Barrierefreiheit, Gesundheit,
  Energie, Transport, Zahlung) brauchen vor jeder Veraenderung
  einen dokumentierten Continuity-Nachweis; ohne ihn ist der
  Vorschlag NICHT_ENTSCHEIDBAR, niemals tauglich.
- Eine uebernommene Reboundpruefung mit ZIELKONFLIKT_BELEGT
  blockt final; NICHT_ENTSCHEIDBAR macht auch hier unentscheidbar.

Honest limits:
- VORSCHLAGTAUGLICH_BELEGT heisst 'dokumentiert entscheidbar durch
  eine befugte menschliche Stelle', nicht 'beschlossen, gebaut,
  installiert oder wirksam' (AUSGEFUELLT != GELEBT;
  STAGING != INSTALLATION; SCRIPTED != INSTALLED).
- Evidenz ist Dokumentation mit Quelle/Verfahren/Zeitraum,
  kein Wahrheitsbeweis (SOURCE != TRUTH).
- Nach-Aenderungs-Evidenz IST PFLICHT fuer das Outcome-Verdict;
  ohne gemessene Nach-Aenderungs-Daten bleibt es
  POST_CHANGE_PENDING (ZIELWERT != ERGEBNIS; PLAN != WIRKUNG).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from controller.impact_area_registry import (
    Area,
    EvidenceBundle,
    IndicatorDefinition,
    MeasurementScope,
)
from controller.impact_area_registry import (
    _validate_evidence,
)
from controller.rebound_conflict_check import (
    VERDICT_NICHT_ENTSCHEIDBAR,
    VERDICT_VERTRAEGLICH,
    VERDICT_ZIELKONFLIKT,
)


class ImprovementCycleError(RuntimeError):
    """Fail-closed: unzulaessige Nutzung des Pruefmoduls."""


MAX_FIRST_STAGE_FRACTION = 0.1
EPS = 1e-9

CRITICAL_SERVICE_KEYS: tuple[str, ...] = (
    "emergency",
    "accessibility",
    "healthcare",
    "energy",
    "transport",
    "payment",
)

VERDICT_ZIELKONFLIKT_BLOCK = "BLOCKIERT_ZIELKONFLIKT"
VERDICT_NOT_AUTHORIZED = "NICHT_AUTORISIERT"
VERDICT_UNDECIDABLE = "NICHT_ENTSCHEIDBAR"
VERDICT_READY = "VORSCHLAGTAUGLICH_BELEGT"
VERDICT_BLOCKED = "BLOCKIERT"

POST_CHANGE_PENDING = "POST_CHANGE_PENDING"
OUTCOME_VERBESSERT = "VERBESSERT_BELEGT"
OUTCOME_NICHT_VERBESSERT = "NICHT_VERBESSERT_BELEGT"

ALLOWED_REBOUND_VERDICTS: tuple[Optional[str], ...] = (
    None, VERDICT_ZIELKONFLIKT, VERDICT_NICHT_ENTSCHEIDBAR, VERDICT_VERTRAEGLICH)

CONTINUITY_INDICATOR = IndicatorDefinition(
    "critical_service_continuity_documented", Area.GEMEINWOHL,
    "Erreichbarkeit und Funktion des kritischen Dienstes waehrend "
    "der Migration dokumentiert",
    "boolean", MeasurementScope.LOCAL_ENVIRONMENT)


@dataclass(frozen=True)
class RolloutStage:
    """EINE begrenzte Ausbringungsstufe (Beschreibung, keine Ausfuehrung)."""
    label: str
    fraction: float


@dataclass(frozen=True)
class TestRecord:
    """Dokumentierter Regressionstest der Aenderung."""
    regression_ok: bool
    evidence: EvidenceBundle


@dataclass(frozen=True)
class AuthorizationRecord:
    """Explizite, befristete Autorisierung durch eine ANDERE Identitaet."""
    authorized_by: str
    proposal_id: str
    scope: str
    expires: str


@dataclass(frozen=True)
class ImprovementProposal:
    """Reine Beschreibung eines Verbesserungsvorschlags. Keine Ausfuehrung."""
    proposal_id: str
    node_id: str
    proposer: str
    target_component: str
    description: str
    goal: str
    is_critical_service: bool = False
    critical_service_key: Optional[str] = None
    continuity_evidence: Optional[EvidenceBundle] = None
    tests: Optional[TestRecord] = None
    authorization: Optional[AuthorizationRecord] = None
    irreversible: bool = False
    rollback_plan: str = ""
    rollback_tested: bool = False
    rollout_stages: Sequence[RolloutStage] = field(default_factory=tuple)
    rebound_verdict: Optional[str] = None


@dataclass(frozen=True)
class OutcomeReport:
    """Nach-Aenderungs-Evidenz. PLAN != WIRKUNG."""
    achieved_value: float
    target_value: float
    unit: str
    evidence: EvidenceBundle


def _nonempty(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ImprovementCycleError("%s missing" % name)


def _proposal_ok(proposal: ImprovementProposal) -> None:
    if not isinstance(proposal, ImprovementProposal):
        raise ImprovementCycleError("proposal must be an ImprovementProposal")
    _nonempty(proposal.proposal_id, "proposal_id")
    _nonempty(proposal.node_id, "node_id")
    _nonempty(proposal.proposer, "proposer")
    _nonempty(proposal.target_component, "target_component")
    _nonempty(proposal.description, "description")
    _nonempty(proposal.goal, "goal")
    if not isinstance(proposal.is_critical_service, bool):
        raise ImprovementCycleError("is_critical_service must be boolean")
    if proposal.is_critical_service:
        if proposal.critical_service_key not in CRITICAL_SERVICE_KEYS:
            raise ImprovementCycleError(
                "critical_service_key must be one of %s"
                % ", ".join(CRITICAL_SERVICE_KEYS))
        if not isinstance(proposal.continuity_evidence, EvidenceBundle):
            raise ImprovementCycleError(
                "critical service needs continuity_evidence")
    if proposal.tests is not None and not isinstance(proposal.tests, TestRecord):
        raise ImprovementCycleError("tests must be None or TestRecord")
    if proposal.authorization is not None and not isinstance(
            proposal.authorization, AuthorizationRecord):
        raise ImprovementCycleError(
            "authorization must be None or AuthorizationRecord")
    if not isinstance(proposal.irreversible, bool):
        raise ImprovementCycleError("irreversible must be boolean")
    if proposal.rebound_verdict not in ALLOWED_REBOUND_VERDICTS:
        raise ImprovementCycleError(
            "rebound_verdict must be None or a known rebound verdict")
    if not isinstance(proposal.rollout_stages, Sequence):
        raise ImprovementCycleError("rollout_stages must be a sequence")
    for stage in proposal.rollout_stages:
        if not isinstance(stage, RolloutStage):
            raise ImprovementCycleError("rollout stage must be RolloutStage")
        _nonempty(stage.label, "stage label")
        if not isinstance(stage.fraction, (int, float)) \
                or not 0.0 < float(stage.fraction) <= 1.0:
            raise ImprovementCycleError(
                "stage fraction must be in (0.0, 1.0]")


def _rollout_ok(stages: Sequence[RolloutStage]) -> dict[str, Any]:
    """Begrenzter Rollout: klein anfangen, nie > 100 Prozent."""
    problems: list[str] = []
    if len(stages) < 2:
        problems.append("MIN_2_STAGES")
    if stages:
        first = float(stages[0].fraction)
        if first > MAX_FIRST_STAGE_FRACTION + EPS:
            problems.append("FIRST_STAGE_MAX_10_PERCENT")
        last = 0.0
        ascending = True
        for stage in stages:
            value = float(stage.fraction)
            if value < last - EPS:
                ascending = False
            last = max(last, value)
        if not ascending:
            problems.append("STAGES_MUST_ASCEND")
        total = sum(float(s.fraction) for s in stages)
        if total > 1.0 + EPS:
            problems.append("SUM_MAX_100_PERCENT")
    return {"ok": not problems, "problems": problems}


def _continuity_ok(proposal: ImprovementProposal) -> dict[str, Any]:
    """Kritische Dienste: Continuity-Nachweis vor Veraenderung."""
    if not proposal.is_critical_service:
        return {"ok": True, "problems": []}
    evidence = proposal.continuity_evidence
    if not isinstance(evidence, EvidenceBundle):
        return {"ok": False, "problems": ["CONTINUITY_EVIDENCE_MISSING"]}
    problems = _validate_evidence(evidence)
    return {"ok": not problems, "problems": problems}


def _authorization_ok(proposal: ImprovementProposal) -> dict[str, Any]:
    """REQUEST != AUTHORIZATION; KEINE SELBSTAUTORISIERUNG."""
    if not proposal.authorization:
        return {"ok": False, "problems": ["NOT_AUTHORIZED"]}
    problems: list[str] = []
    record = proposal.authorization
    if record.authorized_by.strip() == proposal.proposer.strip():
        problems.append("SELF_AUTHORIZATION_REFUSED")
    if record.proposal_id != proposal.proposal_id:
        problems.append("WRONG_PROPOSAL_SCOPE")
    _nonempty(record.scope, "authorization scope")
    _nonempty(record.expires, "authorization expires")
    return {"ok": not problems, "problems": problems}


def _tests_ok(proposal: ImprovementProposal) -> dict[str, Any]:
    """TESTS = PFLICHT; UNKNOWN != PASS."""
    tests = proposal.tests
    if not isinstance(tests, TestRecord):
        return {"ok": False, "problems": ["TESTS_MISSING"]}
    problems: list[str] = []
    if tests.regression_ok is not True:
        problems.append("REGRESSION_NOT_PROVEN")
    problems.extend(_validate_evidence(tests.evidence))
    return {"ok": not problems, "problems": problems}


def _rollback_ok(proposal: ImprovementProposal) -> dict[str, Any]:
    """Rollback Pflicht; IRREVERSIBEL blockt immer."""
    problems: list[str] = []
    if proposal.irreversible:
        problems.append("IRREVERSIBLE_BLOCKED")
    _nonempty(proposal.rollback_plan, "rollback_plan")
    if not problems and not proposal.rollback_plan.strip():
        problems.append("ROLLBACK_PLAN_MISSING")
    if proposal.rollback_tested is not True:
        problems.append("ROLLBACK_NOT_TESTED")
    return {"ok": not problems, "problems": problems}


def evaluate_proposal(proposal: ImprovementProposal) -> dict[str, Any]:
    """Vollstaendige Vorschlagspruefung mit Verdict. Fail-closed.

    Verdicts:
    - BLOCKIERT_ZIELKONFLIKT: uebernommene Reboundpruefung belegt
      einen Zielkonflikt (Bridge aus rebound_conflict_check).
    - NICHT_AUTORISIERT: keine gueltige Autorisierung.
    - BLOCKIERT: Tests/Rollout/Rollback reglementwidrig oder
      IRREVERSIBEL.
    - NICHT_ENTSCHEIDBAR: kritischer Dienst ohne Continuity-Nachweis,
      Rebound unentscheidbar oder Vorschlag unvollstaendig.
    - VORSCHLAGTAUGLICH_BELEGT: dokumentiert entscheidbar durch eine
      befugte menschliche Stelle (kein Beschluss).
    """
    _proposal_ok(proposal)
    blocking: list[str] = []
    undecidable: list[str] = []

    if proposal.rebound_verdict == VERDICT_ZIELKONFLIKT:
        blocking.append("REBOUND_ZIELKONFLIKT")
    elif proposal.rebound_verdict == VERDICT_NICHT_ENTSCHEIDBAR:
        undecidable.append("REBOUND_UNDECIDABLE")

    auth = _authorization_ok(proposal)
    tests = _tests_ok(proposal)
    rollout = _rollout_ok(proposal.rollout_stages)
    rollback = _rollback_ok(proposal)
    continuity = _continuity_ok(proposal)

    if not auth["ok"]:
        blocking.extend(auth["problems"])
    if not tests["ok"]:
        blocking.extend(tests["problems"])
    if not rollout["ok"]:
        blocking.extend(rollout["problems"])
    if not rollback["ok"]:
        blocking.extend(rollback["problems"])
    if not continuity["ok"]:
        undecidable.extend(continuity["problems"])

    if blocking:
        verdict = (VERDICT_ZIELKONFLIKT_BLOCK
                   if "REBOUND_ZIELKONFLIKT" in blocking else VERDICT_BLOCKED)
        if not auth["ok"]:
            verdict = VERDICT_NOT_AUTHORIZED
    elif undecidable:
        verdict = VERDICT_UNDECIDABLE
    else:
        verdict = VERDICT_READY

    return {
        "proposal_id": proposal.proposal_id,
        "verdict": verdict,
        "authorization_ok": auth["ok"],
        "tests_ok": tests["ok"],
        "rollout_ok": rollout["ok"],
        "rollback_ok": rollback["ok"],
        "continuity_ok": continuity["ok"],
        "blocking_reasons": sorted(set(blocking)),
        "undecidable_reasons": sorted(set(undecidable)),
    }


def outcome_status(outcome: Optional[OutcomeReport]) -> dict[str, Any]:
    """Nach-Aenderungs-Status. Ohne Messung bleibt POST_CHANGE_PENDING.

    ZIELWERT != ERGEBNIS: eine gemessene Verschlechterung wird NICHT
    nachtraeglich zur Verbesserung erklaert (Ehrlichkeitsgebot).
    """
    if outcome is None:
        return {"status": POST_CHANGE_PENDING,
                "evidence_ok": False,
                "problems": ["POST_CHANGE_EVIDENCE_MISSING"]}
    if not isinstance(outcome, OutcomeReport):
        raise ImprovementCycleError("outcome must be None or OutcomeReport")
    problems = _validate_evidence(outcome.evidence)
    if not isinstance(outcome.unit, str) or not outcome.unit.strip():
        problems.append("UNIT_MISSING")
    if problems:
        return {"status": POST_CHANGE_PENDING,
                "evidence_ok": False,
                "problems": sorted(set(problems))}
    status = (OUTCOME_VERBESSERT
              if outcome.achieved_value <= outcome.target_value
              else OUTCOME_NICHT_VERBESSERT)
    return {"status": status, "evidence_ok": True, "problems": []}


def cycle_report(proposal: ImprovementProposal,
                 outcome: Optional[OutcomeReport] = None) -> dict[str, Any]:
    """Sammelbericht: Vorschlag und (optional) Outcome in EINEM Bericht."""
    assessment = evaluate_proposal(proposal)
    assessment["outcome"] = outcome_status(outcome)
    return assessment
