#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Gemeinwohlpruefung (MAX-BEST, VIBE-XXX).

Dieses Modul prueft eine Gemeinwohl-Initiative (Beschreibungs-Vorlage,
keine Ausfuehrung) gegen die ACHT SCHUTZREGELN des
V91-LERNBLOCK-GEMEINWOHLDIENST und die Mindestanforderungen einer
Messmatrix: Ausgangswert + Zielwert + Quelle + Verfahren + Zeitraum
+ Pruefer. Ohne beides bleibt die Initiative NICHT_ENTSCHEIDBAR
(MATRIZ != WIRKUNG; MANIFEST != MESSPLAN).

REUSE (NO_DUPLICATE_SYSTEMS):
- Statusmodell, EvidenceBundle und Berichtsaufbau aus
  controller/impact_area_registry.py (#288).
- Zielkonflikt-Verdicts aus controller/rebound_conflict_check.py
  (#291): NICHTS wird hier dupliziert; das Rebound-Ergebnis wird
  als Verdict uebernommen und blockt bei ZIELKONFLIKT_BELEGT
  bzw. haelt NICHT_ENTSCHEIDBAR aufrecht.
- Messmatrizen selbst bleiben in docs/messmatrix/*.json
  (z. B. pilot-i); dieses Modul prueft nur Anforderungen.

Fuer Max-Best-Regeln kodiert (Lernblock-Abschnitt 4):
1. Freiwilligkeit als Grundprinzip, keine Zwangsverpflichtung.
2. Keine Benachteiligung von Menschen mit Behinderungen/Pflegebedarf.
3. Anerkennung unterschiedlicher Leistungsfaehigkeit.
4. Aufwandsentschaedigung und soziale Absicherung.
5. Keine Verdraengung reguljaerer Arbeitsplaetze.
6. Datenschutz und Schutz vor Missbrauch (politisch/wirtschaftlich).
7. Unabhaengige Erfolgskontrolle.
8. Der Dienst darf NICHT zum Kontrollinstrument werden.
Jede Regel braucht eine dokumentierte Umsetzungs-Evidenz
(Quelle, Verfahren, Zeitraum); reine Behauptung zaehlt nicht
(CLAIM != EVIDENCE; AUSGEFUELLT != GELEBT: Selbstauskunft bleibt
Selbstauskunft, UNKNOWN != PASS).

Honest limits: MATRIZ != WIRKUNG; ZIELWERT != ERGEBNIS;
BELEGT ist Beleg-Nachweis, kein Wahrheitsbeweis (SOURCE != TRUTH);
REVIEW != ENTSCHEIDUNG (gesellschaftliche Entscheidungen gehoeren
dem Souveraenen); ASSESSMENT != AUTHORIZATION; SIMULATION != BETRIEB.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from controller.impact_area_registry import (
    Area,
    EvidenceBundle,
    IndicatorDefinition,
    MeasurementClaim,
    MeasurementScope,
    _valid_period,
    registry_report,
)
from controller.rebound_conflict_check import (
    VERDICT_NICHT_ENTSCHEIDBAR,
    VERDICT_VERTRAEGLICH,
    VERDICT_ZIELKONFLIKT,
)


class GemeinwohlError(RuntimeError):
    """Fail-closed: unzulaessige Nutzung des Pruefmoduls."""


SCHUTZREGELN: tuple[IndicatorDefinition, ...] = (
    IndicatorDefinition("rule_voluntary_participation", Area.GEMEINWOHL,
                        "Freiwilligkeit als Grundprinzip, keine Zwangsverpflichtung",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("rule_no_disadvantage_disabled_or_care", Area.GEMEINWOHL,
                        "Keine Benachteiligung behinderter Menschen und Pflegebeduerftiger",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("rule_recognized_varying_capacity", Area.GEMEINWOHL,
                        "Anerkennung unterschiedlicher Leistungsfaehigkeit",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("rule_compensation_and_security", Area.GEMEINWOHL,
                        "Aufwandsentschaedigung und soziale Absicherung",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("rule_no_displacement_of_paid_work", Area.GEMEINWOHL,
                        "Keine Verdraengung reguljaerer Arbeitsplaetze",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("rule_data_protection_abuse_guard", Area.GEMEINWOHL,
                        "Datenschutz und Schutz vor politischem oder wirtschaftlichem Missbrauch",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("rule_independent_effect_control", Area.GEMEINWOHL,
                        "Unabhaengige Erfolgskontrolle",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
    IndicatorDefinition("rule_not_a_control_instrument", Area.GEMEINWOHL,
                        "Der Dienst darf nicht zum Kontrollinstrument werden",
                        "boolean", MeasurementScope.LOCAL_ENVIRONMENT),
)

RULE_KEYS: tuple[str, ...] = tuple(d.key for d in SCHUTZREGELN)

ALLOWED_REBOUND_VERDICTS: tuple[Optional[str], ...] = (
    None, VERDICT_ZIELKONFLIKT, VERDICT_NICHT_ENTSCHEIDBAR, VERDICT_VERTRAEGLICH)

VERDICT_GEMEINWOHLTAUGLICH = "GEMEINWOHLTAUGLICH_BELEGT"


@dataclass(frozen=True)
class ImpactPlanIndicator:
    """EIN Messmatrix-Eintrag: Ausgangswert, Zielwert, Quelle, Pruefer.

    Mindestanforderungen nach Lernblock Abschnitt 7 und
    pilot-i-Messmatrix: ohne Ausgangswert + Zielwert + Zeitraum +
    Verfahren + Pruefer bleibt der Eintrag ungueltig
    (MATRIZ != WIRKUNG; ZIELWERT != ERGEBNIS).
    """
    name: str
    unit: str
    baseline: float
    target: float
    period_start: str
    period_end: str
    method: str
    verifier: str
    source: str
    uncertainty: Optional[float] = None


@dataclass(frozen=True)
class GemeinwohlInitiative:
    """Reine Beschreibung einer Initiative. Keine Ausfuehrung."""
    initiative_id: str
    description: str
    rule_evidence: Mapping[str, Optional[EvidenceBundle]]
    messplan: Sequence[ImpactPlanIndicator]
    rebound_verdict: Optional[str] = None


def _initiative_ok(initiative: GemeinwohlInitiative) -> None:
    if not isinstance(initiative, GemeinwohlInitiative):
        raise GemeinwohlError("initiative must be a GemeinwohlInitiative")
    if not isinstance(initiative.initiative_id, str) \
            or not initiative.initiative_id.strip():
        raise GemeinwohlError("initiative_id missing")
    if not isinstance(initiative.description, str) \
            or not initiative.description.strip():
        raise GemeinwohlError("description missing")
    if not isinstance(initiative.rule_evidence, Mapping):
        raise GemeinwohlError("rule_evidence must be a mapping")
    for key, evidence in initiative.rule_evidence.items():
        if key not in RULE_KEYS:
            raise GemeinwohlError("unknown protection rule: %s" % key)
        if evidence is not None and not isinstance(evidence, EvidenceBundle):
            raise GemeinwohlError("rule %s must be None or an EvidenceBundle" % key)
    if not isinstance(initiative.messplan, (list, tuple)):
        raise GemeinwohlError("messplan must be a sequence of ImpactPlanIndicator")
    for entry in initiative.messplan:
        if not isinstance(entry, ImpactPlanIndicator):
            raise GemeinwohlError("messplan entries must be ImpactPlanIndicator")
    if initiative.rebound_verdict not in ALLOWED_REBOUND_VERDICTS:
        raise GemeinwohlError(
            "rebound_verdict must be one of %s" % (ALLOWED_REBOUND_VERDICTS,))


def _numeric_ok(value) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    value_f = float(value)
    return math.isfinite(value_f) and value_f >= 0


def validate_messplan_entry(entry: ImpactPlanIndicator) -> list[str]:
    """Mindestanforderungen-Check EINES Messplaneintrags. Fail-closed."""
    if not isinstance(entry, ImpactPlanIndicator):
        raise GemeinwohlError("entry must be an ImpactPlanIndicator")
    problems: list[str] = []
    if not isinstance(entry.name, str) or not entry.name.strip():
        problems.append("name missing")
    if not isinstance(entry.unit, str) or not entry.unit.strip():
        problems.append("unit missing")
    if not _numeric_ok(entry.baseline):
        problems.append("baseline missing or invalid (finite, non-negative)")
    if not _numeric_ok(entry.target):
        problems.append("target missing or invalid (finite, non-negative)")
    if not _valid_period(entry.period_start, entry.period_end):
        problems.append("period invalid (two ISO-8601 timestamps, start <= end)")
    for field_name, label in (("method", "method"), ("verifier", "verifier"),
                              ("source", "source")):
        value = getattr(entry, field_name)
        if not isinstance(value, str) or not value.strip():
            problems.append("%s missing" % label)
    if entry.uncertainty is not None and not _numeric_ok(entry.uncertainty):
        problems.append("uncertainty must be None or finite non-negative")
    return problems


def messplan_report(initiative: GemeinwohlInitiative) -> dict:
    """Messplan-Sammelbericht. Enthaelt NIE Zielerreichung in Prozent."""
    _initiative_ok(initiative)
    entries: dict[str, dict] = {}
    invalid_count = 0
    for position, entry in enumerate(initiative.messplan):
        problems = validate_messplan_entry(entry)
        if problems:
            invalid_count += 1
        entries[entry.name.strip() if isinstance(entry.name, str)
                and entry.name.strip() else "eintrag-%d" % position] = {
            "ok": not problems,
            "problems": problems,
        }
    return {
        "entry_count": len(initiative.messplan),
        "invalid_count": invalid_count,
        "entries": entries,
        "messplan_ok": len(initiative.messplan) > 0 and invalid_count == 0,
    }


def assess_gemeinwohl(initiative: GemeinwohlInitiative) -> dict:
    """Vollstaendige Gemeinwohlpruefung mit Verdict. Fail-closed.

    Verdicts:
    - ZIELKONFLIKT_BELEGT: uebernommene Reboundpruefung blockt.
    - NICHT_ENTSCHEIDBAR: Schutzregel ungeprueft/evidenzlos,
      Messplan fehlt oder ungueltig, oder Rebound unentscheidbar
      (UNKNOWN != PASS, nie still tauglich).
    - GEMEINWOHLTAUGLICH_BELEGT: alle Regeln dokumentiert belegt,
      Messplan gueltig, keine Zielkonflikt-Blockade.
    Selbstauskunft bleibt Selbstauskunft: BELEGT heisst hier
    'Dokumentation mit Quelle/Verfahren/Zeitraum vorhanden',
    nicht 'Regel im Alltag gelebt' (AUSGEFUELLT != GELEBT).
    """
    _initiative_ok(initiative)
    submissions: dict[str, object] = {}
    for key in RULE_KEYS:
        evidence = initiative.rule_evidence.get(key)
        if isinstance(evidence, EvidenceBundle):
            submissions[key] = MeasurementClaim(1.0, "boolean", evidence)
        else:
            submissions[key] = None
    report = registry_report(list(SCHUTZREGELN), submissions)

    messplan = messplan_report(initiative)

    problems: list[str] = []
    for key in RULE_KEYS:
        if report["indicators"][key]["status"] != "BELEGT":
            problems.append("Schutzregel %s nicht geprueft (UNKNOWN != PASS)" % key)
    if initiative.messplan:
        for name, entry in messplan["entries"].items():
            for p in entry["problems"]:
                problems.append("Messplaneintrag %s: %s" % (name, p))
    if not messplan["messplan_ok"]:
        problems.append("Messplan unzureichend (MATRIZ != WIRKUNG)")

    rebound_effect = None
    if initiative.rebound_verdict == VERDICT_ZIELKONFLIKT:
        rebound_effect = VERDICT_ZIELKONFLIKT
        problems.append("Reboundpruefung blockt: ZIELKONFLIKT_BELEGT")
    elif initiative.rebound_verdict == VERDICT_NICHT_ENTSCHEIDBAR:
        rebound_effect = VERDICT_NICHT_ENTSCHEIDBAR
        problems.append("Reboundpruefung unentscheidbar (bleibt offen)")

    if rebound_effect == VERDICT_ZIELKONFLIKT:
        verdict = VERDICT_ZIELKONFLIKT
    elif problems:
        verdict = VERDICT_NICHT_ENTSCHEIDBAR
    else:
        verdict = VERDICT_GEMEINWOHLTAUGLICH

    result = dict(report)
    result["schema"] = "v91.gemeinwohl_check.v1"
    result["initiative"] = {
        "initiative_id": initiative.initiative_id.strip(),
        "rebound_verdict": initiative.rebound_verdict,
    }
    result["messplan"] = messplan
    result["verdict"] = verdict
    result["problems"] = problems
    result["honest_limits"] = report["honest_limits"] + (
        "MATRIZ != WIRKUNG: Ein Messplan ist noch keine Wirkung.",
        "ZIELWERT != ERGEBNIS: Ziele sind keine Messergebnisse.",
        "AUSGEFUELLT != GELEBT: Regel-Dokumentation ist Selbstauskunft, kein Lebensnachweis.",
        "REVIEW != ENTSCHEIDUNG: gesellschaftliche Entscheidungen gehoeren dem Souveraenen.",
        "ASSESSMENT != AUTHORIZATION: Diese Pruefung berechtigt zu nichts.",
    )
    return result
