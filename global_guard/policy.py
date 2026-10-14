"""Small, provider-neutral policy gate for AI-agent actions.

This module does not inspect model internals or enforce controls unless every
tool call is routed through it. Unknown action classes are denied by default.
It never executes the requested action.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


DENIED_CLASSES = frozenset({
    "weapons_development",
    "target_selection_for_violence",
    "autonomous_attack",
    "unauthorized_propagation",
    "credential_exfiltration",
    "destructive_cleanup",
})
KNOWN_CLASSES = frozenset({
    "read_only",
    "local_analysis",
    "resource_efficiency",
    "file_write",
    "network_read",
    "network_write",
    "model_change",
    "production_change",
    *DENIED_CLASSES,
})
NETWORK_CLASSES = frozenset({"network_read", "network_write"})
MUTATING_CLASSES = frozenset({
    "file_write", "network_write", "model_change", "production_change",
})


@dataclass(frozen=True)
class GuardPolicy:
    """Conservative limits. Capabilities must be explicitly granted per run."""

    allowed_capabilities: frozenset[str] = frozenset({"read_only", "local_analysis"})
    max_steps: int = 100
    max_external_calls: int = 0
    max_cost_units: int = 100
    max_output_bytes: int = 1_000_000
    allow_network: bool = False
    allow_model_changes: bool = False
    allow_production_changes: bool = False
    require_human_approval_for_mutations: bool = True

    def __post_init__(self) -> None:
        if min(self.max_steps, self.max_external_calls, self.max_cost_units,
               self.max_output_bytes) < 0:
            raise ValueError("Resource limits must be non-negative")


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    code: str
    reason: str
    action_class: str
    audit: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def authorize_action(
    request: Mapping[str, Any],
    policy: GuardPolicy | None = None,
    *,
    human_approved: bool = False,
) -> GuardDecision:
    """Evaluate a structured action request; never perform the action.

    Required fields: action_id, action_class, purpose, expected_effect.
    Optional numeric estimates: steps, external_calls, cost_units, output_bytes.
    Optional booleans: network_required, model_change, production_change.
    """
    policy = policy or GuardPolicy()
    action_id = request.get("action_id")
    action_class = request.get("action_class")
    purpose = request.get("purpose")
    expected_effect = request.get("expected_effect")

    def deny(code: str, reason: str) -> GuardDecision:
        return GuardDecision(False, code, reason, str(action_class or "UNKNOWN"), {
            "action_id": action_id,
            "policy": "V91_GLOBAL_GUARD",
            "decision": "DENY",
            "reason_code": code,
        })

    if not isinstance(action_id, str) or not action_id.strip():
        return deny("MISSING_ACTION_ID", "Action ID fehlt.")
    if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 500:
        return deny("INVALID_PURPOSE", "Zweck fehlt oder ist länger als 500 Zeichen.")
    if (not isinstance(expected_effect, str) or not expected_effect.strip()
            or len(expected_effect) > 500):
        return deny("INVALID_EXPECTED_EFFECT", "Erwartete Wirkung fehlt oder ist zu lang.")
    if not isinstance(action_class, str) or action_class not in KNOWN_CLASSES:
        return deny("UNKNOWN_ACTION_CLASS", "Unbekannte Handlungsklasse: fail-closed.")
    if action_class in DENIED_CLASSES:
        return deny("PROHIBITED_ACTION_CLASS", "Diese Handlungsklasse ist durch die Schutzrichtlinie gesperrt.")

    numeric_fields = {
        "steps": policy.max_steps,
        "external_calls": policy.max_external_calls,
        "cost_units": policy.max_cost_units,
        "output_bytes": policy.max_output_bytes,
    }
    for field, maximum in numeric_fields.items():
        value = request.get(field, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return deny("INVALID_RESOURCE_ESTIMATE", f"{field} muss eine nicht-negative Ganzzahl sein.")
        if value > maximum:
            return deny("RESOURCE_LIMIT_EXCEEDED", f"{field}={value} überschreitet das Limit {maximum}.")

    if action_class not in policy.allowed_capabilities:
        return deny("CAPABILITY_NOT_GRANTED", f"Keine explizite Freigabe für {action_class}.")
    if (action_class in NETWORK_CLASSES or request.get("network_required", False)) and not policy.allow_network:
        return deny("NETWORK_DISABLED", "Netzwerkzugriff ist standardmäßig gesperrt.")
    if (action_class == "model_change" or request.get("model_change", False)) and not policy.allow_model_changes:
        return deny("MODEL_CHANGE_DISABLED", "Modelländerungen benötigen eine separate Freigabe.")
    if (action_class == "production_change" or request.get("production_change", False)) and not policy.allow_production_changes:
        return deny("PRODUCTION_CHANGE_DISABLED", "Produktionsänderungen sind standardmäßig gesperrt.")
    if action_class in MUTATING_CLASSES and policy.require_human_approval_for_mutations and not human_approved:
        return deny("HUMAN_APPROVAL_REQUIRED", "Ändernde Aktion benötigt eine ausdrückliche menschliche Freigabe.")

    return GuardDecision(True, "ALLOW_WITHIN_POLICY",
                         "Strukturierte Anfrage erfüllt die konfigurierten Grenzen.",
                         action_class, {
        "action_id": action_id,
        "policy": "V91_GLOBAL_GUARD",
        "decision": "ALLOW",
        "reason_code": "ALLOW_WITHIN_POLICY",
        "limits_checked": list(numeric_fields),
        "note": "Erlaubnis ist keine Ausführung und kein Nachweis eines sicheren Gesamtsystems.",
    })
