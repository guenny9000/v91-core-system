#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Decision dossier (Issue #268, second core slice): a validated record
format that keeps facts, personal account, inference and decision
STRICTLY SEPARATE before any consequential assessment of a person.

Fail-closed rules (UNKNOWN != PASS, CLAIM != EVIDENCE):
- Every verified fact carries its own source; a fact without source
  is not a fact.
- The person's own account is recorded (given or explicitly declined
  with a record entry); an assessment without the person's side is
  not complete.
- Inferences are SECOND-CLASS: each inference must carry its basis
  and an explicit uncertainty note, and is never allowed to appear
  as fact. An empty inference list is honest and valid.
- The dossier must invite corrections, name uncertainty, carry a
  response deadline (>= 1 day) and an escalation route, preserve
  statutory external rights, and demand human review before any
  automated score can affect the person.

Honest limits (SCRIPTED != INSTALLED, REVIEW != ENTSCHEIDUNG):
- This validates the structure of an assessment dossier; it does not
  run in any authority and does not prove the recorded facts are
  true (SIGNATUR != WAHRHEIT). OBSERVED != ERFOLG.
"""

from __future__ import annotations

from typing import Any

REQUIRED_STRINGS = (
    "dossier_id", "decision_id", "date", "assessor",
    "uncertainty", "decision", "outcome", "escalation_route",
)


class DecisionDossierError(ValueError):
    """Raised fail-closed with collected violations: UNKNOWN != PASS."""


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_decision_dossier(record: Any) -> dict[str, Any]:
    """Validate a person-assessment dossier, fail-closed."""
    violations: list[str] = []
    if not isinstance(record, dict):
        raise DecisionDossierError(["record: dict required"])

    for key in REQUIRED_STRINGS:
        if not _nonempty_str(record.get(key)):
            violations.append(key + ": non-empty string required")

    # Verified facts: non-empty, each with own source.
    facts = record.get("verified_facts")
    if not isinstance(facts, list) or not facts:
        violations.append("verified_facts: non-empty list required")
    else:
        for i, entry in enumerate(facts):
            if (not isinstance(entry, dict)
                    or not _nonempty_str(entry.get("fact"))
                    or not _nonempty_str(entry.get("source"))):
                violations.append(
                    f"verified_facts[{i}]: fact and source required "
                    "(FAKTUM OHNE QUELLE IST KEIN FAKTUM)")

    # Personal account: given (own words) or explicitly declined.
    account = record.get("personal_account")
    if not isinstance(account, dict):
        violations.append("personal_account: dict required")
    else:
        mode = account.get("mode")
        if mode == "given":
            if not _nonempty_str(account.get("text")):
                violations.append("personal_account.text: required when given")
        elif mode == "declined_with_record":
            if not _nonempty_str(account.get("record_entry")):
                violations.append(
                    "personal_account.record_entry: required when declined")
        else:
            violations.append(
                "personal_account.mode: must be given or declined_with_record")

    # Inferences: second-class, each with basis and uncertainty note.
    inferences = record.get("inferences")
    if not isinstance(inferences, list):
        violations.append("inferences: list required (may be empty)")
    else:
        for i, entry in enumerate(inferences):
            if (not isinstance(entry, dict)
                    or not _nonempty_str(entry.get("inference"))
                    or not _nonempty_str(entry.get("basis"))
                    or not _nonempty_str(entry.get("uncertainty_note"))
                    or entry.get("marked_uncertain") is not True):
                violations.append(
                    f"inferences[{i}]: inference, basis, uncertainty_note "
                    "and marked_uncertain=True required "
                    "(SCHLUSS IST KEIN FAKT)")

    # Corrections must be invited; applied corrections carry an entry.
    if record.get("correction_invited") is not True:
        violations.append("correction_invited: must be explicitly True")
    corrections = record.get("corrections")
    if corrections is not None:
        if not isinstance(corrections, list):
            violations.append("corrections: list required when present")
        else:
            for i, entry in enumerate(corrections):
                if (not isinstance(entry, dict)
                        or not _nonempty_str(entry.get("error"))
                        or not _nonempty_str(entry.get("correction"))):
                    violations.append(
                        f"corrections[{i}]: error and correction required")

    # Response deadline: reasonable, at least one day.
    deadline = record.get("response_deadline_days")
    if not isinstance(deadline, int) or isinstance(deadline, bool) or deadline < 1:
        violations.append("response_deadline_days: integer >= 1 required")

    # Statutory rights stay outside and above V91.
    if record.get("statutory_external_rights_preserved") is not True:
        violations.append(
            "statutory_external_rights_preserved: must be explicitly True")

    # Human review before any automated score matters.
    if record.get("human_review_before_automation") is not True:
        violations.append(
            "human_review_before_automation: must be explicitly True")

    if violations:
        raise DecisionDossierError(violations)

    return dict(record)
