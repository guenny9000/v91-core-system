#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Quorum-Review-Auftrag und persistentes Abstimmungsprotokoll (Issue
#167, Teilschritt 1: Kontrakt und Speicher, KEINE API-Aufrufe).
Erzeugt den unveraenderlichen Review-Auftrag fuer 2-aus-3-Bewertungen:
alle Bewerter erhalten denselben proposal digest, dieselbe evidence
bundle id, dieselbe policy version und dieselbe deadline. Die
Stimmenpruefung und die Auswertung bleiben allein bei
controller/agent_consensus.py (REUSE, kein zweiter Konsens-Validator);
dieses Modul persistiert Stimmen SHA-256-verkettet (Manipulation
bricht die Kette sichtbar, fail-closed beim Laden) und pflegt
dauerhafte Sequence-Floors pro Agent (Replay-Schutz kommt aus dem
speichernden Zustand, nicht aus Absenderangaben).
Kein Netz, kein API-Aufruf, keine Ausfuehrung: REQUEST != BEFEHL;
VOTE != ENTSCHEIDUNG; DETECTION != AUTHORIZATION.
Honest limits: eine gespeicherte Stimme ist signiert und verkettet,
aber die Zustaendigkeit des Schluessels und die Unabhaengigkeit der
Bewerter bleiben Betreiber-Konfiguration und sind hier nicht
pruefbar (CLAIM != EVIDENCE).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

