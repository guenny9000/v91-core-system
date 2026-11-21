#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Public Reporting (MAX-BEST, VIBE-XXXI): oeffentliche, datenschutzsichere
Berichtsstruktur fuer Digitale-Hygiene-Ergebnisse (Issue #276, Faehigkeit
10: kontinuierliche Verbesserung oeffentlich ehrlich berichten).

Fuenf ehrliche Reifegrad-Labels, getrennt und nie vermischt:
  DOCUMENTED   es existiert eine Beschreibung/Vorgabe
  IMPLEMENTED  es existiert Quellcode/Bestand
  TESTED       es existiert eine reproduzierbare Pruefung
  VERIFIED     es existiert unabhaengig gepruefte Evidenz
  DEPLOYED     es existiert belegte Evidenz aus dem realen Betrieb

Regeln (fail-closed):
- Ein Label ist ein Verweis auf Evidenz, keine Eigenschaft des Wunsches
  (LABEL ohne Beleg wird verweigert; VERIFIED/DEPLOYED ohne EvidenceBundle
  ist ein Fehler). DEPLOYED erfordert zusaetzlich deployment_evidence am
  Bericht (REPORT != DEPLOYMENT).
- KEINE Erfolgsquoten, KEINE Prozente, KEINE Zielerreichung: nur gezaehlte
  Mengen und Rohwerte mit Einheit (COUNT != IMPACT).
- Datenschutz: Texte mit Schluessel- oder Personen-Identifikatoren werden
  verweigert (PRIVACY_LOCK > TRANSPARENZ; keine Secrets, keine
  Personendaten, keine ausnutzbaren Schwachstellen-Details).
- UNKNOWN ist nie PASS; ein Bericht ohne Grenzen ist Werbung und wird
  verweigert (mindestens eine limitation ist Pflicht).

