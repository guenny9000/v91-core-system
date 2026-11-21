#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Appeal process for automated decisions (Issue #276, capability 7:
human rights and due process).

Fail-closed appeal lifecycle. An appeal against a consequential
automated decision can be filed, gets an independent reviewer, may
collect evidence while open, and must be resolved with one of three
outcomes. The process protects lawful criticism, requires documented
suspension of consequential effects while the appeal is open, and
keeps privacy by processing structural records only.

Fail-closed rules (UNKNOWN != PASS):

1. CRITICISM != VERBOT: appeal grounds are never inspected for
   content; criticism of the decision, its maker or the system is
   structural free speech. Only malformed structure fails closed.
2. EFFECTS SUSPENDED: at filing, the appeal must document that the
   consequential effects of the decision are suspended while the
   appeal is open (REVIEW gets a real chance, not a fait accompli).
3. INDEPENDENT REVIEW: the assigned reviewer must differ from the
   appellant AND from the original decision maker; the resolver
   must satisfy the same independence (REVIEWER != RICHTER IN
   EIGENER SACHE).
4. NO DUPLICATE OPEN APPEALS: one open appeal per appellant per
   decision; duplicates are refused instead of silently merged.
5. OVERTURN != LOESCHUNG: resolution appends an outcome; the
   original decision record is never removed or rewritten.
6. APPEAL OUTCOMES: upheld, overturned, remanded (back for a new,
   documented decision). Anything else fails closed.
7. PRIVACY (LEAST DATA): the process stores IDs and statuses only;
   summarize() emits counts, never personal data.

Honest limits:
- This module validates process records; it runs inside no court,
  authority, employer or platform, and a passing appeal lifecycle
  proves documentation quality, not real-world justice.
- RECORDS != GERECHTIGKEIT, REVIEW != WAHRHEIT, SCRIPTED != INSTALLED.
- Suspension of effects must be documented, but this module cannot
  enforce it in any external system (DOCUMENTED != DURCHGESETZT).
