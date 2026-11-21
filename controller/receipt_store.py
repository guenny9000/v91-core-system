"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Receipt-Store (MAX-BEST, VIBE-XXXVI; Issue #167 Betriebsteile):
persistenter, append-only Speicher fuer die signierten
Review-Receipt-Umschlaege (VIBE-XXXV) mit Hash-Kette und
Replay-Schutz, analog und in Paarung mit dem QuorumLedger.

Problem: review_receipt verlangt als Caller-Pflicht die Persistenz des
Umschlags (RECEIPTS != LEDGER). Bislang existierte fuer Umschlaege kein
dauerhafter, verifizierender Speicher: jede Auswertung nach Neustart
haette auf unbelegte Umschlags-Listen vertraut. SCRIPTED != INSTALLED;
dieser Store macht die Umschlag-Persistenz installiert und ueberpruefbar.

REUSE / NO_DUPLICATE_SYSTEMS:
  crypto_receipts    kanonische Bytes (Hash-Kette, Signaturfeld)
  review_receipt     Strukturpruefung (receipt_fields_valid),
                     Ed25519-Verifikation (verify_review_receipt),
                     Paarungspruefung (receipt_binds_to_vote)
  quorum_ledger      Persistenz-MUSTER (JSONL, Hash-Kette, fsync,
                     Replay-Floor); bewusst gespiegelt, nicht
                     importiert: Stimmen und Umschlaege bleiben
                     getrennte Dateien, GETRENNT != HIERARCHIE.
  quorum_evaluator   Entscheidung bleibt dort (STORE != BEURTEILUNG)

Regeln (fail-closed):
- append_receipt verlangt IMMER die passende QuorumLedger-Stimme und
  prueft die Bindung erneut (receipt_binds_to_vote): ein Umschlag ohne
  belegte Stimme wird nie gespeichert.
- Laden prueft Hash-Kette, Ed25519-Signatur jedes Umschlags und
  Sequenz-Monotonie je Agent ueber Neustarts hinweg.
- Verstoss gegen irgendeine Pruefung: komplette Operation verweigert
  bzw. komplettes Laden abgebrochen. UNKNOWN != PASS.

Honest limits:
- Append-only mit Hash-Kette ist Manipulationserkennung, KEIN
  WORM-Speicher (Identisch zum QuorumLedger: wer die Datei ersetzen
  kann, kann sie neu schreiben).
- STORE != BEURTEILUNG: der Store persistiert und prueft Belege,
  entscheidet aber nichts.
- BINDING != LEDGER-NACHWEIS: der Store beweist die kryptografische
  Bindung des Umschlags an die Stimme, aber NICHT, dass die Stimme
  selbst je im QuorumLedger lag.
- Oeffentliche Schluessel muessen aus unabhaengig vertrauenswuerdigem
  Kontext stammen, NIEMALS aus dem Store selbst.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

from controller.crypto_receipts import canonical_record_bytes
from controller.review_receipt import (
    receipt_binds_to_vote,
    receipt_fields_valid,
    verify_review_receipt,
)

GENESIS = "GENESIS"


class ReceiptStoreError(Exception):
    """Fail-closed Fehler des Receipt-Store."""


