"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Struktur-Review: Wirtschafts-/Korruptionsanalyse-Wächter nach
Direktiv-Abschnitt 6 (docs/V91-GLOBAL-FEDERATION-DIRECTIVE.md).
Bewertet eine erkannte Struktur (Institution, Programm, Regelwerk)
gegen die 7 Prüfkriterien der Direktive - NUR auf Basis gelieferter,
belegter Einschätzungen. Keine Bewertung ohne Nachweis-Referenz
(CLAIM != EVIDENCE), keine positiven Behauptungen aus fehlenden
Angaben (UNKNOWN != PASS). Beobachtet und bewertet Daten; ergreift
nichts, ruft niemanden an, verändert keine Fremdsysteme.
REVIEW != ENTSCHEIDUNG; DETECTION != AUTHORIZATION.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

# Die 7 Bewertungskriterien exakt nach Direktiv-Abschnitt 6.
CRITERIA: tuple = (
    "gesellschaftlicher_nutzen",
    "menschenrechtsvertraeglichkeit",
    "kosten_und_ressourcenverbrauch",
    "transparenz",
    "nachhaltigkeit",
    "missbrauchsrisiken",
    "alternativen_und_verbesserbarkeit",
)

STATUS_BELEGT = "BELEGT"
STATUS_PROBLEM = "PROBLEM_BELEGT"
STATUS_UNGEPRUEFT = "NICHT_GEPRUEFT"
VALID_STATUSES: tuple = (STATUS_BELEGT, STATUS_PROBLEM, STATUS_UNGEPRUEFT)


class StructureReviewError(Exception):
    """Fail-closed Fehler des Struktur-Reviews."""


def evaluate_structure(review: Dict) -> Dict:
    """Bewertet EINE Struktur anhand belegter Kriterien-Einschätzungen.

    Eingabe (dict): structure_id (nicht-leerer str), assessor (nicht-leerer
    str), criteria: {kriterium: {status, evidence, source, assessed_at}}.
    BELEGT/PROBLEM_BELEGT verlangen nicht-leere evidence- UND source-
    Angaben sowie nicht-leeren assessed_at-Zeitstempel.
    NICHT_GEPRUEFT verlangt ausdrücklich keine Evidenz (ehrliche Lücke).
    """
    if not isinstance(review, dict):
        raise StructureReviewError("review must be a dict")
    structure_id = review.get("structure_id")
    assessor = review.get("assessor")
    if not isinstance(structure_id, str) or not structure_id.strip():
        raise StructureReviewError("structure_id must be a non-empty string")
    if not isinstance(assessor, str) or not assessor.strip():
        raise StructureReviewError("assessor must be a non-empty string")
    criteria = review.get("criteria")
    if not isinstance(criteria, dict):
        raise StructureReviewError("criteria must be a dict")
    unexpected = set(criteria) - set(CRITERIA)
    if unexpected:
        raise StructureReviewError(f"unknown criteria (allowed: {sorted(CRITERIA)}): {sorted(unexpected)}")

    findings: List = []
    unverified: List = []
    problems: List = []
    for name in CRITERIA:
        entry = criteria.get(name)
        if not isinstance(entry, dict):
            raise StructureReviewError(f"criterion {name}: entry must be a dict")
        status = entry.get("status")
        if status not in VALID_STATUSES:
            raise StructureReviewError(
                f"criterion {name}: status must be one of {sorted(VALID_STATUSES)}"
            )
        if status == STATUS_UNGEPRUEFT:
            unverified.append(name)
            continue
        evidence = entry.get("evidence")
        source = entry.get("source")
        assessed_at = entry.get("assessed_at")
        for field, value in (("evidence", evidence), ("source", source), ("assessed_at", assessed_at)):
            if not isinstance(value, str) or not value.strip():
                raise StructureReviewError(
                    f"criterion {name}: {field} required (non-empty string) for status {status}"
                )
        findings.append({
            "criterion": name,
            "status": status,
            "evidence": evidence,
            "source": source,
            "assessed_at": assessed_at,
        })
        if status == STATUS_PROBLEM:
            problems.append(name)

    if problems:
        verdict = "NEGATIVE_FINDING_PROBLEMS_BELEGT"
    elif unverified:
        verdict = "REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN"
    else:
        verdict = "BEWERTUNG_ABGESCHLOSSEN_NACHWEISLICH"

    return {
        "schema_version": 1,
        "structure_id": structure_id,
        "assessor": assessor,
        "criteria_total": len(CRITERIA),
        "criteria_belegt": len(findings) - len(problems),
        "criteria_problem_belegt": len(problems),
        "criteria_ungeprueft": len(unverified),
        "problems": sorted(problems),
        "ungeprueft": sorted(unverified),
        "verdict": verdict,
        "honest_limits": [
            "REVIEW != ENTSCHEIDUNG; DETECTION != AUTHORIZATION.",
            "BELEGT ist eine belegte Einschätzung, keine unabhängige Bestätigung.",
            "Veränderungen erfolgen friedlich, demokratisch, rechtsstaatlich (Direktive Abschnitt 6).",
        ],
    }


def main(argv: Optional[List] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Struktur-Review: Bewertung einer Struktur gegen die 7 Direktiv-Kriterien"
    )
    parser.add_argument("--report-json", type=str, required=True, help="Pfad zum Review-JSON")
    args = parser.parse_args(argv)

    try:
        with open(args.report_json, "r", encoding="utf-8") as handle:
            review = json.load(handle)
    except OSError as exc:
        print(json.dumps({"error": f"cannot read report: {exc}"}))
        return 2
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid json: {exc}"}))
        return 2
    try:
        result = evaluate_structure(review)
    except StructureReviewError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verdict"] == "BEWERTUNG_ABGESCHLOSSEN_NACHWEISLICH" else 1


if __name__ == "__main__":
    sys.exit(main())