REUSE (NO_DUPLICATE_SYSTEMS):
  impact_area_registry.py  EvidenceBundle + Beleg-Validierung (Import)
  node_inventory.py         Bestandsaufnahme-Kategorien (Datenquelle)
  finding_registry.py       UNKNOWN/VERIFIED/DISPUTED-Taxonomie (#283)
  safe_response.py          Antwort-Verben (#279)
Dieses Modul formatiert NUR: ES MISST NICHT, ES PRUEFT NICHT, ES
ENTSCHEIDET NICHT. REPORT != MESSUNG; REPORT != FREIGABE.

Honest limits:
DOCUMENTED != IMPLEMENTED; IMPLEMENTED != TESTED; TESTED != VERIFIED;
VERIFIED != DEPLOYED; AGGREGAT != EINZELFALL; PUBLISHED != TRUE;
DATA_ENCLOSED != DATA_VERIFIED.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from controller.impact_area_registry import (
    EvidenceBundle,
    _validate_evidence,
)


class PublicReportingError(RuntimeError):
    """Fail-closed: unzulaessiger oeffentlicher Bericht."""


LABEL_DOCUMENTED = "DOCUMENTED"
LABEL_IMPLEMENTED = "IMPLEMENTED"
LABEL_TESTED = "TESTED"
LABEL_VERIFIED = "VERIFIED"
LABEL_DEPLOYED = "DEPLOYED"

LABEL_ORDER: tuple[str, ...] = (
    LABEL_DOCUMENTED, LABEL_IMPLEMENTED, LABEL_TESTED,
    LABEL_VERIFIED, LABEL_DEPLOYED,
)
ALLOWED_LABELS = frozenset(LABEL_ORDER)

# Schluessel- und Identitaetsmarker: oeffentliche Berichte duerfen sie
# NIE enthalten (Issue #276 Faehigkeit 10: keine Secrets, keine
# Personendaten, keine ausnutzbaren Schwachstellen-Details).
FORBIDDEN_TEXT_MARKERS: tuple[str, ...] = (
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "private_key", "credential", "session_id", "bearer ",
)
FORBIDDEN_PATTERNS_EMAIL = "@"

HONEST_LIMITS: tuple[str, ...] = (
    "DOCUMENTED != IMPLEMENTED; IMPLEMENTED != TESTED; TESTED != VERIFIED; VERIFIED != DEPLOYED.",
    "Ein Label verweist auf vorliegende Evidenz, nicht auf Wahrheit (PUBLISHED != TRUE).",
    "Gezaehlte Mengen sind keine Wirkung (COUNT != IMPACT); keine Prozente, keine Zielerreichung.",
    "Berichte sind Aggregate: der Einzelfall kann abweichen (AGGREGAT != EINZELFALL).",
    "REPORT != FREIGABE: dieser Bericht berechtigt zu keinem Eingriff.",
)


@dataclass(frozen=True)
class PublicMetric:
    """Ein oeffentlich berichtbarer Rohwert mit Ehrlichkeits-Label."""
    name: str
    value: float
    unit: str
    label: str
    basis: str
    evidence: Optional[EvidenceBundle] = None


def _validate_text(text: object, field: str, problems: list[str]) -> None:
    if not isinstance(text, str) or not text.strip():
        problems.append(f"{field} missing")
        return
    lowered = text.lower()
    for marker in FORBIDDEN_TEXT_MARKERS:
        if marker in lowered:
            problems.append(f"{field} contains forbidden marker: {marker}")
    if FORBIDDEN_PATTERNS_EMAIL in text:
        problems.append(f"{field} contains e-mail-like personal identifier")


def validate_metric(metric: PublicMetric,
                    deployment_evidence: Optional[EvidenceBundle]) -> list[str]:
    """Fail-closed Pruefung EINER oeffentlichen Metrik. Liefert Probleme."""
    if not isinstance(metric, PublicMetric):
        raise PublicReportingError("metric must be a PublicMetric")
    problems: list[str] = []
    _validate_text(metric.name, "name", problems)
    _validate_text(metric.unit, "unit", problems)
    _validate_text(metric.basis, "basis", problems)
    if isinstance(metric.value, bool) or not isinstance(metric.value, (int, float)):
        problems.append("value must be numeric")
    else:
        value_f = float(metric.value)
        if not math.isfinite(value_f) or value_f < 0:
            problems.append("value must be finite and non-negative")
    if metric.label not in ALLOWED_LABELS:
        problems.append(f"unknown label: {metric.label!r}")
        return problems
    if metric.label in (LABEL_VERIFIED, LABEL_DEPLOYED) and \
            not isinstance(metric.evidence, EvidenceBundle):
        problems.append(f"label {metric.label} requires an EvidenceBundle")
    if metric.label == LABEL_DEPLOYED and \
            not isinstance(deployment_evidence, EvidenceBundle):
        problems.append("label DEPLOYED requires report-level deployment_evidence")
    if isinstance(metric.evidence, EvidenceBundle):
        problems.extend(_validate_evidence(metric.evidence))
        _validate_text(metric.evidence.source, "evidence source", problems)
        _validate_text(metric.evidence.method, "evidence method", problems)
        _validate_text(metric.evidence.reference, "evidence reference", problems)
    if isinstance(deployment_evidence, EvidenceBundle):
        problems.extend(_validate_evidence(deployment_evidence))
        _validate_text(deployment_evidence.source, "deployment source", problems)
        _validate_text(deployment_evidence.method, "deployment method", problems)
        _validate_text(deployment_evidence.reference, "deployment reference", problems)
    return problems


def build_public_report(metrics: Sequence[PublicMetric],
                        limitations: Sequence[str],
                        deployment_evidence: Optional[EvidenceBundle] = None) -> dict:
    """Oeffentlicher Bericht: nur Gezaehltes, nur Belegtes, mit Grenzen.

    Ein Bericht ohne limitations wird verweigert (Werbungsverbot); eine
    leere Metrikliste wird verweigert (leere Berichte behaupten Reife);
    DEPLOYED nur mit belegter deployment_evidence, sonst Fehler.
    """
    if not isinstance(metrics, (list, tuple)) or not metrics:
        raise PublicReportingError("metrics must be a non-empty sequence")
    if not isinstance(limitations, (list, tuple)) or not limitations:
        raise PublicReportingError("limitations must be a non-empty sequence "
                                   "(a report without limitations is advertising)")
    for limitation in limitations:
        if not isinstance(limitation, str) or not limitation.strip():
            raise PublicReportingError("limitations must be non-empty strings")

    validated: list[dict] = []
    label_counts = {label: 0 for label in LABEL_ORDER}
    problems_all: list[str] = []
    for metric in metrics:
        problems = validate_metric(metric, deployment_evidence)
        if problems:
            problems_all.extend(f"{metric.name}: {p}" if isinstance(
                metric, PublicMetric) and metric.name else p for p in problems)
            continue
        label_counts[metric.label] += 1
        entry = {
            "name": metric.name,
            "value": float(metric.value),
            "unit": metric.unit,
            "label": metric.label,
            "basis": metric.basis,
        }
        if metric.evidence is not None:
            entry["evidence_source"] = metric.evidence.source
            entry["evidence_method"] = metric.evidence.method
            entry["evidence_period"] = f"{metric.evidence.period_start} .. {metric.evidence.period_end}"
        validated.append(entry)
    if problems_all:
        raise PublicReportingError("; ".join(sorted(set(problems_all))))

    report: dict = {
        "schema": "v91.public_reporting.v1",
        "metrics": validated,
        "label_counts": label_counts,
        "limitations": [str(item) for item in limitations],
        "honest_limits": HONEST_LIMITS,
    }
    deployment = {"claimed": False, "evidence": None}
    if deployment_evidence is not None:
        problems = _validate_evidence(deployment_evidence)
        if problems:
            raise PublicReportingError(
                "deployment evidence invalid: " + "; ".join(problems))
        deployment = {
            "claimed": True,
            "evidence": {
                "source": deployment_evidence.source,
                "method": deployment_evidence.method,
                "period": f"{deployment_evidence.period_start} .. {deployment_evidence.period_end}",
                "reference": deployment_evidence.reference,
            },
        }
    report["deployment"] = deployment
    return report
