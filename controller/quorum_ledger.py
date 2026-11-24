"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Quorum-Ledger: dauerhaft gespeicherte, Ed25519-signierte
Abstimmungsbelege (Votes) der Agenten-Quorum-Orchestrierung mit
Hash-Kette und persistentem Replay-Schutz (Sequenz-Floor je Agent).

Ehrliche Grenzen (bewusst, nicht Luecken):
- Ed25519 beweist die Urheberschaft einer Stimme, NICHT die Wahrheit
  ihrer Bewertung. Schluesselverwaltung bleibt beim Caller; private
  Schluessel muessen unabhaengig je Agent verwaltet werden.
- Die oeffentlichen Pruefschluessel muessen aus unabhaengig
  vertrauenswuerdigem Kontext stammen, NIEMALS aus dem Ledger selbst.
- Die Zeitquelle (issued_at) ist Caller-vertraut; dieses Modul erzwingt
  keine Netzwerkfristen (Adapter-Verantwortung, siehe agent_quorum.py).
- Append-only mit Hash-Kette ist Manipulationserkennung, KEIN
  WORM-Speicher; wer die Datei ersetzen kann, kann sie auch neu
  schreiben. BELEGT != VERIFIZIERT; LEDGER != BEURTEILUNG.
- Der bestehende HMAC-Konsens (agent_consensus) bleibt getrennt
  vorhanden und wird NICHT als gleichwertiger Ersatz fuer
  asymmetrische Agentensignaturen behandelt.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

from controller.crypto_receipts import (
    SIGNATURE_FIELD,
    canonical_record_bytes,
    sign_record,
    verify_record_signature,
)
from controller.ledger_lock import exclusive_ledger_lock

RECORD_TYPE_VOTE = "quorum_vote"
SIGNATURE_ALGORITHM = "ED25519"
GENESIS = "GENESIS"


class QuorumLedgerError(Exception):
    """Fail-closed Fehler des Quorum-Ledgers."""


def _is_int(value: Any) -> bool:
    return type(value) is int


