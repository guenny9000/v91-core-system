"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Consensus-Archive (MAX-BEST, VIBE-XXXVII; Issue #167 Betriebsteile):
Ledger UND Receipt-Store als gepaarte, konsistenzaufzwingende
Einheit. Schliesst die Restluecke von #300: bislang konnte der Caller
Stimme und Umschlag getrennt persistieren und inkonsistente Zustaende
erzeugen (Umschlag ohne Ledger-Stimme, Stimme ohne Umschlag).

REUSE / NO_DUPLICATE_SYSTEMS:
  quorum_ledger    Stimmen-Persistenz (Instanz, unveraendert)
  receipt_store    Umschlag-Persistenz (Instanz, unveraendert)
  review_receipt   Paarungspruefung receipt_binds_to_vote,
                   Strukturpruefung receipt_fields_valid
  quorum_ledger.vote_fields_valid Stimmen-Struktur
  quorum_evaluator Entscheidung bleibt dort (ARCHIV != BEURTEILUNG)

Invarianten (fail-closed):
- cast_vote haengt Stimme und Umschlag NUR gemeinsam an: Pre-Check
  der Bindung VOR jeder Persistenz; misslingt der Umschlag nach der
  Stimme, wird die Stimmen-Zeile kompensiert (Datei um die letzte
  Zeile zurueckgeschrieben und neu verifiziert). SCHIEBEN != LAUF.
- Laden prueft die Paarung beider Dateien: jede Stimme braucht GENAU
  EINEN bindenden Umschlag, jeder Umschlag GENAU EINE Stimme.
  Inkonstistenz => komplettes Laden abgebrochen (UNKNOWN != PASS).

Honest limits:
- KOMPENSATION != TRANSAKTION: kein echtes Dateisystem-Commit ueber
  zwei Dateien. Ein Absturz zwischen Stimmen-Append und Kompensation
  hinterlaesst eine inkonsistente Datei, die beim naechsten Laden
  fail-closed erkannt wird (ERKENNBAR != UNMOEGLICH).
- ARCHIV != MERKLE-TREE: die Paarung zaehlt und bindet, sie beweist
  keine Vollstaendigkeit gegenueber einer Aussenwelt.
- Alle Aussagen gelten nur innerhalb der zwei Dateien; ein extern
  gepflegtes Ledger bleibt fuer das Archiv unsichtbar.
- Keine Ausfuehrung, keine Autorisierung, kein Netz, keine echten
  Credentials; oeffentliche Schluessel aus vertrauenswuerdigem,
  unabhaengigem Kontext, NIEMALS aus dem Archiv.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Tuple

from controller.quorum_ledger import QuorumLedger, QuorumLedgerError, vote_fields_valid
from controller.receipt_store import ReceiptStore, ReceiptStoreError
from controller.review_receipt import (
    evaluate_ledger_reviews,
    receipt_binds_to_vote,
    receipt_fields_valid,
)

LEDGER_FILENAME = "quorum-votes.jsonl"
RECEIPTS_FILENAME = "review-receipts.jsonl"


class ConsensusArchiveError(Exception):
    """Fail-closed Fehler des Consensus-Archivs."""


