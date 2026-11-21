#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Fail-closed Watchdog fuer das Forum-Claim-Ledger (Taskboard-Konvention
Phase 5, VIBE-XLVII). Erkennt zeitlich abgelaufene aktive Claims
(expires_at <= now) und macht sie NUR auf explizite Anforderung per
regelkonformem EXPIRE-Ereignis wieder frei. Keine eigene Regellogik,
keine zweite Wahrheitsquelle: jeder EXPIRE laeuft ausschliesslich ueber
ClaimLedger.append_event (atomar, fail-closed); beim Receipt-Gate gilt
REJECTED != GESPEICHERT (null Byte auf Platte).

DRY-RUN != APPLY: Der Standardmodus ist scan (nur Report, garantiert
null Byte auf Platte). Schreibend ist nur der Modus expire mit
Operator-Identitaet, Signier-Key und Pflichtbegruendung.

Exit-Codes (deterministisch, WATCHDOG != DAEMON, SCRIPTED != INSTALLED):
- 0 scan/expire OK (auch mit leerer Trefferliste)
- 1 Nutzungs- oder Eingabefehler (unlesbare Dateien, fehlende Felder)
- 2 REJECTED oder CONFLICT (unautorisiertes EXPIRE, Replay, Guard)
- 3 I/O- oder Integritaetsfehler (corruptes Ledger, Schreibfehler)

Ehrliche Grenzen (bewusst, nicht Luecken):
- SIGNATURE != TRUTH, UNKNOWN != PASS: Ein verifiziertes Ereignis
  beweist Schluesselherrschaft, nicht die Wahrheit der Angabe.
- KEIN Daemon: Dieses Skript ist ein Einmal-Runner; ein zyklischer
  Betrieb mit Taskplaner bleibt separates Betreiber-Thema (nicht
  Teil dieses Wirks). INSTALLIERT != SKRIPTIERT.
- Zeitquelle ist time.time() (oder --now fuer reproduzierbare
  Laeufe); eine manipulierte Systemuhr macht EXPIRE frueher oder
  spaeter moeglich, aber nie ohne autorisierte Operator-Signatur.
- Abgelaufene aber NICHT expired Claims bleiben Konflikt-gebunden
  (fail-closed gegen Doppel-Claim); der Watchdog ist der einzige
  regelkonforme Weg, sie freizugeben, und nur im Modus expire.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from controller import claim_ledger  # noqa: E402
from scripts import v91_claim_cli  # noqa: E402

EXIT_OK = 0
EXIT_USAGE_OR_INPUT = 1
EXIT_REJECTED_OR_CONFLICT = 2
EXIT_IO_OR_CORRUPT = 3

MODE_SCAN = "scan"
MODE_EXPIRE = "expire"


def _emit(payload: Dict[str, Any], exit_code: int) -> int:
    sys.stdout.write(json.dumps(payload, sort_keys=True, ensure_ascii=True) + chr(10))
    return exit_code


def _now_epoch(args: argparse.Namespace) -> int:
    if args.now is not None:
        if args.now <= 0:
            raise ValueError("--now must be a positive epoch")
        return args.now
    return int(time.time())


def _active_claims(ledger: claim_ledger.ClaimLedger) -> List[Dict[str, Any]]:
    """Aktive Claims aus den verifizierten Ereignissen ableiten
    (gleiche Ableitung wie v91_claim_cli status; keine zweite
    Regelquelle: ein Claim gilt als aktiv, bis DONE/RELEASE/EXPIRE
    folgt)."""
    active: Dict[str, Dict[str, Any]] = {}
    for rec in ledger.records():
        event = rec["event"]
        if event == "CLAIM":
            active[rec["task_id"]] = dict(rec)
        elif event in ("DONE", "RELEASE", "EXPIRE"):
            active.pop(rec["task_id"], None)
    return list(active.values())


def _expired(active: List[Dict[str, Any]], now: int) -> List[Dict[str, Any]]:
    expired = [c for c in active if c.get("expires_at", 0) <= now]
    expired.sort(key=lambda c: (c["expires_at"], c["task_id"]))
    return expired


def _claim_view(claim: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_id": claim["task_id"],
        "scope": claim["scope"],
        "author": claim["author"],
        "issued_at": claim["issued_at"],
        "expires_at": claim["expires_at"],
    }


def _open_ledger(args: argparse.Namespace):
    ledger_path = Path(args.ledger)
    if not ledger_path.exists():
        return None, "ledger_not_found"
    public_keys, authorities = v91_claim_cli._load_keyring(args.keyring)
    ledger = claim_ledger.ClaimLedger(ledger_path, public_keys, authorities)
    return ledger, None


def _cmd_scan(args: argparse.Namespace) -> int:
    try:
        now = _now_epoch(args)
        ledger, reason = _open_ledger(args)
        if reason == "ledger_not_found":
            return _emit(
                {"status": "UNKNOWN", "reason": reason, "ledger": str(Path(args.ledger)), "expired_claims": [], "written": False},
                EXIT_OK,
            )
        expired = _expired(_active_claims(ledger), now)
        return _emit(
            {
                "status": "SCANNED",
                "mode": MODE_SCAN,
                "now_epoch": now,
                "ledger": str(Path(args.ledger)),
                "entry_count": ledger.entry_count(),
                "expired_claims": [_claim_view(c) for c in expired],
                "written": False,
            },
            EXIT_OK,
        )
    except ValueError as exc:
        return _emit({"status": "REJECTED", "stage": "input", "reason": str(exc), "written": False}, EXIT_USAGE_OR_INPUT)
    except claim_ledger.ClaimLedgerError as exc:
        return _emit({"status": "CORRUPT_OR_INVALID", "error_type": type(exc).__name__, "reason": str(exc), "written": False}, EXIT_IO_OR_CORRUPT)


