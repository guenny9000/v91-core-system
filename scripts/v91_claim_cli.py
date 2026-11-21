#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Fail-closed CLI-Caller fuer das Forum-Claim-Ledger (Taskboard-
Konvention Phase 4, VIBE-XLVI). Verbindet claim_ledger und
author_receipt_guard: keine eigene Regellogik, keine zweite
Wahrheitsquelle. Jeder Append laeuft ausschliesslich ueber
ClaimLedger.append_event (atomar, fail-closed); beim Receipt-Gate gilt
REJECTED != GESPEICHERT (null Byte auf Platte).

Exit-Codes (deterministisch, SCRIPTED != INSTALLED):
- 0 ACCEPTED / status OK
- 1 Nutzungs- oder Eingabefehler (unlesbare Dateien, fehlende Felder)
- 2 REJECTED oder CONFLICT (Guard, Doppel-Claim, unautorisiertes
  EXPIRE, Replay) -> Ledger-Datei bleibt unveraendert
- 3 I/O- oder Integritaetsfehler (corruptes Ledger, Schreibfehler)

Ehrliche Grenzen (bewusst, nicht Luecken):
- SIGNATURE != TRUTH, UNKNOWN != PASS: Ein verifizierter Receipt
  beweist Schluesselherrschaft, nicht die Wahrheit der Angabe.
- Private Keys und Policy kommen aus Caller-Kontext (Dateien), NIEMALS
  aus dem Ledger. Der CLI persistiert keine Schluessel.
- Receipt-Signaturpruefung braucht das Ed25519-Backend; ist es nicht
  verfuegbar, wird jede Receipt-Pruefung REJECTED
  (receipt_backend_unavailable) statt optimistisch durchgewinkt.
- KEIN Daemon: Der CLI ist ein Kommando-Runner; ein zyklischer
  Betrieb mit Taskplaner bleibt separates Betreiber-Thema (nicht
  Teil dieses Wirks).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from controller import author_receipt_guard  # noqa: E402
from controller import claim_ledger  # noqa: E402

EXIT_OK = 0
EXIT_USAGE_OR_INPUT = 1
EXIT_REJECTED_OR_CONFLICT = 2
EXIT_IO_OR_CORRUPT = 3

EVENTS = ("claim", "release", "done", "expire")


def _emit(payload: Dict[str, Any], exit_code: int) -> int:
    sys.stdout.write(json.dumps(payload, sort_keys=True, ensure_ascii=True) + chr(10))
    return exit_code


def _load_json_file(path_str: str, label: str) -> Dict[str, Any]:
    p = Path(path_str)
    if not p.is_file():
        raise ValueError(label + " file not found: " + str(p))
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(label + " JSON must be an object")
    return data


def _load_keyring(path_str: str) -> Tuple[Dict[str, bytes], list]:
    """Liest die Keyring-Datei: {"public_keys": {author: hex64},
    "expire_authorities": [author, ...]}. Fail-closed."""
    data = _load_json_file(path_str, "keyring")
    public_keys_raw = data.get("public_keys")
    if not isinstance(public_keys_raw, dict) or not public_keys_raw:
        raise ValueError("keyring.public_keys must be a non-empty object")
    public_keys: Dict[str, bytes] = {}
    for author, hex_key in public_keys_raw.items():
        if not isinstance(hex_key, str) or len(hex_key) != 64:
            raise ValueError("public key for '" + str(author) + "' must be hex64")
        try:
            public_keys[author] = bytes.fromhex(hex_key)
        except ValueError as exc:
            raise ValueError("public key for '" + str(author) + "' not hex") from exc
    authorities = data.get("expire_authorities", [])
    if not isinstance(authorities, list):
        raise ValueError("keyring.expire_authorities must be a list")
    return public_keys, authorities


def _load_private_key(path_str: str) -> bytes:
    p = Path(path_str)
    if not p.is_file():
        raise ValueError("private key file not found: " + str(p))
    hex_key = p.read_text(encoding="utf-8").strip()
    if len(hex_key) != 64:
        raise ValueError("private key must be hex64 raw bytes")
    try:
        key = bytes.fromhex(hex_key)
    except ValueError as exc:
        raise ValueError("private key not hex") from exc
    return key