class ReceiptStore:
    """
    Persistenter append-only Speicher fuer signierte
    Review-Receipt-Umschlaege: JSONL, Hash-Kette ueber Eintraege,
    Ed25519-Pflicht je Umschlag, Replay-Floor je Agent
    (Sequenz strikt monoton, ueber Neustarts).
    """

    def __init__(self, path: Path, public_keys: Mapping[str, bytes]):
        if not isinstance(path, Path):
            raise ReceiptStoreError("path must be a Path")
        if not isinstance(public_keys, Mapping) or not public_keys:
            raise ReceiptStoreError("public_keys must be a non-empty mapping")
        for agent_id, key in public_keys.items():
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ReceiptStoreError("agent id must be non-empty")
            if not isinstance(key, bytes) or len(key) != 32:
                raise ReceiptStoreError("public key must be raw 32 bytes")
        self._path = path
        self._keys = dict(public_keys)
        self._floors: Dict[str, int] = {}
        self._prev_hash = GENESIS
        self._entries = 0
        self._records: List[Dict] = []
        if path.exists():
            self._load_and_verify()

    def _entry_hash(self, prev: str, entry_record: Dict) -> str:
        payload = {"prev": prev, "entry": entry_record}
        return hashlib.sha256(canonical_record_bytes(payload)).hexdigest()

    def _load_and_verify(self) -> None:
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = fh.read()
        if raw and not raw.endswith("\n"):
            raise ReceiptStoreError("truncated last line; fail closed")
        lines = raw.split("\n")[:-1] if raw else []
        for line in lines:
            if not line.strip():
                raise ReceiptStoreError("blank line in store; fail closed")
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReceiptStoreError("malformed JSON line; fail closed") from exc
            if not isinstance(entry, dict):
                raise ReceiptStoreError("store entry must be an object")
            if set(entry) != {"prev", "entry", "entry_hash"}:
                raise ReceiptStoreError("store entry schema violated")
            if entry["prev"] != self._prev_hash:
                raise ReceiptStoreError("hash chain broken; fail closed")
            expected = self._entry_hash(entry["prev"], entry["entry"])
            if entry["entry_hash"] != expected:
                raise ReceiptStoreError("entry hash mismatch; fail closed")
            record = entry["entry"]
            agent_id = record.get("agent_id") if isinstance(record, dict) else None
            public_key = self._keys.get(agent_id)
            if public_key is None:
                raise ReceiptStoreError("unknown agent in store; fail closed")
            if not verify_review_receipt(record, public_key):
                raise ReceiptStoreError("receipt signature invalid; fail closed")
            sequence = record["sequence"]
            if sequence <= self._floors.get(agent_id, 0):
                raise ReceiptStoreError("replay/sequence violation in store; fail closed")
            self._floors[agent_id] = sequence
            self._prev_hash = entry["entry_hash"]
            self._entries += 1
            self._records.append(dict(record))

    def replay_floor(self, agent_id: str) -> int:
        """Aktueller Sequenz-Floor (Persistenz ueber Neustarts)."""
        return self._floors.get(agent_id, 0)

    def entry_count(self) -> int:
        return self._entries

    def head_hash(self) -> str:
        return self._prev_hash

    def records(self) -> Tuple:
        """Verifizierte Umschlaege als Kopien, in Anhaengereihenfolge."""
        return tuple(dict(record) for record in self._records)

    def append_receipt(self, receipt: Mapping, vote_record: Mapping) -> str:
        """Haengt einen verifizierten, an die Stimme gebundenen Umschlag an.

        Fail-closed: die zugehoerige QuorumLedger-Stimme ist PFLICHT und
        die Bindung wird hier erneut geprueft (BINDING != BEHAUPTET):
        RECEIPT_OHNE_STIMME != GESPEICHERT.
        """
        if not isinstance(receipt, Mapping) or not receipt_fields_valid(receipt):
            raise ReceiptStoreError("receipt invalid; fail closed")
        if not isinstance(vote_record, Mapping):
            raise ReceiptStoreError("vote record must be a mapping; fail closed")
        agent_id = receipt["agent_id"]
        public_key = self._keys.get(agent_id)
        if public_key is None:
            raise ReceiptStoreError("unknown agent; fail closed")
        if not verify_review_receipt(receipt, public_key):
            raise ReceiptStoreError("receipt signature verification failed; fail closed")
        if not receipt_binds_to_vote(receipt, vote_record):
            raise ReceiptStoreError("receipt does not bind to vote; fail closed")
        sequence = receipt["sequence"]
        if sequence <= self._floors.get(agent_id, 0):
            raise ReceiptStoreError("replay or stale sequence refused; fail closed")
        record = dict(receipt)
        entry_hash = self._entry_hash(self._prev_hash, record)
        entry = {"prev": self._prev_hash, "entry": record, "entry_hash": entry_hash}
        line = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        self._floors[agent_id] = sequence
        self._prev_hash = entry_hash
        self._entries += 1
        self._records.append(record)
        return entry_hash
