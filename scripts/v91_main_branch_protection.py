#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Main-branch protection: CHECK -> (explicit APPLY) -> RE-CHECK -> REPORT.

Reality-first rules of this module (consistent with the V91 audit core):
- SCRIPTED != INSTALLED: this code never touches GitHub by itself. Real
  requests happen only through the GitHub CLI (gh), authenticated by the
  operator; this module never reads, stores, or logs tokens.
- UNKNOWN != PASS: a failed gh call is NEVER interpreted as "unprotected".
  GitHub answers 403 (no rights), 404 (no rule, or rule hidden by missing
  rights), and network errors differently; each maps to its own honest
  status. Only a 200 answer counts as PROTECTED.
- CHECK_ONLY default: changing the protection rule requires the explicit
  --apply flag (same opt-in principle as V91_ENABLE_REAL_ACTIONS).
- After an apply, the rule is re-read and the core fields are compared
  against the requested state; a mismatch is reported, never smoothed over.

Proposed as a PowerShell snippet in an external report (2026-11-23) whose
status attributes (ACTIVE, DRIFT:0/3, CS:SYNC) were TEXT-ONLY with zero
repository hits; this module is the real, CI-tested implementation of the
legitimate core idea, with two corrections the draft needed:
  1. draft treated any gh exit code != 0 as "unprotected" (rights gaps
     would silently read as "no protection");
  2. draft set required_status_checks.strict=True together with an empty
     contexts list, which enforces nothing and misrepresents the rule.