"""

from __future__ import annotations

APPEAL_STATUS_PENDING = "PENDING"
APPEAL_STATUS_IN_REVIEW = "IN_REVIEW"
APPEAL_STATUS_RESOLVED = "RESOLVED"

ALLOWED_GROUNDS = frozenset({
    "factual_error",
    "procedural_error",
    "new_evidence",
    "proportionality",
    "discrimination_concern",
    "criticism_of_decision",
})

ALLOWED_OUTCOMES = frozenset({"upheld", "overturned", "remanded"})

REQUIRED_APPEAL_STRINGS = (
    "appeal_id",
    "decision_id",
    "decision_maker",
    "appellant",
    "filed_on",
)


class AppealProcessError(Exception):
    """Raised fail-closed with a machine-readable reason."""


def _require_str(record: dict, key: str) -> None:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AppealProcessError("field_missing_or_empty:" + key)


def _validate_struct(caseload: dict) -> None:
    if not isinstance(caseload, dict) or "appeals" not in caseload:
        raise AppealProcessError("caseload_malformed")
    if not isinstance(caseload["appeals"], dict):
        raise AppealProcessError("appeals_must_be_dict")


def new_caseload() -> dict:
    return {"appeals": {}}


def file_appeal(caseload: dict, appeal: dict) -> str:
    """File a new appeal. CRITICISM != VERBOT, structure only."""
    _validate_struct(caseload)
    if not isinstance(appeal, dict):
        raise AppealProcessError("appeal_not_a_dict")
    for key in REQUIRED_APPEAL_STRINGS:
        _require_str(appeal, key)
    grounds = appeal.get("grounds")
    if not isinstance(grounds, list) or not grounds:
        raise AppealProcessError("grounds_missing")
    for ground in grounds:
        if ground not in ALLOWED_GROUNDS:
            raise AppealProcessError("ground_unknown:" + str(ground))
    if appeal.get("effects_suspended") is not True:
        raise AppealProcessError("effects_must_be_suspended_during_appeal")

    appeal_id = appeal["appeal_id"]
    if appeal_id in caseload["appeals"]:
        raise AppealProcessError("duplicate_appeal_id:" + appeal_id)
    for entry in caseload["appeals"].values():
        if (
            entry["decision_id"] == appeal["decision_id"]
            and entry["appellant"] == appeal["appellant"]
            and entry["status"] != APPEAL_STATUS_RESOLVED
        ):
            raise AppealProcessError(
                "duplicate_open_appeal:" + str(appeal["decision_id"])
            )

    evidence = appeal.get("evidence")
    if evidence is not None and (
        not isinstance(evidence, list)
        or not all(isinstance(item, dict) for item in evidence)
    ):
        raise AppealProcessError("evidence_malformed")

    caseload["appeals"][appeal_id] = {
        "appeal_id": appeal_id,
        "decision_id": appeal["decision_id"],
        "decision_maker": appeal["decision_maker"],
        "appellant": appeal["appellant"],
        "filed_on": appeal["filed_on"],
        "grounds": list(grounds),
        "effects_suspended": True,
        "status": APPEAL_STATUS_PENDING,
        "reviewer": None,
        "evidence": list(evidence) if evidence is not None else [],
        "outcome": None,
        "resolved_on": None,
    }
    return APPEAL_STATUS_PENDING


def _independent_reviewer(appeal: dict, person: str) -> bool:
    return (
        isinstance(person, str)
        and person.strip()
        and person != appeal["appellant"]
        and person != appeal["decision_maker"]
    )


def assign_review(caseload: dict, appeal_id: str, assignment: dict) -> str:
    """Assign an independent reviewer. REVIEWER != PARTEI."""
    _validate_struct(caseload)
    if appeal_id not in caseload["appeals"]:
        raise AppealProcessError("appeal_not_found:" + str(appeal_id))
    for key in ("reviewer", "qualification"):
        _require_str(assignment, key)
    appeal = caseload["appeals"][appeal_id]
    if appeal["status"] != APPEAL_STATUS_PENDING:
        raise AppealProcessError("appeal_not_pending:" + appeal["status"])
    reviewer = assignment["reviewer"]
    if not _independent_reviewer(appeal, reviewer):
        raise AppealProcessError("reviewer_not_independent")
    if reviewer in [item.get("person") for item in appeal["evidence"]]:
        # No evidence contribution before assignment: keeps the
        # reviewer's record clean of prior involvement.
        raise AppealProcessError("reviewer_contributed_evidence")
    appeal["reviewer"] = reviewer
    appeal["reviewer_qualification"] = assignment["qualification"]
    appeal["status"] = APPEAL_STATUS_IN_REVIEW
    return APPEAL_STATUS_IN_REVIEW


def add_evidence(caseload: dict, appeal_id: str, evidence_item: dict) -> None:
    """Attach evidence. Access limited to appellant and reviewer."""
    _validate_struct(caseload)
    if appeal_id not in caseload["appeals"]:
        raise AppealProcessError("appeal_not_found:" + str(appeal_id))
    appeal = caseload["appeals"][appeal_id]
    if appeal["status"] == APPEAL_STATUS_RESOLVED:
        raise AppealProcessError("appeal_already_resolved")
    _require_str(evidence_item, "person")
    _require_str(evidence_item, "source")
    if evidence_item["person"] not in (appeal["appellant"], appeal["reviewer"]):
        raise AppealProcessError("person_not_authorized_for_evidence")
    appeal["evidence"].append(
        {
            "person": evidence_item["person"],
            "source": evidence_item["source"],
            "checked_on": evidence_item.get("checked_on", ""),
        }
    )


def resolve_appeal(caseload: dict, appeal_id: str, resolution: dict) -> str:
    """Resolve an appeal. OVERTURN != LOESCHUNG, outcomes append."""
    _validate_struct(caseload)
    if appeal_id not in caseload["appeals"]:
        raise AppealProcessError("appeal_not_found:" + str(appeal_id))
    for key in ("resolved_by", "outcome", "resolved_on", "statement"):
        _require_str(resolution, key)
    if resolution["outcome"] not in ALLOWED_OUTCOMES:
        raise AppealProcessError("outcome_unknown:" + str(resolution["outcome"]))
    appeal = caseload["appeals"][appeal_id]
    if appeal["status"] != APPEAL_STATUS_IN_REVIEW:
        raise AppealProcessError("appeal_not_in_review:" + appeal["status"])
    if appeal["reviewer"] is not None and resolution["resolved_by"] != appeal["reviewer"]:
        # Only the assigned independent reviewer may resolve; no
        # silent substitution (REVIEW != WEISUNG).
        raise AppealProcessError("resolver_not_assigned_reviewer")
    if not _independent_reviewer(appeal, resolution["resolved_by"]):
        raise AppealProcessError("resolver_not_independent")
    if resolution["outcome"] == "remanded" and not resolution.get("remand_instructions"):
        raise AppealProcessError("remand_needs_instructions")

    appeal["outcome"] = resolution["outcome"]
    appeal["resolved_on"] = resolution["resolved_on"]
    appeal["resolution_statement"] = resolution["statement"]
    if resolution["outcome"] == "remanded":
        appeal["remand_instructions"] = resolution["remand_instructions"]
    appeal["status"] = APPEAL_STATUS_RESOLVED
    return APPEAL_STATUS_RESOLVED


def summarize(caseload: dict) -> dict:
    """Counts and honesty limits only. SUMMARIZE != PERSONENDATEN."""
    _validate_struct(caseload)
    appeals = caseload["appeals"]
    pending = 0
    in_review = 0
    resolved = 0
    by_outcome: dict[str, int] = {outcome: 0 for outcome in sorted(ALLOWED_OUTCOMES)}
    for appeal in appeals.values():
        if appeal["status"] == APPEAL_STATUS_PENDING:
            pending += 1
        elif appeal["status"] == APPEAL_STATUS_IN_REVIEW:
            in_review += 1
        elif appeal["status"] == APPEAL_STATUS_RESOLVED:
            resolved += 1
            if appeal["outcome"] in by_outcome:
                by_outcome[appeal["outcome"]] += 1
    return {
        "appeals_total": len(appeals),
        "pending": pending,
        "in_review": in_review,
        "resolved": resolved,
        "by_outcome": by_outcome,
        "honesty_limits": (
            "CRITICISM != VERBOT, REVIEW != WAHRHEIT, "
            "RECORDS != GERECHTIGKEIT, OVERTURN != LOESCHUNG, "
            "DOCUMENTED != DURCHGESETZT, SCRIPTED != INSTALLED"
        ),
    }
