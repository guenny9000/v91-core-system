#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Offline smoke harness for the local-first resilience core
(Issue #8, suggested first increment).

Composition over EXISTING primitives (NO_DUPLICATE_SYSTEMS): the
local checks themselves come from controller.startup_check.
build_startup_report (emergency stop flag + measurement ledger
chain verification). This module adds only what #8 asks on top:
a machine-readable smoke evidence report and the structural rule
that external synchronization is strictly OPTIONAL: the sync
status is recorded but NEVER gates local readiness, so a network
or GitHub outage can not stop or fail the local smoke run.

Status semantics (UNKNOWN != PASS, NO_DATA_AVAILABLE != PASS):
- SMOKE_PASS      only when every local check is PASS
- SMOKE_UNKNOWN   when nothing failed but a check stayed unprovable
- SMOKE_NOT_READY when any local check FAILED

Ehrliche Grenzen: SMOKE != PRODUCTION; RECORDED != INSTALLED; this
harness performs zero network I/O by construction and proves only
the checked artifacts at run time, not disk, kernel oder supervision.
SYNC != READY-KRITERIUM: sync_status ist ein reines Beobachtungsfeld,
nie Evidenz fuer oder gegen lokale Bereitschaft. Das Modul startet
nichts, installiert nichts und greift auf keine fremden Systeme zu.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.startup_check import (
    NOT_READY,
    READY,
    UNKNOWN,
    StartupCheckError,
    build_startup_report,
)

SCHEMA_VERSION = 1
DEFAULT_SYNC_STATUS = "UNKNOWN"
SYNC_OPTIONAL_STATUSES = ("OK", "UNAVAILABLE", "DEGRADED", "UNKNOWN")

STATUS_PASS = "SMOKE_PASS"
STATUS_UNKNOWN = "SMOKE_UNKNOWN"
STATUS_NOT_READY = "SMOKE_NOT_READY"
EXIT_PASS = 0
EXIT_UNKNOWN = 1
EXIT_NOT_READY = 2

HONEST_LIMITS = [
    "SMOKE != PRODUCTION; ein gruner Smoke-Lauf ist kein Betriebsnachweis.",
    "SYNC != READY-KRITERIUM; der Sync-Status bewertet die lokale Bereitschaft nie.",
    "NO_DATA_AVAILABLE != PASS; fehlende Evidenz bleibt ehrlich sichtbar.",
    "RECORDED != INSTALLED; der Report beschreibt, er repariert nichts.",
]


class OfflineSmokeError(ValueError):
    """Invalid harness arguments or a fail-closed local check error."""


def _validate_sync_status(status: Any) -> str:
    if not isinstance(status, str) or status not in SYNC_OPTIONAL_STATUSES:
        raise OfflineSmokeError(
            f"sync_status must be one of {list(SYNC_OPTIONAL_STATUSES)} "
            f"(fail-closed; sync is an observation, never a pass filter)"
        )
    return status


def _evidence_entries(startup_report: dict) -> list:
    """Map the startup checklist to evidence items (NO copy of checks)."""
    entries = []
    for item in startup_report.get("checklist", []):
        entries.append({
            "check": item.get("name"),
            "status": item.get("status"),
            "reason": item.get("reason"),
            "evidence_reference": "controller.startup_check.build_startup_report",
        })
    return entries


def _canonical_sha256(payload: dict) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_smoke_report(flag_path, ledgers=None, key=None, *,
                       sync_status: str = DEFAULT_SYNC_STATUS,
                       now: datetime | None = None) -> dict:
    """Run the offline local checks and build the smoke evidence report.

    Fail-closed on bad harness arguments or a StartupCheckError; the
    sync status is recorded but can never change the outcome
    (external sync is optional by design, Issue #8).
    """
    sync_status = _validate_sync_status(sync_status)
    try:
        startup_report = build_startup_report(flag_path, ledgers or {}, key=key)
    except StartupCheckError as exc:
        raise OfflineSmokeError(f"local startup check failed closed: {exc}") from exc

    mapped = {READY: STATUS_PASS, UNKNOWN: STATUS_UNKNOWN,
              NOT_READY: STATUS_NOT_READY}
    status = mapped[startup_report["status"]]

    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime):
        raise OfflineSmokeError("now must be a datetime")

    embedded = {
        "startup_status": startup_report["status"],
        "checklist": startup_report["checklist"],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "local_checks": {
            "startup_status": startup_report["status"],
            "evidence": _evidence_entries(startup_report),
            "report_sha256": _canonical_sha256(embedded),
        },
        "external_sync": {
            "status": sync_status,
            "gates_local_readiness": False,
            "note": "optional exchange channel; UNAVAILABLE must not stop "
                    "local checks (Issue #8 architecture boundary 3)",
        },
        "honest_limits": HONEST_LIMITS,
    }


def smoke_exit_code(status: str) -> int:
    if status == STATUS_PASS:
        return EXIT_PASS
    if status == STATUS_UNKNOWN:
        return EXIT_UNKNOWN
    return EXIT_NOT_READY


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m controller.offline_smoke",
        description="Offline V91 smoke run: local checks plus evidence "
                    "report, external sync strictly optional.",
    )
    parser.add_argument("--flag-path", required=True,
                        help="path of the emergency-stop flag file")
    parser.add_argument("--ledger", action="append", default=[],
                        metavar="NAME=PATH",
                        help="measurement ledger to verify (repeatable)")
    parser.add_argument("--sync-status", default=DEFAULT_SYNC_STATUS,
                        help="observed sync state; never gates the outcome")
    args = parser.parse_args(argv)

    ledgers: dict[str, str] = {}
    for item in args.ledger:
        if "=" not in item:
            print(json.dumps({"status": STATUS_NOT_READY,
                              "reason": "ledger arguments must look like "
                                        "NAME=PATH"}))
            return EXIT_NOT_READY
        name, _, path = item.partition("=")
        ledgers[name] = path

    try:
        report = build_smoke_report(
            args.flag_path, ledgers, sync_status=args.sync_status
        )
    except OfflineSmokeError as exc:
        print(json.dumps({"status": STATUS_NOT_READY, "reason": str(exc)}))
        return EXIT_NOT_READY

    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return smoke_exit_code(report["status"])


if __name__ == "__main__":
    raise SystemExit(main())