def _cmd_expire(args: argparse.Namespace) -> int:
    if not args.reason or not args.reason.strip():
        return _emit({"status": "REJECTED", "stage": "input", "reason": "--reason required for expire", "written": False}, EXIT_USAGE_OR_INPUT)
    try:
        now = _now_epoch(args)
        private_key = v91_claim_cli._load_private_key(args.key)
        receipt = None
        policy = None
        if args.receipt:
            receipt = v91_claim_cli._build_receipt(v91_claim_cli._load_json_file(args.receipt, "receipt"))
        if args.policy:
            policy = v91_claim_cli._build_policy(v91_claim_cli._load_json_file(args.policy, "receipt policy"))
    except ValueError as exc:
        return _emit({"status": "REJECTED", "stage": "input", "reason": str(exc), "written": False}, EXIT_USAGE_OR_INPUT)

    if policy == "NO_BACKEND":
        return _emit({"status": "REJECTED", "stage": "receipt_backend", "reason": "receipt_backend_unavailable", "written": False}, EXIT_USAGE_OR_INPUT)

    try:
        ledger, reason = _open_ledger(args)
    except (ValueError, claim_ledger.ClaimLedgerError) as exc:
        if isinstance(exc, ValueError):
            return _emit({"status": "REJECTED", "stage": "input", "reason": str(exc), "written": False}, EXIT_USAGE_OR_INPUT)
        return _emit({"status": "CORRUPT_OR_INVALID", "error_type": type(exc).__name__, "reason": str(exc), "written": False}, EXIT_IO_OR_CORRUPT)
    if reason == "ledger_not_found":
        return _emit({"status": "UNKNOWN", "reason": reason, "ledger": str(Path(args.ledger)), "expired_claims": [], "written": False}, EXIT_OK)

    try:
        active = _active_claims(ledger)
        expired = _expired(active, now)
        if not expired:
            return _emit(
                {"status": "NOTHING_TO_EXPIRE", "mode": MODE_EXPIRE, "now_epoch": now, "expired_claims": [], "written": False},
                EXIT_OK,
            )
        results = []
        for claim in expired:
            task_id = claim["task_id"]
            sequence = ledger.replay_floor(args.author) + 1
            record = claim_ledger.build_claim_event(
                event=claim_ledger.EVENT_EXPIRE,
                author=args.author,
                task_id=task_id,
                scope=claim["scope"],
                sequence=sequence,
                issued_at=now,
                private_key=private_key,
                reason=args.reason,
            )
            entry_hash = ledger.append_event(record, receipt=receipt, receipt_policy=policy)
            results.append({"task_id": task_id, "entry_hash": entry_hash})
        return _emit(
            {
                "status": "APPLIED",
                "mode": MODE_EXPIRE,
                "now_epoch": now,
                "expired_claims": [_claim_view(c) for c in expired],
                "expired_events": results,
                "written": True,
            },
            EXIT_OK,
        )
    except (ValueError, claim_ledger.ClaimLedgerError) as exc:
        # REJECTED != GESPEICHERT: append_event schreibt atomar pro
        # Ereignis; ein Fehlschlag haelt bereits garantierte Ereignisse
        # nicht zurueck, schreibt aber KEIN ungueltiges mehr.
        return _emit(
            {
                "status": "REJECTED",
                "error_type": type(exc).__name__,
                "reason": str(exc),
                "now_epoch": now,
            },
            EXIT_REJECTED_OR_CONFLICT,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="v91_watchdog",
        description="Fail-closed watchdog for the V91 forum claim ledger (scan/expire).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser(MODE_SCAN, help="Report expired claims; never writes (DRY-RUN != APPLY)")
    p_scan.add_argument("--ledger", required=True)
    p_scan.add_argument("--keyring", required=True)
    p_scan.add_argument("--now", default=None, type=int, help="Deterministic now epoch (default: system time)")

    p_exp = sub.add_parser(MODE_EXPIRE, help="Expire all due claims via ledger EXPIRE events")
    p_exp.add_argument("--ledger", required=True)
    p_exp.add_argument("--keyring", required=True)
    p_exp.add_argument("--key", required=True, help="File with hex64 operator signing key")
    p_exp.add_argument("--author", required=True, help="Operator identity (must be an expire authority)")
    p_exp.add_argument("--reason", required=True, help="Mandatory reason recorded in every EXPIRE event")
    p_exp.add_argument("--now", default=None, type=int, help="Deterministic now epoch (default: system time)")
    p_exp.add_argument("--receipt", default=None, help="Receipt JSON file (optional)")
    p_exp.add_argument("--policy", default=None, help="Receipt policy JSON file (optional)")
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == MODE_SCAN:
        return _cmd_scan(args)
    return _cmd_expire(args)


if __name__ == "__main__":
    raise SystemExit(main())
