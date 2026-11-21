#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Finding registry with dispute and correction lifecycle
(Issue #276, capability 3: evidence and integrity; acceptance
criterion: false-positive rate, disputed findings, correction
outcomes, time to resolution).

Fail-closed registry for findings. A finding enters with evidence
claims, may be disputed by anyone, and every dispute MUST be resolved
before the finding may be counted as verified. Refutation produces a
FALSE_POSITIVE entry with a mandatory correction note; the original
claim text is NEVER deleted or overwritten (corrections append, they
do not erase).

Fail-closed rules (UNKNOWN != PASS, CLAIM != EVIDENCE):

1. DISPUTED != WIDERLEGT: a dispute is a question, not a verdict.
   While any dispute is open, the finding can neither be VERIFIED
   nor counted as verified anywhere.
2. WIDERLEGUNG braucht Beweis: FALSE_POSITIVE requires refutation
   evidence (source + date), never the disputer's word alone.
3. KORREKTUR != LOESCHUNG: corrected findings keep the original
   claim; the correction is appended with its own evidence and date.
   ORIGINAL BELEGT BLEIBT.
4. RESOLUTION braucht eine andere Person als die Erhebung
   (INDEPENDENT != IDENTISCH).
5. UNKNOWN stays UNKNOWN: without evidence a finding stays
   UNKNOWN and never passes.
6. Honesty: the registry counts findings, it does not establish
   truth. REGISTRY != WAHRHEIT, REVIEW != DECISION, SCRIPTED !=
   INSTALLED.
