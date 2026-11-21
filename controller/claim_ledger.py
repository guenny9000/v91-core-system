"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Dateibasiertes Forum-Claim-Ledger (Taskboard-Konvention Phase 2,
VIBE-XLIV). Wiederverwendung der quorum_ledger-Muster: append-only
JSONL, Hash-Kette ueber Eintraege, kanonisches JSON, Ed25519-Pflicht
fuer jedes Ereignis (crypto_receipts-Reuse), Sequenz-Floor je Autor
gegen Replay ueber Neustarts. Die Ereignis- und Konfliktregeln sind
deckungsgleich mit docs/V91-FORUM-TASKBOARD-KONVENTION.md Abschnitt 2.

Phase 3 (VIBE-XLV), rueckwaertskompatible Zusatzschicht: Ein optionaler
Author-Receipt (author_receipt_guard-Reuse) kann VOR jedem Schreiben
fail-closed geprueft werden. AUTHOR_CLAIM != IDENTITY: Der author eines
Ereignisses bleibt eine Selbstauskunft; erst ein verifizierter Receipt
hebt die Identitaet auf VERIFIED. SIGNATURE != TRUTH, UNKNOWN != PASS.
Ohne uebergebene ReceiptPolicy bleibt das Verhalten exakt wie in
Phase 2 (bestehende Aufrufe und Tests unveraendert).

Ereignisse (append-only, je gebunden an task_id, scope, author,
expected_base_sha bzw. reason, issued_at):
- CLAIM: belegt task_id UND scope ausschliesslich; Pflichtfelder sind
  expected_base_sha (Commit-SHA der Basis, KEIN Blob-SHA) und
  expires_at > issued_at.
- RELEASE: Rueckzug durch den Halter ODER eine Operator-Identitaet.
- DONE: Abschluss NUR durch den Halter; gibt task_id/scope frei.
- EXPIRE: NUR durch eine Operator-Identitaet, NUR wenn der Claim
  zeitlich abgelaufen ist (issued_at >= expires_at) und mit
  Pflichtbegruendung (reason). EXPIRE ist der einzige Weg, einen
  abgelaufenen Claim ohne DONE neu belegbar zu machen; kein stilles
  Uebernehmen.

Ehrliche Grenzen (bewusst, nicht Luecken):
- Ed25519 beweist die Urheberschaft eines Ereignisses, NICHT die
  Wahrheit seiner Angabe; Schluesselverwaltung bleibt beim Caller.
- Oeffentliche Schluessel muessen aus unabhaengig vertrauenswuerdigem
  Kontext stammen, NIEMALS aus dem Ledger selbst.
- FAIL-CLOSED GEGEN DOPPELCLAIM: Ein aktiver CLAIM auf dieselbe
  task_id oder denselben scope wird strikt zurueckgewiesen
  (CONFLICT), auch nach zeitlichem Ablauf und VOR einem expliziten
  EXPIRE. Kein Ueberschreiben, kein Erben.
- ATOMARES SCHREIBEN (MAX-BEST-Pruefung 1): Jeder Append schreibt
  die komplette neue Datei in eine Temp-Datei im selben Verzeichnis,
  fsync, dann atomares os.replace. Abstuerze koennen KEINE halben
  Eintraege erzeugen; verwaiste Temp-Dateien werden beim Laden
  ignoriert und NIE still importiert (TEMPOERAER != LEDGER).
- EXPIRE-AUTORISIERUNG (MAX-BEST-Pruefung 2): expire_authorities
  sind explizit zu uebergebende Operator-Identitaeten; EXPIRE ohne
  Autoritaet, vor Ablauf oder ohne Begruendung wird verweigert.
- CRASH-ERKENNUNG (MAX-BEST-Pruefung 3): Eine abgeschnittene letzte
  Zeile, eine Leerzeile, eine gebrochene Hash-Kette oder eine
  ungueltige Signatur fuehren zum Load-Fehler; das Ledger kann
  nicht in einen scheinbar gesunden Zustand versetzt werden.
