#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Support consent gate (Issue #268, third core slice): fail-closed
validator for support, therapy and assistance records about a person.

Rules (UNKNOWN != PASS):
- VOLUNTARY: support is voluntary; a legal mandate is only accepted
  with an explicit legal basis AND offered independent oversight.
- INFORMED CONSENT: risks, alternatives, costs and conflicts of
  interest are disclosed; questions are invited.
- SELF-DETERMINED GOALS: goals are agreed with the person, never
  merely imposed to make them more convenient for institutions.
- NO COERCION: coercive, humiliating, punitive and identity-erasing
  treatment flags must be explicitly False.
- REFUSAL IS NOT INCAPACITY: refusal or criticism is never treated as
  proof of incapacity.
- HONEST CLASSIFICATION: treatment must be classified; experimental
  or commercial-unproven support needs explicit acknowledgement.
- PRIVACY: minimum-necessary sharing with a named legal basis.

Honest limits (SCRIPTED != INSTALLED, REVIEW != ENTSCHEIDUNG):
- Validates record structure, not real-world care; OBSERVED != ERFOLG.
"""

from __future__ import annotations

from typing import Any

REQUIRED_STRINGS = ("support_id", "date", "provider")

TREATMENT_CLASSES = frozenset({
    "evidence_based", "experimental", "commercial_unproven",
})

FORBIDDEN_FLAGS = (
    "coercive_treatment", "humiliating_treatment",
    "punitive_purpose", "identity_erasing_treatment",
)

CONSENT_DISCLOSURES = ("risks", "alternatives", "costs", "conflicts_of_interest")


class SupportConsentGateError(ValueError):
    """Raised fail-closed with collected violations: UNKNOWN != PASS."""


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_support_record(record: Any) -> dict[str, Any]:
    """Validate an ethical support/therapy record, fail-closed."""
    violations: list[str] = []
    if not isinstance(record, dict):
        raise SupportConsentGateError(["record: dict required"])

    for key in REQUIRED_STRINGS:
        if not _nonempty_str(record.get(key)):
            violations.append(key + ": non-empty string required")

    # Voluntary unless a documented legal mandate with oversight.
    voluntary = record.get("voluntary")
    if voluntary is True:
        consent = record.get("informed_consent")
        if not isinstance(consent, dict):
            violations.append("informed_consent: dict required when voluntary")
        else:
            for key in CONSENT_DISCLOSURES:
                if not _nonempty_str(consent.get(key)):
                    violations.append(
                        "informed_consent." + key + ": non-empty string required")
            if consent.get("questions_invited") is not True:
                violations.append(
                    "informed_consent.questions_invited: must be explicitly True")
    elif voluntary is False:
        mandate = record.get("legal_mandate")
        if (not isinstance(mandate, dict)
                or not _nonempty_str(mandate.get("legal_basis"))
                or mandate.get("independent_oversight_offered") is not True):
            violations.append(
                "legal_mandate: legal_basis and "
                "independent_oversight_offered=True required when voluntary is False")
    else:
        violations.append("voluntary: True/False required")

    # Self-determined goals, no normalization as self-purpose.
    if record.get("goals_agreed_with_person") is not True:
        violations.append(
            "goals_agreed_with_person: must be explicitly True "
            "(SELBSTBESTIMMUNG: Ziele werden vereinbart, nicht verordnet)")

    # Refusal is never proof of incapacity.
    if record.get("refusal_treated_as_incapacity") is not False:
        violations.append(
            "refusal_treated_as_incapacity: must be explicitly False")

    # No coercion, humiliation, punishment, identity erasure.
    for flag in FORBIDDEN_FLAGS:
        if record.get(flag) is not False:
            violations.append(flag + ": must be explicitly False")

    # Honest treatment classification.
    treatment = record.get("treatment_classification")
    if treatment not in TREATMENT_CLASSES:
        violations.append(
            "treatment_classification: must be one of " + ", ".join(
                sorted(TREATMENT_CLASSES)))
    elif treatment != "evidence_based":
        ack = (record.get("informed_consent") or {}).get(
            "experimental_status_acknowledged") if isinstance(
            record.get("informed_consent"), dict) else None
        if ack is not True:
            violations.append(
                "informed_consent.experimental_status_acknowledged: "
                "must be True for non-evidence-based treatment")

    # Privacy: minimum necessary, with a named legal basis.
    if record.get("minimum_necessary_sharing") is not True:
        violations.append(
            "minimum_necessary_sharing: must be explicitly True")
    if not _nonempty_str(record.get("privacy_legal_basis")):
        violations.append("privacy_legal_basis: non-empty string required")

    if violations:
        raise SupportConsentGateError(violations)

    return dict(record)