def _build_receipt(receipt_data: Dict[str, Any]):
    for field in ("signer_id", "key_id", "signature"):
        value = receipt_data.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError("receipt." + field + " missing or invalid")
    issued = receipt_data.get("issued_at_epoch")
    if not isinstance(issued, int) or isinstance(issued, bool) or issued <= 0:
        raise ValueError("receipt.issued_at_epoch must be a positive int")
    expires = receipt_data.get("expires_at_epoch")
    if expires is not None and not isinstance(expires, int):
        raise ValueError("receipt.expires_at_epoch must be int or null")
    claimed = receipt_data.get("claimed_author")
    if claimed is not None and not isinstance(claimed, str):
        raise ValueError("receipt.claimed_author must be str or null")
    return author_receipt_guard.AuthorReceipt(
        signer_id=receipt_data["signer_id"],
        key_id=receipt_data["key_id"],
        signature=receipt_data["signature"],
        issued_at_epoch=receipt_data["issued_at_epoch"],
        expires_at_epoch=expires,
        claimed_author=claimed,
    )


def _build_policy(policy_data: Dict[str, Any]):
    """Baut die ReceiptPolicy aus JSON. Signaturen werden mit dem
    Ed25519-Backend geprueft; fehlt das Backend: fail-closed."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return "NO_BACKEND"

    trusted_raw = policy_data.get("trusted_keys")
    if not isinstance(trusted_raw, dict) or not trusted_raw:
        raise ValueError("policy.trusted_keys must be a non-empty object")
    trusted: Dict[str, str] = {}
    public_hex: Dict[str, bytes] = {}
    for key_id, entry in trusted_raw.items():
        if not isinstance(entry, dict):
            raise ValueError("policy.trusted_keys." + str(key_id) + " must be an object")
        signer = entry.get("signer")
        pub_hex = entry.get("public_key")
        if not isinstance(signer, str) or not signer or not isinstance(pub_hex, str) or len(pub_hex) != 64:
            raise ValueError("policy.trusted_keys." + str(key_id) + " needs signer and hex64 public_key")
        try:
            public_hex[key_id] = bytes.fromhex(pub_hex)
        except ValueError as exc:
            raise ValueError("policy.trusted_keys." + str(key_id) + " public_key not hex") from exc
        trusted[key_id] = signer

    def verify_fn(payload: str, signature_hex: str, key_id: str) -> bool:
        pub = public_hex.get(key_id)
        if pub is None:
            return False
        try:
            Ed25519PublicKey.from_public_bytes(pub).verify(bytes.fromhex(signature_hex), payload.encode("utf-8"))
            return True
        except Exception:
            return False

    def now_epoch_fn() -> int:
        import time
        return int(time.time())

    return claim_ledger.ReceiptPolicy(
        trusted_keys=trusted,
        verify_signature_fn=verify_fn,
        now_epoch_fn=now_epoch_fn,
        revoked_signers=tuple(policy_data.get("revoked_signers", [])),
        revoked_keys=tuple(policy_data.get("revoked_keys", [])),
        require_verified_receipt=bool(policy_data.get("require_verified_receipt", True)),
    )


def _record(args: argparse.Namespace, event: str):
    expires_at = None
    if event == "CLAIM":
        if args.ttl_seconds is None:
            raise ValueError("--ttl-seconds required for claim")
        if args.ttl_seconds <= 0:
            raise ValueError("--ttl-seconds must be positive")
        expires_at = args.issued_at + args.ttl_seconds
    reason = ""
    if event == "EXPIRE":
        if not args.reason or not args.reason.strip():
            raise ValueError("--reason required for expire")
        reason = args.reason
    try:
        return claim_ledger.build_claim_event(
            event=event,
            author=args.author,
            task_id=args.task_id,
            scope=args.scope,
            sequence=args.sequence,
            issued_at=args.issued_at,
            private_key=args._private_key,
            expected_base_sha=args.base_sha,
            expires_at=expires_at if expires_at is not None else 0,
            reason=reason,
        )
    except claim_ledger.ClaimLedgerError as exc:
        raise ValueError("record rejected: " + str(exc)) from exc


def _cmd_write(args: argparse.Namespace, event: str) -> int:
    receipt = None
    policy = None
    try:
        public_keys, authorities = _load_keyring(args.keyring)
        args._private_key = _load_private_key(args.key)
        if args.receipt:
            receipt = _build_receipt(_load_json_file(args.receipt, "receipt"))
        if args.policy:
            policy = _build_policy(_load_json_file(args.policy, "receipt policy"))
    except ValueError as exc:
        return _emit({"status": "REJECTED", "stage": "input", "reason": str(exc), "written": False}, EXIT_USAGE_OR_INPUT)

    if policy == "NO_BACKEND":
        return _emit(
            {
                "status": "REJECTED",
                "stage": "receipt_backend",
                "reason": "receipt_backend_unavailable",
                "written": False,
            },
            EXIT_USAGE_OR_INPUT,
        )

    try:
        record = _record(args, event)
    except ValueError as exc:
        return _emit({"status": "REJECTED", "stage": "input", "reason": str(exc), "written": False}, EXIT_USAGE_OR_INPUT)

    ledger_path = Path(args.ledger)
    try:
        ledger = claim_ledger.ClaimLedger(ledger_path, public_keys, authorities)
    except claim_ledger.ClaimLedgerError as exc:
        return _emit({"status": "REJECTED", "error_type": type(exc).__name__, "reason": str(exc), "written": False}, EXIT_IO_OR_CORRUPT)

    try:
        entry_hash = ledger.append_event(record, receipt=receipt, receipt_policy=policy)
    except claim_ledger.ReceiptVerificationError as exc:
        return _emit(
            {
                "status": "REJECTED",
                "guard_status": "REJECTED",
                "reason": exc.evaluation.reason,
                "task_id": args.task_id,
                "written": False,
            },
            EXIT_REJECTED_OR_CONFLICT,
        )
    except claim_ledger.ClaimLedgerError as exc:
        return _emit(
            {
                "status": "REJECTED",
                "error_type": type(exc).__name__,
                "reason": str(exc),
                "task_id": args.task_id,
                "written": False,
            },
            EXIT_REJECTED_OR_CONFLICT,
        )

    return _emit(
        {
            "status": "ACCEPTED",
            "event": event,
            "task_id": args.task_id,
            "scope": args.scope,
            "entry_hash": entry_hash,
            "written": True,
        },
        EXIT_OK,
    )


def _cmd_status(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    if not ledger_path.exists():
        return _emit(
            {"status": "UNKNOWN", "reason": "ledger_not_found", "ledger": str(ledger_path), "entry_count": 0},
            EXIT_OK,
        )
    try:
        public_keys, authorities = _load_keyring(args.keyring)
        ledger = claim_ledger.ClaimLedger(ledger_path, public_keys, authorities)
    except (ValueError, claim_ledger.ClaimLedgerError) as exc:
        return _emit(
            {"status": "CORRUPT_OR_INVALID", "error_type": type(exc).__name__, "reason": str(exc)},
            EXIT_IO_OR_CORRUPT,
        )
    events = [
        {"event": rec["event"], "task_id": rec["task_id"], "scope": rec["scope"], "author": rec["author"]}
        for rec in ledger.records()
    ]
    active_claims = {}
    for rec in ledger.records():
        if rec["event"] == "CLAIM":
            active_claims[rec["task_id"]] = rec["author"]
        elif rec["event"] in ("DONE", "RELEASE", "EXPIRE") and rec["task_id"] in active_claims:
            del active_claims[rec["task_id"]]
    return _emit(
        {
            "status": "VERIFIED_CHAIN",
            "ledger": str(ledger_path),
            "entry_count": ledger.entry_count(),
            "active_claims": active_claims,
            "events": events,
        },
        EXIT_OK,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="v91_claim_cli",
        description="Fail-closed CLI for the V91 forum claim ledger.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for cmd_name in EVENTS:
        p = sub.add_parser(cmd_name)
        p.add_argument("--ledger", required=True, help="Path to the JSONL claim ledger")
        p.add_argument("--keyring", required=True, help="Keyring JSON {public_keys, expire_authorities}")
        p.add_argument("--key", required=True, help="File with hex64 private signing key")
        p.add_argument("--author", required=True, help="Author claim identifier")
        p.add_argument("--task-id", required=True, help="Task ID (e.g. VIBE-XLVI)")
        p.add_argument("--scope", required=True, help="Claimed scope")
        p.add_argument("--sequence", required=False, default=1, type=int, help="Per-author sequence number")
        p.add_argument("--issued-at", required=True, type=int, help="Issuing epoch seconds")
        p.add_argument("--base-sha", default="", help="Expected base commit SHA (required for claim)")
        p.add_argument("--ttl-seconds", default=None, type=int, help="Claim TTL (required for claim)")
        p.add_argument("--reason", default=None, help="Mandatory reason for expire")
        p.add_argument("--receipt", default=None, help="Receipt JSON file (optional)")
        p.add_argument("--policy", default=None, help="Receipt policy JSON file (optional)")

    p_status = sub.add_parser("status")
    p_status.add_argument("--ledger", required=True, help="Path to the JSONL claim ledger")
    p_status.add_argument("--keyring", required=True, help="Keyring JSON for verification")
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "status":
        return _cmd_status(args)
    event = args.command.upper()
    if event == "CLAIM" and (not args.base_sha or len(args.base_sha) != 40):
        return _emit({"status": "REJECTED", "stage": "input", "reason": "--base-sha must be a 40-char commit SHA", "written": False}, EXIT_USAGE_OR_INPUT)
    return _cmd_write(args, event)


if __name__ == "__main__":
    raise SystemExit(main())
