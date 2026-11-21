#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Waste reduction audit (Issue #268, section 5: reduce waste without
harm to people).

Fail-closed validator for proposals that cut spending, structures,
forms, assessments, software, subscriptions or procurement. It
answers ONE question first: does the cut harm people? Only a cut
that provably does not harm people may pass, and even then only
with conditions.

Fail-closed rules (UNKNOWN != PASS, CLAIM != EVIDENCE):

1. PEOPLE != COST CENTRE: a service, human contact, local job or
   support route is NEVER removed merely because an automated
   process is cheaper. Any such removal requires measured outcome
   evidence AND an equivalent-access replacement guarantee.
2. FULL LIFECYCLE: a purchase-price-only comparison is not a cost
   comparison. Maintenance, energy, travel, environmental effects,
   accessibility, failure rates and hidden burdens shifted onto
   families or disabled people must be addressed (quantified or
   explicitly justified as none).
3. PREFERENCE: repair, local capacity, open standards, durable
   tools and cooperative purchasing win when their lifecycle cost
   is lower with equivalent access. Choosing new procurement against
   such an alternative requires a documented justification.
4. ZIELWERT != ERGEBNIS: a projected saving is not a measured
   outcome. Removing an existing structure requires duplicate or
   redundancy evidence, not an assumption.
5. Honesty: the audit result itself states its limits. REVIEW !=
   ENTSCHEIDUNG, SCRIPTED != INSTALLED, MATRIZ != WIRKUNG.
