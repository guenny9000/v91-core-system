#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Person dignity gate (Issue #268, first core slice).

Fail-closed validator for consequential decisions about a person
(types: care, benefits, education, work, housing, access, freedom).
The gate REFUSES a decision record unless it proves:

1. PERSON != LABEL: the person was offered a hearing; behavioural
   traits, disabilities, diagnoses or communication style are never
   accepted as a stated reason by themselves.
2. NO AI DIAGNOSIS: a diagnosis field is only accepted with source
   "clinical_documented"; sources "behaviour_inference" or
   "ai_profile_inference" are refused fail-closed.
3. HEARING: hearing offered and either accepted (own statement
   recorded) or explicitly declined with a record entry.
4. SECOND REVIEW: an independent reviewer distinct from the original
   decision maker, with a qualification.
5. APPEAL: an appeal route exists and retaliation for complaining is
   structurally excluded (flag must be explicitly False).
6. ACCOMMODATIONS: accommodations were considered (flag explicitly
   True).

Honest limits (SCRIPTED != INSTALLED, REVIEW != ENTSCHEIDUNG):
- This module validates records; it does not run inside any authority,
  employer or court, and passing the gate proves documentation quality,
  not real-world justice (OBSERVED != ERFOLG).
- A passing record can still be wrong; the gate enforces verifiable
  structure, not truth (SIGNATUR != WAHRHEIT).
- UNKNOWN != PASS: any missing or unparseable field fails closed.
"""

from __future__ import annotations

from typing import Any

CONSEQUENTIAL_TYPES = frozenset({
    "care", "benefits", "education", "work", "housing", "access", "freedom",
})

REQUIRED_STRINGS = (
    "decision_id", "decision_type", "date", "decision_maker",
    "criteria", "consequences", "appeal_route",
)

ALLOWED_DIAGNOSIS_SOURCES = frozenset({"clinical_documented"})
REFUSED_DIAGNOSIS_SOURCES = frozenset({
    "behaviour_inference", "ai_profile_inference",
})

HEARING_MODES = frozenset({"accepted", "declined_with_record"})


class PersonDignityGateError(ValueError):
    """Raised fail-closed with collected violations: UNKNOWN != PASS."""


def _require_str(record: dict[str, Any], key: str, violations: list[str]) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        violations.append(f"{key}: non-empty string required")
        return ""
    return value.strip()


def validate_consequential_decision(record: Any) -> dict[str, Any]:
    """Validate a consequential decision record, fail-closed.

    Returns a normalized copy on success, raises
    PersonDignityGateError listing every violation otherwise.
    """
    violations: list[str] = []
    if not isinstance(record, dict):
        raise PersonDignityGateError(["record: dict required"])

    out: dict[str, Any] = {}
    for key in REQUIRED_STRINGS:
        out[key] = _require_str(record, key, violations)

    decision_type = out.get("decision_type", "")
    if decision_type not in CONSEQUENTIAL_TYPES:
        violations.append(
            "decision_type: must be one of " + ", ".join(sorted(CONSEQUENTIAL_TYPES)))

    # Reasons must be a non-empty list of non-empty strings.
    reasons = record.get("reasons")
    if not isinstance(reasons, list) or not reasons or not all(
            isinstance(r, str) and r.strip() for r in reasons):
        violations.append("reasons: non-empty list of non-empty strings required")
    else:
        out["reasons"] = [r.strip() for r in reasons]

    # Rule 1/6: accommodations must be explicitly considered.
    if record.get("accommodations_considered") is not True:
        violations.append("accommodations_considered: must be explicitly True")

    # Rule 3: hearing offered; declined needs an explicit record entry.
    hearing = record.get("hearing")
    if not isinstance(hearing, dict) or hearing.get("offered") is not True:
        violations.append("hearing: offered=True required")
    else:
        mode = hearing.get("mode")
        if mode not in HEARING_MODES:
            violations.append(
                "hearing.mode: must be accepted or declined_with_record")
        elif mode == "accepted":
            statement = hearing.get("statement")
            if not isinstance(statement, str) or not statement.strip():
                violations.append(
                    "hearing.statement: required when hearing was accepted")

    # Rule 2: diagnosis only with a documented clinical source,
    # never inferred from behaviour or AI profiling.
    diagnoses = record.get("diagnoses")
    if diagnoses is not None:
        if not isinstance(diagnoses, list):
            violations.append("diagnoses: list required when present")
        else:
            for entry in diagnoses:
                if not isinstance(entry, dict) or not isinstance(
                        entry.get("label"), str) or not entry.get("label").strip():
                    violations.append("diagnoses[].label: non-empty string required")
                    continue
                source = entry.get("source")
                if source in REFUSED_DIAGNOSIS_SOURCES:
                    violations.append(
                        "diagnoses[].source: " + source + " refused "
                        "(KI darf keine eigenstaendige Diagnose ableiten)")
                elif source not in ALLOWED_DIAGNOSIS_SOURCES:
                    violations.append(
                        "diagnoses[].source: must be clinical_documented")

    # Rule 1: a trait may be context, never a standalone stated reason.
    if record.get("traits_used_as_stated_reason") is not False:
        violations.append(
            "traits_used_as_stated_reason: must be explicitly False "
            "(MENSCH != SCHUBLADE: Eigenschaft ist Kontext, kein Grund)")

    # Rule 4: independent second reviewer, distinct from the maker.
    review = record.get("second_review")
    if not isinstance(review, dict):
        violations.append("second_review: dict required")
    else:
        reviewer = review.get("reviewer")
        qualification = review.get("qualification")
        if not isinstance(reviewer, str) or not reviewer.strip():
            violations.append("second_review.reviewer: non-empty string required")
        elif reviewer.strip() == out.get("decision_maker", ""):
            violations.append(
                "second_review.reviewer: must differ from decision_maker")
        if not isinstance(qualification, str) or not qualification.strip():
            violations.append("second_review.qualification: non-empty string required")

    # Rule 5: appeal route without retaliation.
    if record.get("retaliation_for_appeal") is not False:
        violations.append(
            "retaliation_for_appeal: must be explicitly False")

    if violations:
        raise PersonDignityGateError(violations)

    out["accommodations_considered"] = True
    out["traits_used_as_stated_reason"] = False
    out["retaliation_for_appeal"] = False
    if isinstance(record.get("hearing"), dict):
        out["hearing"] = record["hearing"]
    if isinstance(record.get("second_review"), dict):
        out["second_review"] = record["second_review"]
    if isinstance(record.get("diagnoses"), list):
        out["diagnoses"] = record["diagnoses"]
    return out
