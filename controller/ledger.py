#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Append-only hash-chain ledger (JSON Lines).

Tamper-EVIDENT, not tamper-proof: anyone with write access to the file can
rewrite the whole chain. Use an external anchor (e.g. publish the head hash)
for stronger guarantees.

Concurrency contract (since the 25.11.2026 hardening): append runs under
the INTERPROCESS exclusive_ledger_lock (controller/ledger_lock.py) and
re-reads seq/head from the file inside the critical section, so separate
processes cannot append with a stale head. Single-machine only; the ledger
lock builds no distributed guarantee (LOCK != BEWEIS, verify_chain bleibt
Massstab).
"""

import hashlib
import hmac
import json
import os
import threading
from pathlib import Path
from typing import Any

try:
    from controller.ledger_lock import exclusive_ledger_lock
except ImportError:  # direkter Start aus controller/ (flat-Pfad)
    from ledger_lock import exclusive_ledger_lock

GENESIS = "0" * 64


def compute_hash(prev_hash: str, seq: int, timestamp: str, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{prev_hash}|{seq}|{timestamp}|{body}".encode()).hexdigest()


def verify_chain(path: str) -> dict[str, Any]:
    """Re-verify every entry. Returns a report; never raises on corrupt data."""
    report: dict[str, Any] = {"records_checked": 0, "chain_valid": True, "errors": []}
    if not os.path.exists(path):
        return report
    prev = GENESIS
    with open(path, encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            report["records_checked"] += 1
            try:
                rec = json.loads(line)
                expected_seq = report["records_checked"] - 1
                if rec["seq"] != expected_seq:
                    report["errors"].append(f"line {line_no}: SEQ_MISMATCH")
                if not hmac.compare_digest(str(rec["prev_hash"]), prev):
                    report["errors"].append(f"line {line_no}: CHAIN_BROKEN")
                calc = compute_hash(rec["prev_hash"], rec["seq"], rec["timestamp"], rec["payload"])
                if not hmac.compare_digest(str(rec["hash"]), calc):
                    report["errors"].append(f"line {line_no}: HASH_MISMATCH")
                prev = rec["hash"]
            except (ValueError, KeyError, TypeError):
                report["errors"].append(f"line {line_no}: MALFORMED")
                break
    report["chain_valid"] = not report["errors"]
    return report


class HashChainLedger:
    """Thread-safe append-only ledger; verifies the existing chain on open."""

    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
        self._lock = threading.Lock()
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        report = verify_chain(self.path)
        if not report["chain_valid"]:
            raise ValueError(f"ledger integrity violation: {report['errors'][:3]}")
        self._seq = report["records_checked"]
        self._head = self._read_head()

    def _read_head(self) -> str:
        head = GENESIS
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        head = json.loads(line)["hash"]
        return head

    def _read_state(self) -> tuple[int, str]:
        """seq und head NEU von der Datei lesen (fuer den kritischen
        Abschnitt unter Interprozess-Lock). Der In-Memory-Zustand
        gilt erst wieder NACH dem Abgleich (EXTERNE APPENDS MOEGLICH).

        Fremdbefund-Nachmessung 25.11.2026 (externes Review, P0):
        threading.Lock schuetzt nur EINEN Prozess; der vorhandene
        Baustein controller/ledger_lock.py (aus PR #517/#529) wurde
        vom HashChainLedger bisher NICHT verwendet. Zwei Prozesse
        mit separat geladenem Kopf haetten mit veraltetem prev_hash
        geschrieben. LOCK != BEWEIS: Verifikation bleibt Massstab.
        """
        seq = 0
        head = GENESIS
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        head = json.loads(line)["hash"]
                        seq += 1
        return seq, head

    @property
    def head(self) -> str:
        return self._head

    def append(self, payload: dict[str, Any], timestamp: str) -> dict[str, Any]:
        with self._lock:
            with exclusive_ledger_lock(Path(self.path)):
                # Kritischer Abschnitt: Neuabgleich + append gehoeren
                # zusammen (Vertrag aus controller/ledger_lock.py).
                self._seq, self._head = self._read_state()
                digest = compute_hash(self._head, self._seq, timestamp, payload)
                record = {
                    "seq": self._seq,
                    "timestamp": timestamp,
                    "prev_hash": self._head,
                    "payload": payload,
                    "hash": digest,
                }
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                self._seq += 1
                self._head = digest
                return record