- RECEIPT-GATE (Phase 3): Die Receipt-Bewertung (VERIFIED /
  UNVERIFIED_CLAIM_ONLY / REJECTED mit reason) wird pro Append
  geprueft und NUR bei REJECTED abgewiesen; sie wird bewusst NICHT
  in den Ledger-Eintrag persistiert, damit das hash-gekettete,
  signierte Eintragsschema stabil bleibt. Wer den Nachweis einer
  Verifikation braucht, fuehrt ihn im aufrufenden Kontext.
- Append-only mit Hash-Kette ist Manipulationserkennung, KEIN
  WORM-Speicher; wer die Datei ersetzen kann, kann sie neu
  schreiben. SCRIPTED != INSTALLED: kein laufender Dienst bindet
  dieses Modul bisher ein (Wiring = Folgearbeit).
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Tuple

from controller.author_receipt_guard import (
    AuthorReceipt,
    ClaimBindingContext,
    ReceiptEvaluation,
    evaluate_author_receipt,
)
from controller.crypto_receipts import (
    SIGNATURE_FIELD,
    canonical_record_bytes,
    sign_record,
    verify_record_signature,
)

RECORD_TYPE_CLAIM = "forum_claim_event"
SIGNATURE_ALGORITHM = "ED25519"
GENESIS = "GENESIS"

EVENT_CLAIM = "CLAIM"
EVENT_RELEASE = "RELEASE"
EVENT_DONE = "DONE"
EVENT_EXPIRE = "EXPIRE"
EVENTS = (EVENT_CLAIM, EVENT_RELEASE, EVENT_DONE, EVENT_EXPIRE)

TMP_PREFIX = "claim-ledger-tmp-"
TMP_SUFFIX = ".jsonl-partial"


class ClaimLedgerError(Exception):
    """Fail-closed Fehler des Claim-Ledgers."""


class ReceiptVerificationError(ClaimLedgerError):
    """Wird ausgeloest, wenn ein Author-Receipt fail-closed abgewiesen
    wird. Ledgerschreibungen werden davor verweigert; die Datei bleibt
    unveraendert (REJECTED != GESPEICHERT)."""

    def __init__(self, evaluation: ReceiptEvaluation) -> None:
        self.evaluation = evaluation
        super().__init__(
            "author receipt rejected ({}): {}".format(
                evaluation.state.value, evaluation.reason
            )
        )


@dataclass(frozen=True)
class ReceiptPolicy:
    """Optionale, pro Caller uebergebene Receipt-Pruefkonfiguration.

    Fail-closed-Regeln: Widerrufene Signer/Schluessel, abgelaufene oder
    in der Zukunft ausgestellte Receipts, unpassende Kontext-Bindung
    und ungueltige Signaturen werden IMMER abgewiesen (REJECTED).
    require_verified_receipt=True weist zusaetzlich fehlende Receipts
    ab; mit False zaehlt der Claim nur als UNVERIFIED_CLAIM_ONLY.
    """

    trusted_keys: Mapping
    verify_signature_fn: Callable[[str, str, str], bool]
    now_epoch_fn: Callable[[], int]
    revoked_signers: Tuple[str, ...] = ()
    revoked_keys: Tuple[str, ...] = ()
    require_verified_receipt: bool = True


def _is_int(value: Any) -> bool:
    return type(value) is int


def _is_hex(value: Any, length: int) -> bool:
    if not isinstance(value, str) or len(value) != length:
        return False
    return all(c in "0123456789abcdef" for c in value)