"""

from __future__ import annotations

ALLOWED_CUT_TYPES = (
    "duplicate_administration",
    "unnecessary_form",
    "repeated_assessment",
    "unused_software",
    "unused_subscription",
    "failing_procurement",
    "service_reduction",
    "human_contact_reduction",
    "local_job_reduction",
    "support_route_reduction",
)

LIFECYCLE_COMPONENTS = (
    "procurement_eur",
    "maintenance_eur",
    "energy_eur",
    "travel_eur",
    "environmental_effects",
    "accessibility_effects",
    "failure_rate",
    "hidden_burdens_shifted",
)

PREFERRED_ALTERNATIVES = (
    "repair",
    "local_capacity",
    "open_standard",
    "durable_tool",
    "cooperative_purchasing",
)


class WasteReductionAuditError(Exception):
    """Raised when a spend-cut record is malformed or not a mapping."""


def _require_bool(record: dict, key: str, violations: list) -> None:
    value = record.get(key)
    if not isinstance(value, bool):
        violations.append("missing_boolean:" + key)


def _check_people_guard(record: dict, violations: list) -> None:
    removal_keys = (
        "removes_service",
        "removes_human_contact",
        "removes_local_jobs",
        "removes_support_route",
    )
    if not isinstance(record.get("automated_replacement_cheaper_only"), bool):
        violations.append("missing_boolean:automated_replacement_cheaper_only")

    removes_people_structure = any(
        isinstance(record.get(k), bool) and record.get(k) for k in removal_keys
    )
    if not removes_people_structure:
        return

    if record.get("automated_replacement_cheaper_only") is True:
        violations.append(
            "people_not_cost_centre:automation_price_is_not_sufficient_reason"
        )

    evidence = record.get("outcome_evidence")
    if not isinstance(evidence, dict) or not evidence:
        violations.append("people_guard:measured_outcome_evidence_missing")
    else:
        if not isinstance(evidence.get("measured_outcome"), str) or not evidence.get(
            "measured_outcome"
        ):
            violations.append("people_guard:measured_outcome_missing")
        if not isinstance(evidence.get("measured_on"), str) or not evidence.get(
            "measured_on"
        ):
            violations.append("people_guard:measurement_date_missing")
        if (
            not isinstance(evidence.get("method"), str)
            or not evidence.get("method")
        ):
            violations.append("people_guard:measurement_method_missing")

    replacement = record.get("replacement_guarantee")
    if not isinstance(replacement, dict) or not replacement:
        violations.append("people_guard:equivalent_access_replacement_missing")
    else:
        if replacement.get("equivalent_access") is not True:
            violations.append(
                "people_guard:replacement_access_not_proven_equivalent"
            )
        if (
            not isinstance(replacement.get("transition_support"), str)
            or not replacement.get("transition_support")
        ):
            violations.append("people_guard:transition_support_missing")


def _check_lifecycle(record: dict, violations: list) -> None:
    comparison = record.get("lifecycle_cost_comparison")
    if not isinstance(comparison, dict):
        violations.append("lifecycle:full_lifecycle_comparison_missing")
        return
    automation_only = comparison.get("purchase_price_only") is True
    if automation_only:
        violations.append("lifecycle:purchase_price_is_not_a_cost_comparison")
    for component in LIFECYCLE_COMPONENTS:
        if component not in comparison:
            violations.append("lifecycle:component_missing:" + component)
    burdens = comparison.get("hidden_burdens_shifted")
    if isinstance(burdens, dict):
        quantified = (
            isinstance(burdens.get("hours_per_week"), (int, float))
            and isinstance(burdens.get("cost_estimate_eur"), (int, float))
        )
        justified = burdens.get("justified_none") is True
        if not quantified and not justified:
            violations.append(
                "lifecycle:hidden_burdens_not_quantified_and_not_justified"
            )
    else:
        violations.append("lifecycle:hidden_burdens_shifted_not_addressed")


def _check_alternatives(record: dict, violations: list) -> None:
    alternatives = record.get("alternatives_considered")
    if not isinstance(alternatives, list) or len(alternatives) == 0:
        violations.append("alternatives:none_considered")
        return
    for alt in alternatives:
        if not isinstance(alt, dict):
            violations.append("alternatives:malformed_entry")
            continue
        for key in ("option", "lifecycle_cost_total_eur", "access_equivalent"):
            if key not in alt:
                violations.append("alternatives:field_missing:" + key)
    better = [
        alt
        for alt in alternatives
        if isinstance(alt, dict)
        and alt.get("option") in PREFERRED_ALTERNATIVES
        and isinstance(alt.get("lifecycle_cost_total_eur"), (int, float))
        and alt.get("access_equivalent") is True
        and isinstance(record.get("chosen_lifecycle_cost_total_eur"), (int, float))
        and alt.get("lifecycle_cost_total_eur")
        < record.get("chosen_lifecycle_cost_total_eur")
    ]
    if better:
        justification = record.get("procurement_deviation_justification")
        if (
            not isinstance(justification, str)
            or not justification
            or justification == "cheaper"
        ):
            violations.append(
                "preference:preferred_alternative_lower_cost_without_justification"
            )


def _check_duplicate_evidence(record: dict, violations: list) -> None:
    cut_type = record.get("cut_type")
    if not isinstance(cut_type, str) or cut_type not in ALLOWED_CUT_TYPES:
        violations.append("record:unknown_cut_type")
    if cut_type in (
        "duplicate_administration",
        "unnecessary_form",
        "repeated_assessment",
        "unused_software",
        "unused_subscription",
    ):
        evidence = record.get("duplicate_or_unused_evidence")
        if not isinstance(evidence, dict) or not evidence:
            violations.append(
                "evidence:duplicate_or_unused_proof_missing_for_existing_structure"
            )
        else:
            if (
                not isinstance(evidence.get("finding"), str)
                or not evidence.get("finding")
            ):
                violations.append("evidence:finding_missing")
            if (
                not isinstance(evidence.get("checked_by"), str)
                or not evidence.get("checked_by")
            ):
                violations.append("evidence:checked_by_missing")


def validate_spend_cut(record) -> dict:
    """Validate a spend-cut proposal. Fail closed: UNKNOWN != PASS."""
    violations: list[str] = []

    if not isinstance(record, dict):
        raise WasteReductionAuditError("record must be a dict")

    for key in ("audit_id", "date", "reviewer"):
        value = record.get(key)
        if not isinstance(value, str) or not value:
            violations.append("record:field_missing:" + key)

    conflict = record.get("conflicts_of_interest")
    if not isinstance(conflict, dict) or not (
        conflict.get("declared") is True or conflict.get("confirmed_none") is True
    ):
        violations.append("record:conflicts_of_interest_not_addressed")

    for key in (
        "removes_service",
        "removes_human_contact",
        "removes_local_jobs",
        "removes_support_route",
        "people_as_cost_centre",
    ):
        _require_bool(record, key, violations)

    if record.get("people_as_cost_centre") is not False:
        if "people_as_cost_centre" not in str(violations):
            violations.append("people_not_cost_centre:metric_treats_people_as_cost")

    cut_type = record.get("cut_type")
    if cut_type in ("service_reduction", "human_contact_reduction",
                    "local_job_reduction", "support_route_reduction"):
        _require_bool(record, "automated_replacement_cheaper_only", violations)

    uncertainty = record.get("uncertainty_note")
    if not isinstance(uncertainty, str) or not uncertainty.strip():
        violations.append("record:uncertainty_note_missing")

    _check_people_guard(record, violations)
    if record.get("lifecycle_cost_required") is True:
        _check_lifecycle(record, violations)
        _check_alternatives(record, violations)
    _check_duplicate_evidence(record, violations)

    decision = "REJECTED" if violations else "APPROVED_WITH_CONDITIONS"
    result = {
        "audit_id": record.get("audit_id") if isinstance(record.get("audit_id"), str) else None,
        "decision": decision,
        "violations": violations,
        "honesty_limits": (
            "REVIEW != DECISION, SCRIPTED != INSTALLED, MATRIZ != WIRKUNG, "
            "ZIELWERT != ERGEBNIS"
        ),
    }
    return result
