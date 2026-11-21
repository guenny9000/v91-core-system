#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Quorum Status Report (MAX-BEST, VIBE-XXXIII): Issue #167 Punkt 10.
"Melden Sie Status getrennt: DESIGNED, IMPLEMENTED, UNIT_TESTED,
API_INTEGRATION_VERIFIED, QUORUM_VERIFIED, EXECUTION_VERIFIED."

Dieses Modul ERZEUGT KEINE STATUS. Es haelt nur fest, was ein Caller
mit BELASTBARER EVIDENZ meldet, und verweigert alles andere
(CLAIM != EVIDENCE). Ein Statusbericht ersetzt keine Pruefung.

Statusstufen (geordnet, nie ueberspringbar):
  DESIGNED             Entwurf existiert und ist benannt.
  IMPLEMENTED           Code existiert am benannten Ort.
  UNIT_TESTED           Deterministische Tests liefen und sind benannt.
  API_INTEGRATION_VERIFIED  Echte Provider-Konfiguration wurde expli-
                        zititv benannt (NIE aus Unit-Tests ableitbar).
  QUORUM_VERIFIED       Echte Quorum-Entscheidung ist belegt.
  EXECUTION_VERIFIED    Echte Ausfuehrung ist belegt.

Kernregeln (fail-closed):
- EVIDENZ ZWINGEND: Jede Stufe verlangt einen passenden Evidence-Typ.
  Falscher Typ, leere Zeile oder zu langer Text wird verweigert.
- NIE SPRINGEN: Eine Komponente kann nur um EINE Stufe vorruecken,
  wenn die Stufe davor bereits registriert war (KEIN WUNDER).
- KEINE STILLE RUECKSTUFE: Regression nur per explizitem
  reset_component mit begruendetem Rueckgabewert (SELFHEAL != RESET).
- SELF-PROMOTION-SPERRE: API_INTEGRATION_VERIFIED verlangt zwingend
  evidence_kind PROVIDER_CONFIG; EXECUTION_VERIFIED verlangt
  EXECUTION_RECEIPT. Etwas anderes (z. B. UNIT_RUN) ist unzulaessig:
  ein Unit-Test beweist NIE eine echte Integration oder Ausfuehrung
  (UNIT_TESTED != API_INTEGRATION_VERIFIED != EXECUTION_VERIFIED).
- UNKNOWN ist nie PASS.