from controller.agent_consensus import Vote, evaluate_consensus

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class QuorumRequestError(RuntimeError):
    """Fehler des Quorum-Kontrakts (fail-closed)."""


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _canonical_vote(vote: Vote) -> bytes:
    """Kanonische Bytes der Stimme, identische Feldreihenfolge wie
    agent_consensus._payload (gleicher Vertrag, gleiche Details)."""
    fields = {
        "agent_id": vote.agent_id, "proposal_digest": vote.proposal_digest,
        "epoch": vote.epoch, "sequence": vote.sequence,
        "issued_at": vote.issued_at, "approve": vote.approve,
    }
    # Bewusst OHNE ensure_ascii=False: byte-identisch zu
    # agent_consensus._payload (gleicher Signaturvertrag, PR #166).
    return json.dumps(fields, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def build_review_request(*, proposal_digest: str, evidence_bundle_id: str,
                         policy_version: str, epoch: int,
                         deadline_utc: int, now_utc: int) -> Dict[str, Any]:
    """Baut den kanonischen Review-Auftrag; inhaltlich IDENTISCH fuer alle
    Bewerter (Issue #167, Punkt 3). Kein Feld darf fehlen oder leer sein;
    eine deadline in der Vergangenheit wird abgelehnt (die Uhr ist
    injizierbar, damit Tests nicht von der Wanduhr abhaengen)."""
    if not isinstance(proposal_digest, str) or not _HEX64.fullmatch(proposal_digest):
        raise QuorumRequestError("proposal_digest must be a lowercase SHA-256 hex digest")
    if not isinstance(evidence_bundle_id, str) or not evidence_bundle_id.strip():
        raise QuorumRequestError("evidence_bundle_id must be a non-empty string")
    if not isinstance(policy_version, str) or not policy_version.strip():
        raise QuorumRequestError("policy_version must be a non-empty string")
    if type(epoch) is not int or epoch < 0:
        raise QuorumRequestError("epoch must be a non-negative integer")
    if type(deadline_utc) is not int or type(now_utc) is not int:
        raise QuorumRequestError("deadline_utc and now_utc must be integers")
    if deadline_utc <= now_utc:
        raise QuorumRequestError("deadline_utc must lie in the future")
    return {
        "schema_version": 1,
        "proposal_digest": proposal_digest,
        "evidence_bundle_id": evidence_bundle_id,
        "policy_version": policy_version,
        "epoch": epoch,
        "deadline_utc": deadline_utc,
        "issued_at_utc": now_utc,
    }


def request_digest(request: Mapping[str, Any]) -> str:
    """Deterministischer Digest des kanonischen Auftrags."""
    if not isinstance(request, Mapping):
        raise QuorumRequestError("request must be a mapping")
    digest = hashlib.sha256(_canonical(dict(request))).hexdigest()
    if not _HEX64.fullmatch(digest):
        raise QuorumRequestError("digest derivation failed")
    return digest


class VoteLedger:
    """Persistentes, SHA-256-verkettetes Abstimmungsprotokoll (JSONL).

    Jede Zeile: {"prev": <entry_sha256 der vorherigen Zeile>,
                 "vote": {...}, "entry_sha256": sha256(prev||vote-kanonisch),
                 "recorded_at_utc": int}. Erste Zeile nutzt prev = 64 Nullen.
    Manipulation an irgendeiner Zeile bricht die Kette und laesst das
    Laden fail-closed scheitern.
    """

    GENESIS = "0" * 64

    def __init__(self, store_path: str | Path) -> None:
        path = Path(store_path)
        if not path.is_absolute():
            raise QuorumRequestError("store_path must be absolute")
        self._path = path

    # -- interne Hilfen -------------------------------------------------
    def _load_verified(self) -> Tuple[List[Vote], str]:
        if not self._path.exists():
            return [], self.GENESIS
        entries: List[Vote] = []
        prev = self.GENESIS
        with self._path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise QuorumRequestError(
                        f"line {line_no}: invalid json: {exc}") from exc
                for field in ("prev", "vote", "entry_sha256"):
                    if field not in record:
                        raise QuorumRequestError(
                            f"line {line_no}: missing field {field!r}")
                vote = record["vote"]
                try:
                    parsed = Vote(
                        agent_id=vote["agent_id"],
                        proposal_digest=vote["proposal_digest"],
                        epoch=vote["epoch"], sequence=vote["sequence"],
                        issued_at=vote["issued_at"], approve=vote["approve"],
                        signature=vote["signature"])
                except (KeyError, TypeError) as exc:
                    raise QuorumRequestError(
                        f"line {line_no}: malformed vote: {exc}") from exc
                recomputed = hashlib.sha256(
                    (record["prev"].encode("utf-8") + _canonical_vote(parsed))).hexdigest()
                if recomputed != record["entry_sha256"]:
                    raise QuorumRequestError(
                        f"line {line_no}: chain integrity broken (fail-closed)")
                if record["prev"] != prev:
                    raise QuorumRequestError(
                        f"line {line_no}: prev-hash chain mismatch")
                prev = record["entry_sha256"]
                entries.append(parsed)
        return entries, prev

    def sequence_floors(self) -> Dict[str, int]:
        """Hoechste gespeicherte Sequence je Agent (dauerhafter Replay-Floor,
        Issue #167 Punkt 6: aus dem Speicher, nicht aus Absenderangaben)."""
        entries, _ = self._load_verified()
        floors: Dict[str, int] = {}
        for vote in entries:
            if vote.sequence > floors.get(vote.agent_id, -1):
                floors[vote.agent_id] = vote.sequence
        return floors

    def append_vote(self, vote: Vote, *, now_utc: int) -> None:
        """Haelt EINE Stimme dauerhaft fest; nur strikt monoton steigende
        Sequenzen je Agent werden angenommen (Replay- und Zurueckdrehen-
        Schutz). Das Ledger uebernimmt nur; die inhaltliche Beweispruefung
        (Signatur, Mitglied, Floor, Epoche) macht agent_consensus bei der
        Auswertung."""
        if not isinstance(vote, Vote):
            raise QuorumRequestError("vote must be an agent_consensus.Vote")
        if type(now_utc) is not int or now_utc < 0:
            raise QuorumRequestError("now_utc must be a non-negative integer")
        floors = self.sequence_floors()
        floor = floors.get(vote.agent_id, -1)
        if vote.sequence <= floor:
            raise QuorumRequestError(
                f"replay/backslide rejected: agent {vote.agent_id!r} sequence "
                f"{vote.sequence} not above durable floor {floor}")
        _, prev = self._load_verified()
        entry = {
            "prev": prev,
            "vote": {
                "agent_id": vote.agent_id,
                "proposal_digest": vote.proposal_digest,
                "epoch": vote.epoch,
                "sequence": vote.sequence,
                "issued_at": vote.issued_at,
                "approve": vote.approve,
                "signature": vote.signature,
            },
        }
        entry["entry_sha256"] = hashlib.sha256(
            (entry["prev"].encode("utf-8") + _canonical_vote(vote))).hexdigest()
        record = json.dumps(
            {**entry, "recorded_at_utc": now_utc}, sort_keys=True,
            ensure_ascii=False)
        parent = self._path.parent
        if str(parent) and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(record + "\n")

    def evaluate(self, *, member_keys: Mapping[str, bytes],
                 proposal_digest: str, epoch: int, now_utc: int,
                 quorum: int | None = None) -> Any:
        """Fuehrt die gespeicherten Stimmen durch agent_consensus aus.
        Die an evaluate_consensus uebergebenen Floors sind die
        EMPFANGS-Floors, rekonstruiert als hoechste gespeicherte Sequence
        je Agent minus 1 (so galt die Sequence-Pruefung zum Zeitpunkt des
        Empfangs; der zukuenftige Replay-Schutz gegen neue Stimmen bleibt
        in append_vote mit dem vollen Floor erhalten)."""
        votes, _ = self._load_verified()
        receive_floors: Dict[str, int] = {}
        for agent, highest in self.sequence_floors().items():
            receive_floors[agent] = highest - 1
        return evaluate_consensus(
            votes, member_keys=member_keys, proposal_digest=proposal_digest,
            epoch=epoch, now=now_utc,
            min_sequence_by_agent=receive_floors, quorum=quorum)


def main(argv: List[str] | None = None) -> int:  # pragma: no cover
    """Konsolenpruefung eines gespeicherten Ledgers oder Auftrags-JSONs."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Quorum review requests and tamper-evident vote ledger (#167)")
    parser.add_argument("--ledger", help="Pfad zum Voteledger-Store (Verifikation)")
    parser.add_argument("--request-json", help="Pfad zum Review-Auftrag (Digestausgabe)")
    args = parser.parse_args(argv)
    if args.ledger:
        ledger = VoteLedger(Path(args.ledger).resolve())
        floors = ledger.sequence_floors()
        print(json.dumps({"status": "VERIFIED", "agents": len(floors),
                          "floors": floors}, ensure_ascii=False))
        return 0
    if args.request_json:
        with open(args.request_json, "r", encoding="utf-8") as handle:
            request = json.load(handle)
        print(json.dumps({"request_digest": request_digest(request)},
                         ensure_ascii=False))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
