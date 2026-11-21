#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Daily report assembler (Tagesbericht-Standard, docs/V91-TAGESBERICHT-
STANDARD.md, PR #130): renders an A/B/C daily report fail-closed.

STANDARDSKRIPTE != BERICHTSBETRIEB: this module ASSEMBLES a report
from supplied artifacts when called; it runs no timer, no daemon and
claims no operating state (SCRIPTED != INSTALLED).

Fail-closed rules (UNKNOWN != PASS, CLAIM != EVIDENCE):

1. Teil A (global) and Teil B (local) entries pass ONLY with claim,
   source and date; anything else is REJECTED and collected, never
   silently dropped. An empty Teil A/B is honest and valid.
2. Teil C shows ONLY the checks that were supplied, each with its
   own head SHA. A check against a different SHA than the current
   repo head is marked STALE_HEAD, evidence for an older state.
3. CI status is GREEN only if every check is 'success' AND matches
   the current head. No checks supplied means UNKNOWN, never GREEN.
4. The report labels itself: generated_by a script, no operating
   claims. No part of this report may be presented as a running
   system's output.
"""

from __future__ import annotations

ALLOWED_CHECK_CONCLUSIONS = ("success", "failure", "skipped", "cancelled")


class DailyReportError(Exception):
    """Raised when the report input is malformed."""


def _entry_ok(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    for key in ("claim", "source", "date"):
        value = entry.get(key)
        if not isinstance(value, str) or not value.strip():
            return False
    return True


def _check_ok(check) -> bool:
    if not isinstance(check, dict):
        return False
    name = check.get("name")
    head = check.get("head_sha")
    conclusion = check.get("conclusion")
    if not isinstance(name, str) or not name.strip():
        return False
    if not isinstance(head, str) or not head.strip():
        return False
    return conclusion in ALLOWED_CHECK_CONCLUSIONS


def assemble_daily_report(data) -> dict:
    """Assemble an honest A/B/C daily report. Fail closed."""
    if not isinstance(data, dict):
        raise DailyReportError("data must be a dict")

    violations: list[str] = []
    report_id = data.get("report_id")
    date = data.get("date")
    if not isinstance(report_id, str) or not report_id.strip():
        violations.append("report:report_id_missing")
    if not isinstance(date, str) or not date.strip():
        violations.append("report:date_missing")

    repo_head = data.get("repo_head_sha")
    if not isinstance(repo_head, str) or not repo_head.strip():
        violations.append("report:repo_head_sha_missing")

    teil_a_accepted: list[dict] = []
    for idx, entry in enumerate(data.get("global_entries", []) or []):
        if _entry_ok(entry):
            teil_a_accepted.append(
                {
                    "claim": entry["claim"].strip(),
                    "source": entry["source"].strip(),
                    "date": entry["date"].strip(),
                }
            )
        else:
            violations.append("teil_a:entry_rejected_no_claim_source_date:" + str(idx))

    teil_b_accepted: list[dict] = []
    for idx, entry in enumerate(data.get("local_entries", []) or []):
        if _entry_ok(entry):
            teil_b_accepted.append(
                {
                    "claim": entry["claim"].strip(),
                    "source": entry["source"].strip(),
                    "date": entry["date"].strip(),
                }
            )
        else:
            violations.append("teil_b:entry_rejected_no_claim_source_date:" + str(idx))

    next_step = data.get("local_next_step")
    if next_step is not None and (
        not isinstance(next_step, str) or not next_step.strip()
    ):
        violations.append("teil_b:empty_next_step_supplied")

    checks_rendered: list[dict] = []
    for idx, check in enumerate(data.get("checks", []) or []):
        if not _check_ok(check):
            violations.append("teil_c:malformed_check:" + str(idx))
            continue
        rendered = {
            "name": check["name"].strip(),
            "head_sha": check["head_sha"].strip(),
            "conclusion": check["conclusion"],
        }
        if (
            isinstance(repo_head, str)
            and repo_head.strip()
            and rendered["head_sha"] != repo_head.strip()
        ):
            rendered["head_match"] = False
            rendered["stale_head"] = True
        else:
            rendered["head_match"] = True
            rendered["stale_head"] = False
        checks_rendered.append(rendered)

    if not checks_rendered:
        ci_status = "UNKNOWN"
    else:
        green = all(
            chk["conclusion"] == "success" and not chk["stale_head"]
            for chk in checks_rendered
        )
        ci_status = "GREEN" if green else "RED"

    result = {
        "report_id": report_id if isinstance(report_id, str) else None,
        "date": date if isinstance(date, str) else None,
        "generated_by": (
            "controller.daily_report (SKRIPT != BETRIEB, kein laufender "
            "Berichtsbetrieb, SCRIPTED != INSTALLED)"
        ),
        "teil_a_global": teil_a_accepted,
        "teil_b_local": {
            "entries": teil_b_accepted,
            "next_step": next_step if isinstance(next_step, str) else None,
        },
        "teil_c_technical": {
            "repo_head_sha": repo_head if isinstance(repo_head, str) else None,
            "checks": checks_rendered,
            "ci_status": ci_status,
        },
        "violations": violations,
    }
    return result