REUSE (NO_DUPLICATE_SYSTEMS):
  status_exchange      Foederations-Knotenstatus (Issue #103) ist ein
                       anderes Protokoll (Fremd-Beschreibung); hier
                       geht es um Evidenz-Stufen der Quorum-Kette.
  daily_report         Operative Tagesberichte bleiben dort.
  provider_health      Advisory Zustaende (DEGRADED etc.) sind KEINE
                       Verifikations-Stufen; keine Ueberschneidung.
  audit                CLAIM != EVIDENCE ist hier nur angewandt.

Honest limits:
BERICHT != BEWEIS (ein Registry-Eintrag prueft die Evidenz nicht
selbst nach, der Caller benennt sie nur); REGISTRIERT != WAHR;
SCRIPTED != INSTALLED; API-Integration bleibt so lange UNKNOWN, bis
eine echte Konfiguration existiert (Issue #167 Grenze: echte Keys
entscheidet nur Sebastian).
"""
from __future__ import annotations

MAX_COMPONENT_BYTES = 64
MAX_EVIDENCE_BYTES = 200

VERIFICATION_STAGES = (
    "DESIGNED",
    "IMPLEMENTED",
    "UNIT_TESTED",
    "API_INTEGRATION_VERIFIED",
    "QUORUM_VERIFIED",
    "EXECUTION_VERIFIED",
)
_STAGE_INDEX = {name: i for i, name in enumerate(VERIFICATION_STAGES)}

# Zulaessige Evidence-Typen je Stufe (SELF-PROMOTION-SPERRE).
_REQUIRED_EVIDENCE_KINDS = {
    "DESIGNED": frozenset({"DESIGN_DOC"}),
    "IMPLEMENTED": frozenset({"MODULE_PATH"}),
    "UNIT_TESTED": frozenset({"UNIT_RUN"}),
    "API_INTEGRATION_VERIFIED": frozenset({"PROVIDER_CONFIG"}),
    "QUORUM_VERIFIED": frozenset({"QUORUM_DECISION"}),
    "EXECUTION_VERIFIED": frozenset({"EXECUTION_RECEIPT"}),
}
_EVIDENCE_FIELDS = frozenset({"kind", "detail"})


class QuorumStatusReportError(ValueError):
    """Raised when a status registration or report is invalid (fail-closed)."""


class Evidence:
    """Named evidence for one verification stage (CLAIM != EVIDENCE)."""

    __slots__ = ("kind", "detail")

    def __init__(self, kind: str, detail: str) -> None:
        if not isinstance(kind, str) or not isinstance(detail, str):
            raise QuorumStatusReportError("evidence fields must be str")
        if len(detail.encode("utf-8")) > MAX_EVIDENCE_BYTES:
            raise QuorumStatusReportError("evidence detail too long")
        if not detail.strip():
            raise QuorumStatusReportError("evidence detail empty")
        _ = kind.strip()
        if not _:
            raise QuorumStatusReportError("evidence kind empty")
        self.kind = kind
        self.detail = detail

    def asdict(self) -> dict:
        return {"kind": self.kind, "detail": self.detail}


class QuorumStatusRegistry:
    """Registry of component verification stages (evidence-bound)."""

    def __init__(self) -> None:
        self._stages: dict[str, str] = {}
        self._evidence: dict[str, dict] = {}

    def register(self, component: str, stage: str, evidence: Evidence) -> str:
        """Register or advance one component by exactly one stage."""
        self._validate_component(component)
        if stage not in _STAGE_INDEX:
            raise QuorumStatusReportError("unknown stage: %r" % (stage,))
        if not isinstance(evidence, Evidence):
            raise QuorumStatusReportError("evidence must be Evidence instance")
        if evidence.kind not in _REQUIRED_EVIDENCE_KINDS[stage]:
            raise QuorumStatusReportError(
                "evidence kind %r not allowed for stage %s" % (evidence.kind, stage))
        current = self._stages.get(component)
        if current is None:
            if stage != VERIFICATION_STAGES[0]:
                raise QuorumStatusReportError(
                    "first registration must be DESIGNED, not %s" % (stage,))
        else:
            delta = _STAGE_INDEX[stage] - _STAGE_INDEX[current]
            if delta <= 0:
                raise QuorumStatusReportError(
                    "stage regression/skip refused (current: %s)" % (current,))
            if delta > 1:
                raise QuorumStatusReportError(
                    "stage jump refused: %s -> %s" % (current, stage))
        self._stages[component] = stage
        self._evidence[component] = evidence.asdict()
        return stage

    def reset_component(self, component: str, reason: str) -> None:
        """Explicit, reasoned removal (KEINE STILLE RUECKSTUFE)."""
        self._validate_component(component)
        if not isinstance(reason, str) or not reason.strip():
            raise QuorumStatusReportError("reset reason empty")
        if component not in self._stages:
            raise QuorumStatusReportError("unknown component: %r" % (component,))
        del self._stages[component]
        del self._evidence[component]

    def stage_of(self, component: str) -> str:
        try:
            return self._stages[component]
        except KeyError:
            raise QuorumStatusReportError(
                "unknown component: %r" % (component,)) from None

    def report(self) -> list[dict]:
        """Sorted full report (copy; caller-owned)."""
        return [
            {"component": c, "stage": self._stages[c], "evidence": dict(self._evidence[c])}
            for c in sorted(self._stages)
        ]

    def summary(self) -> dict:
        counts = {name: 0 for name in VERIFICATION_STAGES}
        for stage in self._stages.values():
            counts[stage] += 1
        return dict(counts)

    @staticmethod
    def _validate_component(component: str) -> None:
        if not isinstance(component, str) or not component.strip():
            raise QuorumStatusReportError("component name empty")
        if len(component.encode("utf-8")) > MAX_COMPONENT_BYTES:
            raise QuorumStatusReportError("component name too long")


def parse_evidence(mapping: object) -> Evidence:
    """Parse untrusted evidence mapping (fail-closed, exact fields)."""
    if not isinstance(mapping, dict):
        raise QuorumStatusReportError("evidence must be a mapping")
    if set(mapping) != _EVIDENCE_FIELDS:
        raise QuorumStatusReportError("evidence fields mismatch")
    return Evidence(mapping["kind"], mapping["detail"])