class ConsensusArchive:
    """
    Gepaarte Persistenz: QuorumLedger-Stimme und Review-Receipt
    werden NUR gemeinsam angehaengt und beim Laden NUR als konsistentes
    Paar akzeptiert.
    """

    def __init__(self, directory: Path, public_keys: Mapping[str, bytes]):
        if not isinstance(directory, Path):
            raise ConsensusArchiveError("directory must be a Path")
        if not isinstance(public_keys, Mapping) or not public_keys:
            raise ConsensusArchiveError("public_keys must be a non-empty mapping")
        directory.mkdir(parents=True, exist_ok=True)
        try:
            self.ledger = QuorumLedger(directory / LEDGER_FILENAME, public_keys)
            self.store = ReceiptStore(directory / RECEIPTS_FILENAME, public_keys)
        except (QuorumLedgerError, ReceiptStoreError) as exc:
            raise ConsensusArchiveError("component load failed; fail closed: %s" % exc) from exc
        self._directory = directory
        self._keys = dict(public_keys)
        self._verify_pairing()

    def _verify_pairing(self) -> None:
        votes = self.ledger.records()
        receipts = self.store.records()
        if len(votes) != len(receipts):
            raise ConsensusArchiveError(
                "pairing violated: votes and receipts differ in count; fail closed")
        votes_by_key = {}
        for vote in votes:
            key = (vote["agent_id"], vote["sequence"])
            if key in votes_by_key:
                raise ConsensusArchiveError(
                    "duplicate vote key in ledger; fail closed")
            votes_by_key[key] = vote
        for receipt in receipts:
            key = (receipt["agent_id"], receipt["sequence"])
            vote = votes_by_key.get(key)
            if vote is None:
                raise ConsensusArchiveError(
                    "receipt without matching ledger vote; fail closed")
            if not receipt_binds_to_vote(receipt, vote):
                raise ConsensusArchiveError(
                    "receipt does not bind to its ledger vote; fail closed")
            votes_by_key.pop(key)
        if votes_by_key:
            raise ConsensusArchiveError(
                "ledger vote without matching receipt; fail closed")

    def _compensate_ledger(self, previous_entries: int) -> None:
        """Schreibt die Stimmen-Datei um die letzte Zeile zurueck
        und verifiziert das Ergebnis vollstaendig (Kompensation)."""
        path = self._directory / LEDGER_FILENAME
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
        if raw and not raw.endswith("\n"):
            raise ConsensusArchiveError("ledger truncated; cannot compensate; fail closed")
        lines = raw.split("\n")[:-1] if raw else []
        if len(lines) != previous_entries + 1:
            raise ConsensusArchiveError(
                "unexpected ledger state; compensation refused; fail closed")
        with open(path, "w", encoding="utf-8") as fh:
            for line in lines[:-1]:
                fh.write(line)
                fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.ledger = QuorumLedger(path, self._keys)
        if self.ledger.entry_count() != previous_entries:
            raise ConsensusArchiveError(
                "compensation verification failed; fail closed")

    def cast_vote(self, vote: Mapping, receipt: Mapping) -> None:
        """Haengt Stimme und Umschlag NUR gemeinsam an (fail-closed).

        Pre-Check: Struktur + Bindung VOR jedweder Persistenz
        (BINDING != BEHAUPTET). Post-Check: misslingt der Umschlag,
        wird die Stimme kompensiert (GETRENNT != GEPAAART).
        """
        if not isinstance(vote, Mapping) or not vote_fields_valid(dict(vote)):
            raise ConsensusArchiveError("vote invalid; fail closed")
        receipt_mapping = dict(receipt) if isinstance(receipt, Mapping) else None
        if receipt_mapping is None or not receipt_fields_valid(receipt_mapping):
            raise ConsensusArchiveError("receipt invalid; fail closed")
        if not receipt_binds_to_vote(receipt_mapping, dict(vote)):
            raise ConsensusArchiveError("receipt does not bind to vote; fail closed")
        agent_id = vote["agent_id"]
        sequence = vote["sequence"]
        if sequence <= self.ledger.replay_floor(agent_id):
            raise ConsensusArchiveError("replay or stale sequence refused; fail closed")
        if sequence <= self.store.replay_floor(agent_id):
            raise ConsensusArchiveError("store replay floor violated; fail closed")
        entries_before = self.ledger.entry_count()
        try:
            self.ledger.append_vote(dict(vote))
        except QuorumLedgerError as exc:
            raise ConsensusArchiveError("ledger refused vote; fail closed: %s" % exc) from exc
        try:
            self.store.append_receipt(receipt_mapping, dict(vote))
        except (ReceiptStoreError, QuorumLedgerError) as exc:
            self._compensate_ledger(entries_before)
            raise ConsensusArchiveError(
                "receipt persistence failed; vote compensated; fail closed: %s" % exc) from exc

    def votes(self) -> Tuple:
        """Verifizierte Stimmen (Kopien), in Anhaengereihenfolge."""
        return self.ledger.records()

    def receipts(self) -> Tuple:
        """Verifizierte Umschlaege (Kopien), in Anhaengereihenfolge."""
        return self.store.records()

    def entry_count(self) -> int:
        if self.ledger.entry_count() != self.store.entry_count():
            raise ConsensusArchiveError("pairing count mismatch; fail closed")
        return self.ledger.entry_count()

    def replay_floor(self, agent_id: str) -> int:
        floor = self.ledger.replay_floor(agent_id)
        if floor != self.store.replay_floor(agent_id):
            raise ConsensusArchiveError("replay floors diverged; fail closed")
        return floor

    def evaluate_reviews(
            self, *, proposal_digest: str, epoch: int, now: int,
            expected_policy_version: str,
            min_sequence_by_agent: Mapping[str, int],
            independent_sources_required: int = 2,
            allowed_clock_skew_seconds: int = 60) -> dict:
        """Laedt das Archiv frisch, verifiziert die Paarung und bewertet es.

        min_sequence_by_agent MUSS aus einem unabhaengig vertrauenswuerdigen
        Sequenz-Floor-Kontext stammen. Nicht den aktuellen Archiv-Floor
        einsetzen: damit wuerden die gerade zu pruefenden Stimmen als stale
        verworfen. now bleibt explizit fuer reproduzierbare Zeitfenster-Tests.

        Ergebnis ist eine Bewertung, keine Autorisierung oder Ausfuehrung.
        Der Reload verifiziert beide Dateien und ihre Paarung; er stellt
        keinen atomaren Snapshot gegen gleichzeitige externe Dateiaenderungen
        oder einen Transaktions-Commit ueber zwei Dateien her.
        """
        fresh = ConsensusArchive(self._directory, self._keys)
        result = evaluate_ledger_reviews(
            fresh.votes(), fresh.receipts(), self._keys,
            proposal_digest=proposal_digest,
            epoch=epoch,
            now=now,
            expected_policy_version=expected_policy_version,
            min_sequence_by_agent=min_sequence_by_agent,
            independent_sources_required=independent_sources_required,
            allowed_clock_skew_seconds=allowed_clock_skew_seconds)
        result["archive_pairing"] = "VERIFIED_ON_RELOAD"
        result["archive_entry_count"] = fresh.entry_count()
        result["archive_limitations"] = [
            "COMPENSATION != TRANSACTION",
            "ARCHIVE != MERKLE-TREE",
            "INDEPENDENCE != PROVEN",
        ]
        return result