def claim_fields_valid(record: Any) -> bool:
    """Strukturelle Pruefung eines Claim-Ereignisses (ohne Signaturbeweis)."""
    if not isinstance(record, dict):
        return False
    if record.get("record_type") != RECORD_TYPE_CLAIM:
        return False
    if record.get("signature_algorithm") != SIGNATURE_ALGORITHM:
        return False
    if record.get("event") not in EVENTS:
        return False
    for field in ("author", "task_id", "scope"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            return False
    if not _is_int(record.get("sequence")) or record["sequence"] < 1:
        return False
    if not _is_int(record.get("issued_at")):
        return False
    if record["event"] == EVENT_CLAIM:
        if not _is_hex(record.get("expected_base_sha"), 40):
            return False
        if not _is_int(record.get("expires_at")):
            return False
        if record["expires_at"] <= record["issued_at"]:
            return False
    if record["event"] == EVENT_EXPIRE:
        reason = record.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return False
    return True


def build_claim_event(
    event: str,
    author: str,
    task_id: str,
    scope: str,
    sequence: int,
    issued_at: int,
    private_key: bytes,
    expected_base_sha: str = "",
    expires_at: int = 0,
    reason: str = "",
) -> Dict:
    """Erzeugt ein Ed25519-signiertes Claim-Ereignis (fail-closed)."""
    record: Dict = {
        "record_type": RECORD_TYPE_CLAIM,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "event": event,
        "author": author,
        "task_id": task_id,
        "scope": scope,
        "sequence": sequence,
        "issued_at": issued_at,
    }
    if event == EVENT_CLAIM:
        record["expected_base_sha"] = expected_base_sha
        record["expires_at"] = expires_at
    if event == EVENT_EXPIRE:
        record["reason"] = reason
    if not claim_fields_valid(record):
        raise ClaimLedgerError("claim event fields invalid; fail closed")
    record[SIGNATURE_FIELD] = sign_record(record, private_key)
    return record


def verify_claim_event(record: Any, public_key: bytes) -> bool:
    """Struktur + Ed25519-Signatur; jede Rueckgabe ausser True ist Nein."""
    if not claim_fields_valid(record):
        return False
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        return False
    return verify_record_signature(record, public_key)


class ClaimLedger:
    """
    Persistenter Claim-Speicher des Forum-Taskboards (Phase 2).

    Append-only JSONL mit Hash-Kette, Ed25519-Pflicht je Ereignis und
    Replay-Floor je Autor. Konflikt- und Autorisierungsregeln werden
    beim Laden UND beim Anhaengen geprueft: eine Ereignisfolge, die
    die Regeln verletzt, kann das Ledger nie in einen gueltigen
    Zustand bringen.

    Phase 3: append_event akzeptiert optional receipt und
    receipt_policy. Mit Policy wird vor jedem Schreiben ein
    Author-Receipt geprueft (AUTHOR_CLAIM != IDENTITY); REJECTED wirft
    ReceiptVerificationError, bevor irgendein Byte geschrieben wird.
    Ohne Policy gilt unveraendert das Phase-2-Verhalten.
    """

    def __init__(
        self,
        path: Path,
        public_keys: Mapping,
        expire_authorities,
    ):
        if not isinstance(path, Path):
            raise ClaimLedgerError("path must be a Path")
        self._validate_keys(public_keys)
        if isinstance(expire_authorities, str) or not hasattr(expire_authorities, "__iter__"):
            raise ClaimLedgerError("expire_authorities must be an iterable of author ids")
        authorities = set()
        for author_id in expire_authorities:
            if not isinstance(author_id, str) or not author_id.strip():
                raise ClaimLedgerError("expire authority must be a non-empty id")
            authorities.add(author_id)
        self._path = path
        self._keys = dict(public_keys)
        self._expire_authorities = frozenset(authorities)
        self._floors: Dict[str, int] = {}
        self._prev_hash = GENESIS
        self._entries = 0
        self._records: list = []
        self._active_claims: Dict[str, Dict] = {}
        self._scopes: Dict[str, str] = {}
        self._raw = b""
        if path.exists():
            self._load_and_verify()

    @staticmethod
    def _validate_keys(public_keys: Any) -> None:
        if not isinstance(public_keys, Mapping) or not public_keys:
            raise ClaimLedgerError("public_keys must be a non-empty mapping")
        for author_id, key in public_keys.items():
            if not isinstance(author_id, str) or not author_id.strip():
                raise ClaimLedgerError("author id must be non-empty")
            if not isinstance(key, bytes) or len(key) != 32:
                raise ClaimLedgerError("public key must be raw 32 bytes")

    # -- Hash-Kette (quorum_ledger-Wiederverwendung) --

    def _entry_hash(self, prev: str, entry_record: Dict) -> str:
        payload = {"prev": prev, "entry": entry_record}
        return hashlib.sha256(canonical_record_bytes(payload)).hexdigest()

    # -- Ereignisregeln (Check ohne Mutation) --

    def _check_event(self, record: Dict) -> None:
        event = record["event"]
        task_id = record["task_id"]
        scope = record["scope"]
        author = record["author"]
        active = self._active_claims.get(task_id)
        if event == EVENT_CLAIM:
            if task_id in self._active_claims:
                raise ClaimLedgerError("CONFLICT: task_id already actively claimed; fail closed")
            if scope in self._scopes:
                raise ClaimLedgerError("CONFLICT: scope already actively claimed; fail closed")
            return
        if active is None:
            raise ClaimLedgerError("no active claim for task_id; fail closed")
        if active["scope"] != scope:
            raise ClaimLedgerError("scope mismatch against active claim; fail closed")
        if event == EVENT_DONE:
            if author != active["author"]:
                raise ClaimLedgerError("DONE only by claim holder; fail closed")
            return
        if event == EVENT_RELEASE:
            if author != active["author"] and author not in self._expire_authorities:
                raise ClaimLedgerError("RELEASE only by holder or operator identity; fail closed")
            return
        if event == EVENT_EXPIRE:
            if author not in self._expire_authorities:
                raise ClaimLedgerError("EXPIRE not authorized for author; fail closed")
            if record["issued_at"] < active["expires_at"]:
                raise ClaimLedgerError("EXPIRE refused before claim expiry; fail closed")
            return

    def _commit_event(self, record: Dict) -> None:
        event = record["event"]
        if event == EVENT_CLAIM:
            self._active_claims[record["task_id"]] = dict(record)
            self._scopes[record["scope"]] = record["task_id"]
            return
        self._active_claims.pop(record["task_id"], None)
        self._scopes.pop(record["scope"], None)

    # -- Laden und Verifizieren (crash-sicher, fail-closed) --

    def _load_and_verify(self) -> None:
        raw = self._path.read_bytes()
        if raw and not raw.endswith(chr(10).encode("utf-8")):
            raise ClaimLedgerError("truncated last line; fail closed")
        if raw:
            text = raw.decode("utf-8")
            for line in text.split(chr(10))[:-1]:
                self._load_line(line)
        self._raw = raw

    def _load_line(self, line: str) -> None:
        if not line.strip():
            raise ClaimLedgerError("blank line in ledger; fail closed")
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ClaimLedgerError("malformed JSON line; fail closed") from exc
        if not isinstance(entry, dict):
            raise ClaimLedgerError("ledger entry must be an object")
        if set(entry) != {"prev", "entry", "entry_hash"}:
            raise ClaimLedgerError("ledger entry schema violated")
        if entry["prev"] != self._prev_hash:
            raise ClaimLedgerError("hash chain broken; fail closed")
        expected = self._entry_hash(entry["prev"], entry["entry"])
        if entry["entry_hash"] != expected:
            raise ClaimLedgerError("entry hash mismatch; fail closed")
        record = entry["entry"]
        author = record.get("author") if isinstance(record, dict) else None
        public_key = self._keys.get(author)
        if public_key is None:
            raise ClaimLedgerError("unknown author in ledger; fail closed")
        if not verify_claim_event(record, public_key):
            raise ClaimLedgerError("event signature invalid; fail closed")
        if record["sequence"] <= self._floors.get(author, 0):
            raise ClaimLedgerError("replay/sequence violation in ledger; fail closed")
        self._check_event(record)
        self._floors[author] = record["sequence"]
        self._commit_event(record)
        self._prev_hash = entry["entry_hash"]
        self._entries += 1
        self._records.append(dict(record))

    # -- Oeffentliche Lese-Schnittstelle --

    def entry_count(self) -> int:
        return self._entries

    def replay_floor(self, author: str) -> int:
        return self._floors.get(author, 0)

    def active_claim(self, task_id: str) -> Dict:
        active = self._active_claims.get(task_id)
        return dict(active) if active is not None else {}

    def scope_claimed_by(self, scope: str):
        return self._scopes.get(scope)

    def records(self) -> Tuple:
        """Verifizierte Ereignisse als Kopien, in Anhaengereihenfolge."""
        return tuple(dict(record) for record in self._records)

    # -- Author-Receipt-Gate (Phase 3, optional) --

    def _evaluate_receipt(
        self,
        record: Dict,
        receipt: Any,
        receipt_policy: ReceiptPolicy,
    ) -> ReceiptEvaluation:
        context = ClaimBindingContext(
            task_id=record.get("task_id", ""),
            scope=record.get("scope", ""),
            event_type=record.get("event", ""),
            expected_base_sha=record.get("expected_base_sha", ""),
            author_claim=record.get("author", ""),
            now_epoch=receipt_policy.now_epoch_fn(),
        )
        return evaluate_author_receipt(
            context,
            receipt,
            trusted_keys=receipt_policy.trusted_keys,
            revoked_signers=receipt_policy.revoked_signers,
            revoked_keys=receipt_policy.revoked_keys,
            verify_signature_fn=receipt_policy.verify_signature_fn,
            require_verified_receipt=receipt_policy.require_verified_receipt,
        )

    # -- Atomares Anhaengen (crash-sicher) --

    def append_event(
        self,
        record: Dict,
        receipt: "AuthorReceipt | None" = None,
        receipt_policy: "ReceiptPolicy | None" = None,
    ) -> str:
        """Haengt ein validiertes, signiertes Ereignis atomar an.

        Mit receipt_policy wird vor jeder Schreibung der (optionale)
        Author-Receipt fail-closed geprueft; REJECTED wirft
        ReceiptVerificationError, bevor irgendein Byte die Platte
        beruehrt (permits_ledger_write == False). Ohne Policy bleibt
        das Phase-2-Verhalten exakt erhalten.
        """
        if receipt_policy is not None:
            evaluation = self._evaluate_receipt(record, receipt, receipt_policy)
            if not evaluation.permits_ledger_write:
                raise ReceiptVerificationError(evaluation)
        author = record.get("author") if isinstance(record, dict) else None
        public_key = self._keys.get(author)
        if public_key is None or not verify_claim_event(record, public_key):
            raise ClaimLedgerError("unverified or unknown event refused; fail closed")
        if record["sequence"] <= self._floors.get(author, 0):
            raise ClaimLedgerError("replay or stale sequence refused; fail closed")
        self._check_event(record)
        entry_hash = self._entry_hash(self._prev_hash, record)
        entry = {"prev": self._prev_hash, "entry": record, "entry_hash": entry_hash}
        line = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        new_raw = self._raw + (line + chr(10)).encode("utf-8")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=TMP_PREFIX, suffix=TMP_SUFFIX, dir=str(self._path.parent)
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(new_raw)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, self._path)
        except BaseException:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            raise
        self._sync_directory_best_effort()
        self._raw = new_raw
        self._floors[author] = record["sequence"]
        self._commit_event(record)
        self._prev_hash = entry_hash
        self._entries += 1
        self._records.append(dict(record))
        return entry_hash

    def _sync_directory_best_effort(self) -> None:
        """Verzeichnis-fsync (POSIX, best effort). Vor dem replace ist die
        Datei selbst bereits fsynced; unterbleibender DIR-fsync (z. B.
        Windows) veraendert die Dateiinhalte nicht."""
        try:
            dir_fd = os.open(str(self._path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
