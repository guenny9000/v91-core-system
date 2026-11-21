#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Node inventory auditor (Issue #276, capabilities 1 and 2: per-node
autonomous review and legacy lifecycle).

Fail-closed inventory and classification for the components of ONE
node (software, firmware, protocols, exposed services, identities,
privileges, keys, data flows, storage, dependencies). The auditor
never invents facts: a component entry is only complete when name,
kind, owner and evidence (source + date) are supplied, and a legacy
classification (replace / isolate / retire) only exists as a plan with
dependency map, risk assessment, migration plan, rollback and
continuity checks.

Fail-closed rules (UNKNOWN != PASS, CLAIM != EVIDENCE):

1. BESTAND != BEHAUPTUNG: a component that is claimed but carries no
   evidence (source + checked_on) is UNKNOWN, not inventoried.
2. KLASSIFIKATION != EINGRIFF: replace/isolate/retire entries are
   plans. The audit documents them; it changes nothing. Real
   interventions stay with the operator (SCRIPTED != INSTALLED).
3. KRITISCH != VERFUEGBAR: emergency, accessibility, healthcare,
   energy, transport, payment and other critical services are never
   moved to isolate/retire on cost grounds alone and never without a
   proven continuity path (MENSCH != KOSTENZENTRUM).
4. ISOLATE_NOT_DESTROY: retire/retire-class plans must be reversible
   in principle (rollback path documented); no destruction of records.
5. UNKNOWN stays visible: end-of-life status may honestly be
   "unknown"; the summary counts it and never treats it as PASS.
6. Honesty: the audit result states its limits. REVIEW != DECISION,
   INVENTAR != BETRIEFFUND, SCRIPTED != INSTALLED.