def _is_hex64(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(c in "0123456789abcdef" for c in value)


def vote_fields_valid(record: Any) -> bool:
    """Strukturelle Pruefung eines Vote-Records (ohne Signaturbeweis)."""
    if not isinstance(record, dict):
        return False
    if record.get("record_type") != RECORD_TYPE_VOTE:
        return False
    if record.get("signature_algorithm") != SIGNATURE_ALGORITHM:
        return False
    if not isinstance(record.get("agent_id"), str) or not record["agent_id"].strip():
        return False
    if not _is_hex64(record.get("proposal_digest")):
        return False
    if not _is_int(record.get("epoch")) or record["epoch"] < 0:
        return False
    if not _is_int(record.get("sequence")) or record["sequence"] < 1:
        return False
    if type(record.get("approve")) is not bool:
        return False
    if not _is_int(record.get("issued_at")):
        return False
    if not isinstance(record.get("policy_version"), str) or not record["policy_version"].strip():
        return False
    return True


def build_signed_vote(
    agent_id: str,
    proposal_digest: str,
    epoch: int,
    sequence: int,
    approve: bool,
    issued_at: int,
    policy_version: str,
    private_key: bytes,
) -> Dict:
    """Erzeugt einen Ed25519-signierten Abstimmungsbeleg (fail-closed)."""
    record: Dict = {
        "record_type": RECORD_TYPE_VOTE,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "agent_id": agent_id,
        "proposal_digest": proposal_digest,
        "epoch": epoch,
        "sequence": sequence,
        "approve": approve,
        "issued_at": issued_at,
        "policy_version": policy_version,
    }
    if not vote_fields_valid(record):
        raise QuorumLedgerError("vote fields invalid; fail closed")
    record[SIGNATURE_FIELD] = sign_record(record, private_key)
    return record


def verify_signed_vote(record: Any, public_key: bytes) -> bool:
    """Struktur + Ed25519-Signatur; jede Rueckgabe ausser True ist Nein."""
    if not vote_fields_valid(record):
        return False
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        return False
    return verify_record_signature(record, public_key)


class QuorumLedger:
    """
    Persistenter Abstimmungsbeleg-Speicher: append-only JSONL,
    Hash-Kette ueber Eintraege, Ed25519-Pflicht fuer jede Stimme,
    Replay-Floor je Agent (Sequenz strikt monoton, ueber Neustarts).
    """

    def __init__(self, path: Path, public_keys: Mapping[str, bytes]):
        if not isinstance(path, Path):
            raise QuorumLedgerError("path must be a Path")
        if not isinstance(public_keys, Mapping) or not public_keys:
            raise QuorumLedgerError("public_keys must be a non-empty mapping")
        for agent_id, key in public_keys.items():
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise QuorumLedgerError("agent id must be non-empty")
            if not isinstance(key, bytes) or len(key) != 32:
                raise QuorumLedgerError("public key must be raw 32 bytes")
        self._path = path
        self._keys = dict(public_keys)
        self._floors: Dict[str, int] = {}
        self._prev_hash = GENESIS
        self._entries = 0
        self._records: list = []
        if path.exists():
            self._load_and_verify()

    def _entry_hash(self, prev: str, entry_record: Dict) -> str:
        payload = {"prev": prev, "entry": entry_record}
        return hashlib.sha256(canonical_record_bytes(payload)).hexdigest()

    def _load_and_verify(self) -> None:
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = fh.read()
        if raw and not raw.endswith("\n"):
            raise QuorumLedgerError("truncated last line; fail closed")
        lines = raw.split("\n")[:-1] if raw else []
        for line in lines:
            if not line.strip():
                raise QuorumLedgerError("blank line in ledger; fail closed")
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise QuorumLedgerError("malformed JSON line; fail closed") from exc
            if not isinstance(entry, dict):
                raise QuorumLedgerError("ledger entry must be an object")
            if set(entry) != {"prev", "entry", "entry_hash"}:
                raise QuorumLedgerError("ledger entry schema violated")
            if entry["prev"] != self._prev_hash:
                raise QuorumLedgerError("hash chain broken; fail closed")
            expected = self._entry_hash(entry["prev"], entry["entry"])
            if entry["entry_hash"] != expected:
                raise QuorumLedgerError("entry hash mismatch; fail closed")
            record = entry["entry"]
            agent_id = record.get("agent_id") if isinstance(record, dict) else None
            public_key = self._keys.get(agent_id)
            if public_key is None:
                raise QuorumLedgerError("unknown agent in ledger; fail closed")
            if not verify_signed_vote(record, public_key):
                raise QuorumLedgerError("vote signature invalid; fail closed")
            sequence = record["sequence"]
            if sequence <= self._floors.get(agent_id, 0):
                raise QuorumLedgerError("replay/sequence violation in ledger; fail closed")
            self._floors[agent_id] = sequence
            self._prev_hash = entry["entry_hash"]
            self._entries += 1
            self._records.append(dict(record))

    def _reset_state(self) -> None:
        """ZustandsZuruecksetzung fuer den Neuabgleich gegen die Datei."""
        self._floors = {}
        self._prev_hash = GENESIS
        self._entries = 0
        self._records = []

    def _sync_from_disk_locked(self) -> None:
        """Erneuert den Kettenzustand aus der Datei (im kritischen Abschnitt).

        Fail-closed: eine geschrumpfte oder verschwundene Datei mit
        bereits geladenem Zustand verweigert den Append (kein stiller
        Reset). Fremde Eintraege (anderer Prozess/Instanz) werden
        durch vollstaendiges Neu-Verifizieren uebernommen.
        """
        if self._entries and not self._path.exists():
            raise QuorumLedgerError("ledger file vanished while state loaded; fail closed")
        if not self._path.exists():
            return
        raw = self._path.read_text(encoding="utf-8")
        lines = [ln for ln in raw.split("\n") if ln.strip()] if raw else []
        if len(lines) < self._entries:
            raise QuorumLedgerError("ledger shrank below known entries; fail closed")
        if len(lines) == self._entries:
            return  # im Zustand, niemand hat zwischenzeitlich geschrieben
        self._reset_state()
        self._load_and_verify()

    def replay_floor(self, agent_id: str) -> int:
        """ Aktueller Sequenz-Floor (Persistenz ueber Neustarts)."""
        return self._floors.get(agent_id, 0)

    def entry_count(self) -> int:
        return self._entries

    def records(self) -> Tuple:
        """Verifizierte Vote-Belege als Kopien, in Anhaengereihenfolge.

        Nur Belege, deren Hash-Kette, Signatur und Sequenzmonotonie beim
        Laden oder Anhaengen geprueft wurden. Auswertung (Implementierung
        in quorum_decision.py) ist hier bewusst NICHT enthalten:
        LEDGER != BEURTEILUNG.
        """
        return tuple(dict(record) for record in self._records)

    def append_vote(self, record: Dict) -> str:
        """Haengt einen validierten, signierten Vote an; gibt entry_hash zurueck.

        Kritischer Abschnitt (Ledger-Lock, siehe controller/ledger_lock.py):
        Neuabgleich gegen die Datei UND append gehoeren zusammen. Der
        Replay-Floor wird NACH dem Neuabgleich erneut geprueft, damit
        eine zwischenzeitliche fremde Aufnahme KEIN Duplikat durchlaesst
        (UNKNOWN != PASS, auch unter Parallelitaet). LOCK != BEWEIS: der
        Lock verhindert Interleaving; die Verifikation bleibt Massstab.
        """
        agent_id = record.get("agent_id") if isinstance(record, dict) else None
        public_key = self._keys.get(agent_id)
        if public_key is None or not verify_signed_vote(record, public_key):
            raise QuorumLedgerError("unverified or unknown vote refused; fail closed")
        sequence = record["sequence"]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with exclusive_ledger_lock(self._path):
            self._sync_from_disk_locked()
            if sequence <= self._floors.get(agent_id, 0):
                raise QuorumLedgerError("replay or stale sequence refused; fail closed")
            entry_hash = self._entry_hash(self._prev_hash, record)
            entry = {"prev": self._prev_hash, "entry": record, "entry_hash": entry_hash}
            line = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(line)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._floors[agent_id] = sequence
            self._prev_hash = entry_hash
            self._entries += 1
            self._records.append(dict(record))
        return entry_hash
