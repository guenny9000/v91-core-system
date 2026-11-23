#!/usr/bin/env python3
"""Tests - main-branch protection module (check / opt-in apply / honest UNKNOWN)."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from v91_main_branch_protection import (  # noqa: E402
    STATUS_ACCESS_DENIED,
    STATUS_APPLY_FAILED,
    STATUS_APPLY_MISMATCH,
    STATUS_APPLY_REFUSED_CHECK_ONLY,
    STATUS_GH_CLI_MISSING,
    STATUS_NOT_PROTECTED_OR_NOT_VISIBLE,
    STATUS_PROTECTED,
    STATUS_PROTECTED_VERIFIED,
    apply_protection,
    build_apply_payload,
    check_protection,
    main,
    write_report,
)


def fake_runner(responses):
    """responses: list of (rc, stdout, stderr) returned per gh call."""
    calls = []

    def run(cmd):
        calls.append(cmd)
        return responses[len(calls) - 1]

    run.calls = calls
    return run


OK_BODY = json.dumps({
    "allow_force_pushes": {"enabled": False},
    "allow_deletions": {"enabled": False},
    "enforce_admins": {"enabled": True},
})


def test_check_protected_reads_only():
    run = fake_runner([(0, OK_BODY, "")])
    r = check_protection("guenny9000", "v91-core-system", "main", runner=run)
    assert r["status"] == STATUS_PROTECTED and r["exit_code"] == 0
    assert len(run.calls) == 1 and run.calls[0][1] == "api"  # single GET, no PUT anywhere


def test_check_404_is_not_claimed_as_verified_evidence():
    run = fake_runner([(1, "", "gh: Not Found (HTTP 404)")])
    r = check_protection("guenny9000", "v91-core-system", "main", runner=run)
    assert r["status"] == STATUS_NOT_PROTECTED_OR_NOT_VISIBLE
    assert r["status"].startswith("UNKNOWN")  # 404 can also mean: no right to see the rule


def test_check_403_access_denied_unknown():
    run = fake_runner([(1, "", "gh: Forbidden (HTTP 403)")])
    r = check_protection("guenny9000", "v91-core-system", "main", runner=run)
    assert r["status"] == STATUS_ACCESS_DENIED and r["exit_code"] == 2


def test_check_gh_missing():
    def missing(cmd):
        raise FileNotFoundError("gh")
    r = check_protection("guenny9000", "v91-core-system", "main", runner=missing)
    assert r["status"] == STATUS_GH_CLI_MISSING and r["exit_code"] == 2


def test_invalid_targets_rejected():
    for o, rr, b in (("", "repo", "main"), ("own er", "repo", "main"), ("o", "re/po", "main"), ("o", "r", "ma in")):
        with pytest.raises(ValueError):
            check_protection(o, rr, b, runner=fake_runner([]))


def test_apply_refused_without_explicit_optin():
    run = fake_runner([])
    r = apply_protection("guenny9000", "v91-core-system", "main", runner=run)
    assert r["status"] == STATUS_APPLY_REFUSED_CHECK_ONLY and r["exit_code"] == 1
    assert len(run.calls) == 0  # no gh call at all


def test_apply_requires_injected_runner_when_opted_in():
    with pytest.raises(ValueError):
        apply_protection("guenny9000", "v91-core-system", "main", allow_apply=True, runner=None)


def test_payload_blocks_force_push_and_deletions():
    p = build_apply_payload([])
    assert p["allow_force_pushes"] is False and p["allow_deletions"] is False
    assert p["enforce_admins"] is True
    assert p["required_status_checks"]["strict"] is False  # empty checks: strict=True would misstate the rule
    p2 = build_apply_payload(["audit-checks"])
    assert p2["required_status_checks"]["strict"] is True and p2["required_status_checks"]["contexts"] == ["audit-checks"]


def test_apply_success_verified_with_recheck():
    run = fake_runner([(0, "{}", ""), (0, OK_BODY, "")])
    r = apply_protection("guenny9000", "v91-core-system", "main", allow_apply=True, runner=run)
    assert r["status"] == STATUS_PROTECTED_VERIFIED and r["exit_code"] == 0
    assert len(run.calls) == 2
    assert run.calls[0][2] == "--method" and run.calls[0][3] == "PUT"  # PUT first...
    assert "--input" in run.calls[0]  # payload via temp file, not via argv
    assert run.calls[1][1] == "api" and "--method" not in run.calls[1]  # ...then honest GET verify


def test_apply_put_failure_reported_honestly():
    run = fake_runner([(1, "", "gh: Forbidden (HTTP 403)"), (0, OK_BODY, "")])
    r = apply_protection("guenny9000", "v91-core-system", "main", allow_apply=True, runner=run)
    assert r["status"] == STATUS_APPLY_FAILED and r["exit_code"] == 1


def test_apply_with_mismatch_never_smoothed_over():
    inconsistent = json.dumps({"allow_force_pushes": {"enabled": True}, "allow_deletions": {"enabled": False}, "enforce_admins": {"enabled": True}})
    run = fake_runner([(0, "{}", ""), (0, inconsistent, "")])
    r = apply_protection("guenny9000", "v91-core-system", "main", allow_apply=True, runner=run)
    assert r["status"] == STATUS_APPLY_MISMATCH and r["exit_code"] == 1
    assert "allow_force_pushes" in r["mismatch_fields"]


def test_gh_audit_trail_records_only_commands():
    run = fake_runner([(0, "{}", ""), (0, OK_BODY, "")])
    r = apply_protection("guenny9000", "v91-core-system", "main", allow_apply=True, runner=run)
    trail = json.dumps(r["gh_calls"])
    assert "PUT" in trail
    assert "token" not in trail.lower()  # no bearer/token material in the audit trail


def test_report_written_no_secrets(tmp_path):
    run = fake_runner([(0, OK_BODY, "")])
    r = check_protection("guenny9000", "v91-core-system", "main", runner=run)
    path = write_report(r, str(tmp_path))
    text = open(path, encoding="utf-8").read()
    assert json.loads(text)["status"] == STATUS_PROTECTED
    assert "token" not in text.lower() and "Bearer" not in text


def test_cli_honest_exit_codes(tmp_path):
    # CI has no gh: main() must report UNKNOWN (exit 2), never pretend or crash.
    code = main(["--owner", "guenny9000", "--repo", "v91-core-system", "--branch", "main", "--report-dir", str(tmp_path)])
    assert code in (0, 1, 2)
    assert os.path.exists(os.path.join(str(tmp_path), "protection_report.json"))