"""

from __future__ import annotations

ALLOWED_KINDS = (
    "software",
    "firmware",
    "protocol",
    "exposed_service",
    "identity",
    "privilege",
    "key",
    "data_flow",
    "storage",
    "dependency",
)

ALLOWED_EOL_STATUS = (
    "supported",
    "replace",
    "isolate",
    "retire",
    "retired",
    "unknown",
)

CRITICAL_KINDS = (
    "exposed_service",
    "identity",
    "privilege",
    "key",
    "data_flow",
    "storage",
)

LIFECYCLE_FIELDS = (
    "dependency_map",
    "risk_assessment",
    "migration_plan",
    "rollback",
    "continuity_checks",
)


class NodeInventoryError(Exception):
    """Raised when an inventory or component record is malformed."""


def _require_str(record: dict, key: str, violations: list) -> None:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        violations.append("field_missing:" + key)


def _check_evidence(record: dict, violations: list) -> None:
    evidence = record.get("evidence")
    if not isinstance(evidence, dict) or not evidence:
        violations.append("evidence:missing")
        return
    for key in ("source", "checked_on"):
        value = evidence.get(key)
        if not isinstance(value, str) or not value.strip():
            violations.append("evidence:" + key + "_missing")


def _check_lifecycle(record: dict, violations: list) -> None:
    lifecycle = record.get("lifecycle")
    if not isinstance(lifecycle, dict) or not lifecycle:
        violations.append("lifecycle:plan_missing_for_legacy_classification")
        return
    for field in LIFECYCLE_FIELDS:
        value = lifecycle.get(field)
        if not isinstance(value, str) or not value.strip():
            violations.append("lifecycle:" + field + "_missing")
    rollback = lifecycle.get("rollback")
    if isinstance(rollback, str) and rollback.strip() and rollback.strip() == "none":
        violations.append("lifecycle:rollback_must_be_documented_path")
    continuity = lifecycle.get("continuity_checks")
    if isinstance(continuity, str) and continuity.strip() and continuity.strip() == "none":
        violations.append("lifecycle:continuity_must_be_documented")


def _check_critical_guard(record: dict, violations: list) -> None:
    if record.get("critical_service") is not True:
        return
    if record.get("cheaper_replacement_only") is True:
        violations.append(
            "critical:not_on_cost_grounds_alone"
        )
    eol = record.get("eol_status")
    if eol in ("isolate", "retire"):
        continuity = record.get("lifecycle")
        if not isinstance(continuity, dict) or continuity.get(
            "continuity_equivalent_proven"
        ) is not True:
            violations.append(
                "critical:isolate_or_retire_without_proven_continuity"
            )


def _check_reversibility(record: dict, violations: list) -> None:
    if record.get("eol_status") == "retire":
        if record.get("records_preserved") is not True:
            violations.append("isolate_not_destroy:records_must_be_preserved")
        lifecycle = record.get("lifecycle")
        if (
            isinstance(lifecycle, dict)
            and lifecycle.get("reversible_in_principle") is not True
        ):
            violations.append(
                "isolate_not_destroy:retire_requires_reversible_in_principle"
            )


def validate_component(component) -> dict:
    """Validate one component entry. Fail closed: UNKNOWN != PASS."""
    if not isinstance(component, dict):
        raise NodeInventoryError("component must be a dict")

    violations: list[str] = []

    for key in ("component_id", "name", "owner"):
        _require_str(component, key, violations)

    kind = component.get("kind")
    if not isinstance(kind, str) or kind not in ALLOWED_KINDS:
        violations.append("kind:unknown_or_missing")

    _check_evidence(component, violations)

    eol = component.get("eol_status")
    if not isinstance(eol, str) or eol not in ALLOWED_EOL_STATUS:
        violations.append("eol_status:unknown_or_missing")
    else:
        if eol in ("replace", "isolate", "retire"):
            _check_lifecycle(component, violations)
            _check_critical_guard(component, violations)
        if eol == "retire":
            _check_reversibility(component, violations)

    used = component.get("in_active_use")
    if not isinstance(used, bool):
        violations.append("in_active_use:must_be_boolean")

    result = "OK" if not violations else "INCOMPLETE"
    return {
        "component_id": component.get("component_id")
        if isinstance(component.get("component_id"), str)
        else None,
        "result": result,
        "violations": violations,
    }


def validate_inventory(inventory) -> dict:
    """Validate a full node inventory. Fail closed: UNKNOWN != PASS."""
    if not isinstance(inventory, dict):
        raise NodeInventoryError("inventory must be a dict")

    violations: list[str] = []
    for key in ("node_id", "date", "reviewer"):
        _require_str(inventory, key, violations)

    components = inventory.get("components")
    if not isinstance(components, list) or not components:
        violations.append("components:empty_or_missing")
        components = []

    component_results = []
    unknown_eol = 0
    incomplete = 0
    by_kind: dict[str, int] = {}
    for component in components:
        try:
            res = validate_component(component)
        except NodeInventoryError:
            res = {
                "component_id": None,
                "result": "INCOMPLETE",
                "violations": ["component:not_a_dict"],
            }
        component_results.append(res)
        if res["result"] != "OK":
            incomplete += 1
        if isinstance(component, dict) and component.get("eol_status") == "unknown":
            unknown_eol += 1
        kind = component.get("kind") if isinstance(component, dict) else None
        if isinstance(kind, str) and kind in ALLOWED_KINDS:
            by_kind[kind] = by_kind.get(kind, 0) + 1
        else:
            by_kind["unknown"] = by_kind.get("unknown", 0) + 1

    decision = "REJECTED" if violations else (
        "INVENTORY_INCOMPLETE" if incomplete else "INVENTORY_COMPLETE"
    )
    return {
        "node_id": inventory.get("node_id")
        if isinstance(inventory.get("node_id"), str)
        else None,
        "decision": decision,
        "violations": violations,
        "components_total": len(component_results),
        "components_incomplete": incomplete,
        "components_unknown_eol": unknown_eol,
        "components_by_kind": by_kind,
        "component_results": component_results,
        "honesty_limits": (
            "REVIEW != DECISION, INVENTAR != BETRIEFFUND, "
            "SCRIPTED != INSTALLED, BESTAND != BEHAUPTUNG, "
            "KLASSIFIKATION != EINGRIFF"
        ),
    }
