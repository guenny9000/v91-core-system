#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Safe response plan validator (Issue #276, capability 6: safe
response).

Fail-closed validator for incident response plans. It documents HOW a
node intends to react to an incident and rejects every plan that
reaches beyond its own boundary: no unauthorized access, no
retaliation, no sabotage, no censorship, no destruction of records,
no denial of lawful services.

Fail-closed rules (UNKNOWN != PASS, CLAIM != EVIDENCE):

1. DETECTION != AUTHORIZATION: a finding triggers documentation, not
   intervention. Any action that affects systems, services or people
   beyond the documented own-node scope requires an explicit
   authorization record (REQUEST != AUTHORIZATION).
2. NOTIFY BEFORE IMPACT: contain/isolate/remediate on services or
   operators that others depend on require a documented operator
   notification up front (channel + addressee + date).
3. FORBIDDEN ACTIONS are hard-rejected, never "conditions":
   unauthorized_access, retaliation, censorship, sabotage,
   records_destruction, denial_of_lawful_service.
4. ISOLATE_NOT_DESTROY: isolate requires a documented recovery path;
   evidence is preserved, never deleted.
5. ZIELWERT != ERGEBNIS: remediate requires a post-change check;
   recover requires a completed verify step in the same plan
   (VERIFY_BEFORE_RECOVER).
6. Honesty: the validator judges plan documents only. PLAN !=
   AUSFUEHRUNG, REVIEW != DECISION, SCRIPTED != INSTALLED.
"""

from __future__ import annotations

ALLOWED_ACTIONS = (
    "preserve_evidence",
    "notify_operator",
    "contain",
    "isolate",
    "remediate",
    "verify",
    "recover",
)

FORBIDDEN_ACTIONS = (
    "unauthorized_access",
    "retaliation",
    "censorship",
    "sabotage",
    "records_destruction",
    "denial_of_lawful_service",
)

IMPACT_ACTIONS = ("contain", "isolate", "remediate")


class SafeResponseError(Exception):
    """Raised when a response plan is malformed."""


def _require_str(record: dict, key: str, violations: list) -> None:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        violations.append("field_missing:" + key)


def _check_detection(record: dict, violations: list) -> None:
    detection = record.get("detection")
    if not isinstance(detection, dict) or not detection:
        violations.append("detection:missing")
        return
    evidence = detection.get("evidence")
    if not isinstance(evidence, dict) or not evidence:
        violations.append("detection:evidence_missing")
    else:
        for key in ("source", "checked_on"):
            if not isinstance(evidence.get(key), str) or not evidence.get(key).strip():
                violations.append("detection:evidence_" + key + "_missing")


def _check_actions(record: dict, violations: list) -> None:
    actions = record.get("actions")
    if not isinstance(actions, list) or not actions:
        violations.append("actions:missing_or_empty")
        return
    for action in actions:
        if not isinstance(action, dict):
            violations.append("actions:malformed_entry")
            continue
        verb = action.get("verb")
        if not isinstance(verb, str) or not verb.strip():
            violations.append("actions:verb_missing")
            continue
        if verb in FORBIDDEN_ACTIONS:
            violations.append("actions:FORBIDDEN:" + verb)
            continue
        if verb not in ALLOWED_ACTIONS:
            violations.append("actions:unknown_verb:" + verb)
        if verb in IMPACT_ACTIONS:
            _check_impact_action(action, record, violations)
        if verb == "isolate":
            recovery = action.get("recovery_path")
            if not isinstance(recovery, str) or not recovery.strip():
                violations.append("isolate_not_destroy:recovery_path_missing")
        if verb == "remediate":
            post = action.get("post_change_check")
            if not isinstance(post, str) or not post.strip():
                violations.append("remediate:post_change_check_missing")
        if verb == "recover":
            has_verify = any(
                isinstance(a, dict) and a.get("verb") == "verify"
                for a in actions
                if isinstance(a, dict)
            )
            if not has_verify:
                violations.append("recover:verify_before_recover_missing")


def _check_impact_action(action: dict, record: dict, violations: list) -> None:
    if action.get("affects_others") is True:
        authorization = record.get("authorization")
        if not isinstance(authorization, dict) or not authorization:
            violations.append("authorization:missing_for_action_affecting_others")
        else:
            for key in ("authorized_by", "scope", "date"):
                value = authorization.get(key)
                if not isinstance(value, str) or not value.strip():
                    violations.append("authorization:" + key + "_missing")
        notification = action.get("operator_notified")
        if not isinstance(notification, dict) or not notification:
            violations.append("notification:operator_notification_missing")
        else:
            for key in ("addressee", "channel", "sent_on"):
                value = notification.get(key)
                if not isinstance(value, str) or not value.strip():
                    violations.append("notification:" + key + "_missing")
    if action.get("critical_service") is True:
        continuity = action.get("continuity_equivalent_proven")
        if continuity is not True:
            violations.append("critical:impact_without_proven_continuity")


def validate_response_plan(plan) -> dict:
    """Validate an incident response plan. Fail closed: UNKNOWN != PASS."""
    if not isinstance(plan, dict):
        raise SafeResponseError("plan must be a dict")

    violations: list[str] = []

    for key in ("plan_id", "date", "reviewer"):
        _require_str(plan, key, violations)

    _check_detection(plan, violations)
    _check_actions(plan, violations)

    uncertainty = plan.get("uncertainty_note")
    if not isinstance(uncertainty, str) or not uncertainty.strip():
        violations.append("record:uncertainty_note_missing")

    decision = "REJECTED" if violations else "APPROVED_FOR_DOCUMENTATION"
    return {
        "plan_id": plan.get("plan_id") if isinstance(plan.get("plan_id"), str) else None,
        "decision": decision,
        "violations": violations,
        "honesty_limits": (
            "PLAN != AUSFUEHRUNG, DETECTION != AUTHORIZATION, "
            "REQUEST != AUTHORIZATION, ISOLATE_NOT_DESTROY, "
            "REVIEW != DECISION, SCRIPTED != INSTALLED"
        ),
    }