"""

import argparse
import json
import os
import sys
import tempfile
import time
from typing import Any, Callable

# Exit codes (same convention as domain_usecase_gate): 0 verified
# protected / applied+verified, 1 concrete failure, 2 unknown.
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_UNKNOWN = 2

STATUS_PROTECTED = "PROTECTED"
STATUS_PROTECTED_VERIFIED = "PROTECTED_VERIFIED"
STATUS_NOT_PROTECTED_OR_NOT_VISIBLE = "UNKNOWN_NOT_PROTECTED_OR_NOT_VISIBLE"
STATUS_ACCESS_DENIED = "UNKNOWN_ACCESS_DENIED"
STATUS_GH_CLI_MISSING = "UNKNOWN_GH_CLI_MISSING"
STATUS_APPLY_REFUSED_CHECK_ONLY = "APPLY_REFUSED_CHECK_ONLY"
STATUS_APPLY_FAILED = "APPLY_FAILED"
STATUS_APPLY_MISMATCH = "APPLY_MISMATCH"

_ACCEPT_HEADER = "application/vnd.github+json"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _validate_target(owner: Any, repo: Any, branch: Any) -> tuple[str, str, str]:
    """Fail-closed input validation: no defaults for owner/repo/branch."""
    for name, value in (("owner", owner), ("repo", repo), ("branch", branch)):
        if not isinstance(value, str) or not value.strip() or "/" in value or " " in value:
            raise ValueError(f"{name} must be a non-empty identifier without whitespace or slashes")
    return owner.strip(), repo.strip(), branch.strip()


def _classify_get(returncode: int, stderr: str) -> str:
    """Classify a protection GET honestly (never guess 'unprotected')."""
    if returncode == 0:
        return STATUS_PROTECTED
    low = (stderr or "").lower()
    if "gh: command not found" in low or "not recognized" in low:
        return STATUS_GH_CLI_MISSING
    if '"message": "not found"' in low or "http 404" in low or " 404 " in low or low.startswith("404"):
        # 404 covers "no protection rule" AND "no permission to see the rule";
        # GitHub does not distinguish them for read-restricted users.
        return STATUS_NOT_PROTECTED_OR_NOT_VISIBLE
    if "http 403" in low or " 403 " in low or low.startswith("403"):
        return STATUS_ACCESS_DENIED
    return "UNKNOWN_GH_ERROR"


def build_apply_payload(required_checks: list[str] | None = None) -> dict[str, Any]:
    """Clean baseline protection rule (protocol: block force-push/deletion)."""
    checks = [str(c).strip() for c in (required_checks or []) if str(c).strip()]
    return {
        "required_status_checks": {
            # strict only with non-empty contexts: strict + empty list
            # enforces nothing and misstates the rule (draft bug #2).
            "strict": bool(checks),
            "contexts": checks,
        },
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 1,
        },
        "restrictions": None,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": False,
        "required_conversation_resolution": True,
    }


def check_protection(
    owner: str,
    repo: str,
    branch: str,
    runner: Callable[[list[str]], tuple[int, str, str]],
) -> dict[str, Any]:
    """Read the current protection state. Never modifies anything."""
    o, r, b = _validate_target(owner, repo, branch)
    endpoint = f"repos/{o}/{r}/branches/{b}/protection"
    try:
        rc, out, err = runner(["gh", "api", endpoint])
    except FileNotFoundError:
        rc, out, err = 127, "", "gh: command not found"
    status = _classify_get(rc, err)
    return {
        "timestamp_utc": _utc_now(),
        "repository": f"{o}/{r}",
        "branch": b,
        "mode": "CHECK_ONLY",
        "status": status,
        "exit_code": EXIT_OK if status == STATUS_PROTECTED else (EXIT_FAIL if status == STATUS_NOT_PROTECTED_OR_NOT_VISIBLE else EXIT_UNKNOWN),
    }


def apply_protection(
    owner: str,
    repo: str,
    branch: str,
    required_checks: list[str] | None = None,
    allow_apply: bool = False,
    runner: Callable[[list[str]], tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    """Check -> (opt-in apply) -> re-check -> verify core fields."""
    o, r, b = _validate_target(owner, repo, branch)
    if not allow_apply:
        return {
            "timestamp_utc": _utc_now(),
            "repository": f"{o}/{r}",
            "branch": b,
            "mode": "APPLY",
            "status": STATUS_APPLY_REFUSED_CHECK_ONLY,
            "exit_code": EXIT_FAIL,
            "note": "apply requires explicit allow_apply=True / --apply; forcing protection states without confirmation is not autonomous",
        }
    if runner is None:
        raise ValueError("runner must be injected; this module never performs network I/O itself")
    endpoint = f"repos/{o}/{r}/branches/{b}/protection"
    calls: list[list[str]] = []

    def rec(cmd: list[str]) -> tuple[int, str, str]:
        calls.append(cmd)
        return runner(cmd)

    payload = build_apply_payload(required_checks)
    fd, payload_path = tempfile.mkstemp(suffix=".json", prefix="v91_protection_payload_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    try:
        rc, out, err = rec(["gh", "api", "--method", "PUT", "-H", f"Accept: {_ACCEPT_HEADER}", endpoint, "--input", payload_path])
    finally:
        os.unlink(payload_path)

    apply_status = "APPLIED" if rc == 0 else "APPLY_FAILED"

    # Re-check: only a 200 answer after the PUT counts as verified.
    rc2, out2, err2 = rec(["gh", "api", endpoint])
    verified_state = json.loads(out2) if (rc2 == 0 and out2.strip()) else {}

    mismatch: list[str] = []
    if rc2 == 0:
        if verified_state.get("allow_force_pushes", {}).get("enabled") is not False:
            mismatch.append("allow_force_pushes")
        if verified_state.get("allow_deletions", {}).get("enabled") is not False:
            mismatch.append("allow_deletions")
        if verified_state.get("enforce_admins", {}).get("enabled") is not True:
            mismatch.append("enforce_admins")
    mismatch_note = "; ".join(mismatch) if mismatch else None

    if rc != 0:
        status = STATUS_APPLY_FAILED
        exit_code = EXIT_FAIL
    elif rc2 != 0:
        status = _classify_get(rc2, err2)  # apply reported ok but verify failed: honest re-read state
        exit_code = EXIT_UNKNOWN
    elif mismatch:
        status = STATUS_APPLY_MISMATCH
        exit_code = EXIT_FAIL
    else:
        status = STATUS_PROTECTED_VERIFIED
        exit_code = EXIT_OK

    # Audit trail: callee names and args only; stdout/stderr content is
    # intentionally NOT recorded because API payloads may contain
    # account-internal information (fail-closed default, no secrets in logs).
    return {
        "timestamp_utc": _utc_now(),
        "repository": f"{o}/{r}",
        "branch": b,
        "mode": "APPLY",
        "status": status,
        "exit_code": exit_code,
        "apply_status": apply_status,
        "mismatch_fields": mismatch_note,
        "requested_rule": payload,
        "gh_calls": calls,
    }


def write_report(report: dict[str, Any], report_dir: str | None = None) -> str:
    """Persist the report as JSON. Returns the file path. No secrets involved."""
    if report_dir:
        os.makedirs(report_dir, exist_ok=True)
        directory = report_dir
    else:
        directory = tempfile.mkdtemp(prefix="v91_main_protection_")
    path = os.path.join(directory, "protection_report.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V91 main-branch protection: check -> opt-in apply -> re-check -> report (SCRIPTED != INSTALLED)")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--apply", action="store_true", help="explicit opt-in; default is check-only")
    parser.add_argument("--required-checks", nargs="*", default=[], help="required status check context names")
    parser.add_argument("--report-dir", default=None)
    args = parser.parse_args(argv)

    def run_gh(cmd: list[str]) -> tuple[int, str, str]:
        # Real mode (operator machine only): gh handles auth; this module
        # never reads tokens. Check-only callers get here without risk.
        import subprocess

        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr

    if args.apply:
        report = apply_protection(
            args.owner, args.repo, args.branch,
            required_checks=list(args.required_checks),
            allow_apply=True, runner=run_gh,
        )
    else:
        report = check_protection(args.owner, args.repo, args.branch, runner=run_gh)
    report_path = write_report(report, args.report_dir)
    report["report_path"] = report_path
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(report["exit_code"])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
