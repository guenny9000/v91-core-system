#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: SchÃ¶pfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Offline startup self-check for the local-first resilience core
(Issue #8, Stage 1).

Composition of EXISTING primitives, no second copy of any check
(NO_DUPLICATE_SYSTEMS):
- emergency stop flag via controller.emergency_stop.check_flag
  (fail-closed: unreadable or foreign-shaped flag counts as STOPPED)
- measurement ledger integrity via controller.measurement_store
  .MeasurementStore.verify_chain (corrupt chain = FAIL, no key =
  UNKNOWN, never claimed intact without evidence)

Status semantics (UNKNOWN != PASS):
- READY    only when every critical check is PASS
- UNKNOWN  when nothing failed but a check stayed unprovable
           (e.g. fresh head without ledger, or no store key)
- NOT_READY when any check FAILED (including a tripped or
           fail-closed unreadable emergency stop)

Honest limits:
- SCRIPTED != INSTALLED: this is a check program, not a daemon and
  not the runtime entry point; wiring into boot is a separate,
  explicitly reviewed step.
- REPORT != REPAIR: a READY report proves the checked artifacts,
  not disk health, kernel state or process supervision.
- LOCAL ONLY: no network, no GitHub, no clock trust, no secrets on
  the command line (the store key comes from the environment exactly
  as MeasurementStore.resolve_key defines).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from controller.emergency_stop import check_flag
from controller.measurement_store import (
    STORE_KEY_ENV,
    MeasurementStore,
    MeasurementStoreError,
)

READY = "READY"
UNKNOWN = "UNKNOWN"
NOT_READY = "NOT_READY"
PASS = "PASS"
FAIL = "FAIL"

EXIT_READY = 0
EXIT_UNKNOWN = 1
EXIT_NOT_READY = 2


class StartupCheckError(ValueError):
    """Invalid arguments or an unusable check target (fail-closed)."""


def _entry(name: str, status: str, reason: str) -> dict:
    return {"name": name, "status": status, "reason": reason}


def build_startup_report(flag_path, ledgers, key=None) -> dict:
    """Evaluate the local core offline and return a status report.

    flag_path: path of the emergency-stop flag (required).
    ledgers: mapping of non-empty unique names to ledger file paths.
    key: store key for chain verification; None means UNKNOWN, never
    a guessed key.
    """
    if not isinstance(flag_path, (str, os.PathLike)) or not str(flag_path).strip():
        raise StartupCheckError("flag_path is required (fail-closed)")
    if key is not None:
        if not isinstance(key, (bytes, bytearray)) or len(key) < 32:
            raise StartupCheckError("store key must be bytes of at least 32 length")
        key = bytes(key)
    if not isinstance(ledgers, dict) or not ledgers:
        ledgers = {}
    seen_names: set[str] = set()
    for name, path in ledgers.items():
        if not isinstance(name, str) or not name.strip():
            raise StartupCheckError("ledger names must be non-empty strings")
        if name in seen_names:
            raise StartupCheckError(f"duplicate ledger name: {name!r}")
        seen_names.add(name)
        if not isinstance(path, (str, os.PathLike)) or not str(path).strip():
            raise StartupCheckError(f"ledger path for {name!r} is required")

    entries: list[dict] = []

    stopped, reason = check_flag(flag_path)
    if stopped:
        entries.append(_entry("emergency_stop", FAIL, reason))
    else:
        entries.append(_entry("emergency_stop", PASS, reason))

    for name in sorted(ledgers):
        path = Path(ledgers[name])
        entry_name = f"ledger:{name}"
        if not path.exists():
            entries.append(_entry(
                entry_name, UNKNOWN,
                "ledger file missing (fresh head or wrong path; NOT claimed intact)",
            ))
            continue
        if key is None:
            entries.append(_entry(
                entry_name, UNKNOWN,
                "no store key provided (V91_MEASUREMENT_STORE_KEY); "
                "chain NOT claimed intact without evidence",
            ))
            continue
        try:
            store = MeasurementStore(path, key=key)
            intact = store.verify_chain()
        except MeasurementStoreError as exc:
            entries.append(_entry(entry_name, FAIL, f"store unusable: {exc}"))
            continue
        except OSError as exc:
            entries.append(_entry(entry_name, FAIL, f"unreadable ledger: {exc}"))
            continue
        if not intact:
            entries.append(_entry(entry_name, FAIL, "chain verification failed"))
        else:
            entries.append(_entry(entry_name, PASS, "chain verified end to end"))

    statuses = {e["status"] for e in entries}
    if FAIL in statuses:
        overall = NOT_READY
    elif UNKNOWN in statuses:
        overall = UNKNOWN
    else:
        overall = READY
    return {"status": overall, "checklist": entries}


def _ledger_argument(value: str) -> dict:
    if "=" not in value:
        raise StartupCheckError("ledger arguments must look like NAME=PATH")
    name, _, path = value.partition("=")
    return {name: path}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m controller.startup_check",
        description="Offline V91 startup self-check (report, no daemon).",
    )
    parser.add_argument("--flag-path", required=True,
                        help="path of the emergency-stop flag file")
    parser.add_argument("--ledger", action="append", default=[],
                        metavar="NAME=PATH",
                        help="measurement ledger to verify (repeatable)")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        default=True,
                        help="print the report as JSON (default)")
    args = parser.parse_args(argv)

    ledgers: dict[str, str] = {}
    try:
        for item in args.ledger:
            ledgers.update(_ledger_argument(item))
    except StartupCheckError as exc:
        print(json.dumps(
            {"status": NOT_READY, "checklist": [], "reason": str(exc)}))
        return EXIT_NOT_READY

    env_value = os.environ.get(STORE_KEY_ENV, "")
    key = None
    if len(env_value.encode("utf-8")) >= 32:
        key = env_value.encode("utf-8")

    try:
        report = build_startup_report(args.flag_path, ledgers, key=key)
    except StartupCheckError as exc:
        print(json.dumps(
            {"status": NOT_READY, "checklist": [], "reason": str(exc)},
            file=sys.stdout)
        return EXIT_NOT_READY

    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] == READY:
        return EXIT_READY
    if report["status"] == NOT_READY:
        return EXIT_NOT_READY
    return EXIT_USÓÕÓY×Û[YW×ÈOH×ÛXZ[×ÈÈYÛXNÈÛÝ\Z\ÙHÞ\Ý[Q^]
XZ[
JB