"""

from __future__ import annotations

ALLOWED_STATUSES = (
    "UNKNOWN",
    "CLAIMED",
    "VERIFIED",
    "DISPUTED",
    "FALSE_POSITIVE",
    "CORRECTED",
)

ALLOWED_RESOLUTIONS = ("upheld", "refuted", "corrected")


class FindingRegistryError(Exception):
    """Raised when registry records are malformed."""


def _require_str(record: dict, key: str) -> None:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FindingRegistryError("field_missing:" + key)


def _valid_evidence(evidence) -> bool:
    return (
        isinstance(evidence, dict)
        and isinstance(evidence.get("source"), str)
        and evidence.get("source").strip()
        and isinstance(evidence.get("checked_on"), str)
        and evidence.get("checked_on").strip()
    )


def new_registry() -> dict:
    return {"findings": {}}


def register_finding(registry: dict, finding: dict) -> str:
    """Register a new finding. Fail closed: UNKNOWN != PASS."""
    if not isinstance(registry, dict) or "findings" not in registry:
        raise FindingRegistryError("registry_malformed")
    if not isinstance(finding, dict):
        raise FindingRegistryError("finding_not_a_dict")
    for key in ("finding_id", "claim", "raised_by"):
        _require_str(finding, key)
    if finding["finding_id"] in registry["findings"]:
        raise FindingRegistryError("duplicate_finding_id:" + finding["finding_id"])

    evidence = finding.get("evidence")
    if evidence is not None and not _valid_evidence(evidence):
        raise FindingRegistryError("evidence_malformed")
    status = "CLAIMED" if _valid_evidence(evidence) else "UNKNOWN"
    registry["findings"][finding["finding_id"]] = {
        "finding_id": finding["finding_id"],
        "claim": finding["claim"],
        "raised_by": finding["raised_by"],
        "evidence": evidence,
        "status": status,
        "disputes": [],
        "verifications": [],
        "corrections": [],
    }
    return status


def add_verification(registry: dict, finding_id: str, verification: dict) -> str:
    """Add independent verification. DISPUTED blocks VERIFIED."""
    if not isinstance(registry, dict) or finding_id not in registry.get("findings", {}):
        raise FindingRegistryError("finding_not_found:" + str(finding_id))
    for key in ("verified_by", "method"):
        _require_str(verification, key)
    entry = registry["findings"][finding_id]
    if verification["verified_by"] == entry["raised_by"]:
        raise FindingRegistryError("verification_not_independent:same_as_raiser")
    if verification["verified_by"] in [v.get("verified_by") for v in entry["verifications"]]:
        raise FindingRegistryError("verification_duplicate_person")
    if _has_open_dispute(entry):
        raise FindingRegistryError("dispute_open:no_verification_while_disputed")
    if not _valid_evidence(verification.get("evidence")):
        raise FindingRegistryError("evidence_malformed")
    entry["verifications"].append(
        {
            "verified_by": verification["verified_by"],
            "method": verification["method"],
            "evidence": verification["evidence"],
        }
    )
    if entry["status"] in ("UNKNOWN", "CLAIMED"):
        entry["status"] = "VERIFIED"
    return entry["status"]


def raise_dispute(registry: dict, finding_id: str, dispute: dict) -> str:
    """Raise a dispute. DISPUTED != WIDERLEGT: a question, not a verdict."""
    if not isinstance(registry, dict) or finding_id not in registry.get("findings", {}):
        raise FindingRegistryError("finding_not_found:" + str(finding_id))
    for key in ("disputed_by", "reason"):
        _require_str(dispute, key)
    entry = registry["findings"][finding_id]
    if dispute["disputed_by"] == entry["raised_by"]:
        raise FindingRegistryError("cannot_dispute_own_finding")
    entry["disputes"].append(
        {
            "disputed_by": dispute["disputed_by"],
            "reason": dispute["reason"],
            "disputed_on": dispute.get("disputed_on", ""),
            "resolution": None,
        }
    )
    if entry["status"] not in ("FALSE_POSITIVE", "CORRECTED"):
        entry["status"] = "DISPUTED"
    return entry["status"]


def resolve_dispute(registry: dict, finding_id: str, resolution_record: dict) -> str:
    """Resolve the oldest open dispute. Fail closed on independence."""
    if not isinstance(registry, dict) or finding_id not in registry.get("findings", {}):
        raise FindingRegistryError("finding_not_found:" + str(finding_id))
    for key in ("resolved_by", "resolution", "resolved_on"):
        _require_str(resolution_record, key)
    if resolution_record["resolution"] not in ALLOWED_RESOLUTIONS:
        raise FindingRegistryError("resolution_unknown:" + str(resolution_record["resolution"]))

    entry = registry["findings"][finding_id]
    open_disputes = [d for d in entry["disputes"] if d["resolution"] is None]
    if not open_disputes:
        raise FindingRegistryError("no_open_dispute")
    dispute = open_disputes[0]
    if resolution_record["resolved_by"] == dispute["disputed_by"]:
        raise FindingRegistryError("resolution_not_independent:same_as_disputer")

    dispute["resolution"] = {
        "resolved_by": resolution_record["resolved_by"],
        "resolution": resolution_record["resolution"],
        "resolved_on": resolution_record["resolved_on"],
    }

    if resolution_record["resolution"] == "upheld":
        if _valid_evidence(entry.get("evidence")):
            entry["status"] = "VERIFIED"
        else:
            entry["status"] = "UNKNOWN"
    elif resolution_record["resolution"] == "refuted":
        if not _valid_evidence(resolution_record.get("refutation_evidence")):
            raise FindingRegistryError("refutation_needs_evidence")
        entry["status"] = "FALSE_POSITIVE"
    return entry["status"]


def add_correction(registry: dict, finding_id: str, correction: dict) -> str:
    """Append a correction. KORREKTUR != LOESCHUNG: original stays."""
    if not isinstance(registry, dict) or finding_id not in registry.get("findings", {}):
        raise FindingRegistryError("finding_not_found:" + str(finding_id))
    for key in ("corrected_by", "corrected_claim"):
        _require_str(correction, key)
    if not _valid_evidence(correction.get("evidence")):
        raise FindingRegistryError("evidence_malformed")
    entry = registry["findings"][finding_id]
    if _has_open_dispute(entry):
        raise FindingRegistryError("dispute_open:no_correction_while_disputed")
    entry["corrections"].append(
        {
            "corrected_by": correction["corrected_by"],
            "corrected_claim": correction["corrected_claim"],
            "evidence": correction["evidence"],
            "corrected_on": correction.get("corrected_on", ""),
        }
    )
    entry["status"] = "CORRECTED"
    return entry["status"]


def _has_open_dispute(entry: dict) -> bool:
    return any(d["resolution"] is None for d in entry["disputes"])


def summarize(registry: dict) -> dict:
    """Counts by status. DISPUTED never counts as verified."""
    if not isinstance(registry, dict) or "findings" not in registry:
        raise FindingRegistryError("registry_malformed")
    by_status: dict[str, int] = {status: 0 for status in ALLOWED_STATUSES}
    disputed_open = 0
    for entry in registry["findings"].values():
        by_status[entry["status"]] = by_status.get(entry["status"], 0) + 1
        if _has_open_dispute(entry):
            disputed_open += 1
    total = len(registry["findings"])
    return {
        "findings_total": total,
        "by_status": by_status,
        "disputes_open": disputed_open,
        "false_positive_rate": (
            by_status["FALSE_POSITIVE"] / total if total else None
        ),
        "verified_count": by_status["VERIFIED"],
        "honesty_limits": (
            "REGISTRY != WAHRHEIT, DISPUTED != WIDERLEGT, "
            "KORREKTUR != LOESCHUNG, UNKNOWN != PASS, "
            "REVIEW != DECISION, SCRIPTED != INSTALLED"
        ),
    }
