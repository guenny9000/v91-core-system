#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Batch Quorum Gate (MAX-BEST, VIBE-XLII): die fail-closed Bruecke von
einem VoteBatch (provider_vote_adapter) zur Quorum-ENTSCHIEDUNG.
Schliesst die Luecke aus dem VIBE-XLI-Audit: ein abgebrochener Lauf
darf nie ueber Caller-Disziplin gesichert sein (KOMMENTAR != MECHANISMUS).

Kontrakt:
  decide_vote_batch(...) -> ConsensusResult

Kernregeln (fail-closed):
- CANCELLED != PARTIAL QUORUM: Ein als abgebrochen markierter Batch
  wird IMMER als NO_QUORUM entschieden, egal wie viele gueltige
  Stimmen vorher eingesammelt wurden (auch bei quorum=1 mit einer
  vollstaendig gueltigen Stimme; ABBRUCH GANZHEIT vor Teilerfolg).
- DIGEST-BINDING: Ein cancellation_digest, der nicht zum proposal_digest
  passt, ist ein Abbruch aus einer FREMDEN Runde: NO_QUORUM, die
  Stimmen werden nicht einmal angesehen (BINDING != BEHAUPTET).
- KEINE AUSNAHME: Es gibt keinen Parameter, der cancelled ueberstimmt.
  Wer eine abgebrochene Runde doch auswerten will, muss einen NEUEN,
  sauberen Lauf starten; dieses Modul ist die einzige sichere Bruecke.
- Ungueltige Eingaben (kein VoteBatch, fehlende Felder) werden
  verweigert, nie geraten (UNKNOWN ist nie PASS).

REUSE (NO_DUPLICATE_SYSTEMS):
  provider_vote_adapter  Sammlung + Abbruch-Kennzeichnung (VIBE-XLI),
                        bleibt unangetastet; die Teilstimme bleibt
                        dort als Evidence erhaltbar (BEWEIS != STIMME).
  agent_consensus        Signatur-/Replay-/Mehrheitspruefung und das
                        ConsensusResult bleiben dort (Import, kein
                        Duplikat); dieses Gate fuegt NUR die
                        Abbruch-Durchsetzung hinzu.
  quorum_decision        Bewertet persistierte Ledger-Belege (andere
                        Quelle); dieses Gate bewertet den frischen
                        Batch einer Sammelrunde. Keine Ueberlappung.
  quorum_execution_gate  Getrennte Ausfuehrungsseite; ENTSCHEIDUNG
                        bleibt != AUSGEFUEHRUNG.

Honest limits:
GATE != GERICHT (eine Mehrheit beweist keine Richtigkeit);
entschieden != ausgefuehrt (EXECUTION braucht quorum_execution_gate);
SCRIPTED != INSTALLED.
"""
from __future__ import annotations

from typing import Mapping

from controller.agent_consensus import ConsensusResult, Decision, evaluate_consensus
from controller.provider_vote_adapter import VoteBatch

_BATCH_FIELDS = ("votes", "failures")


class BatchQuorumGateError(ValueError):
    """Invalid input to the batch quorum gate (fail-closed)."""


def _refuse_no_quorum(*, member_keys: Mapping[str, bytes],
                      proposal_digest: str, epoch: int, now: int,
                      min_sequence_by_agent: Mapping[str, int],
                      quorum: int | None = None,
                      allowed_clock_skew_seconds: int = 60,
                      why: str = "") -> ConsensusResult:
    """NO_QUORUM via the REAL evaluation path with zero votes (REUSE)."""
    result = evaluate_consensus(
        [],
        member_keys=member_keys,
        proposal_digest=proposal_digest,
        epoch=epoch,
        now=now,
        min_sequence_by_agent=min_sequence_by_agent,
        quorum=quorum,
        allowed_clock_skew_seconds=allowed_clock_skew_seconds,
    )
    assert result.decision is Decision.NO_QUORUM
    return result


def decide_vote_batch(
    batch: VoteBatch,
    *,
    member_keys: Mapping[str, bytes],
    proposal_digest: str,
    epoch: int,
    now: int,
    min_sequence_by_agent: Mapping[str, int],
    quorum: int | None = None,
    allowed_clock_skew_seconds: int = 60,
) -> ConsensusResult:
    """Evaluate one collected batch; a cancelled round is ALWAYS NO_QUORUM."""
    if not isinstance(batch, VoteBatch):
        raise BatchQuorumGateError("batch must be a VoteBatch (fail-closed)")
    for field in _BATCH_FIELDS:
        if not hasattr(batch, field):
            raise BatchQuorumGateError("batch is missing field %r" % field)

    cancelled = getattr(batch, "cancelled", None)
    digest = getattr(batch, "cancellation_digest", None)

    if cancelled is True:
        if digest is not None and digest != proposal_digest:
            return _refuse_no_quorum(
                member_keys=member_keys,
                proposal_digest=proposal_digest, epoch=epoch, now=now,
                min_sequence_by_agent=min_sequence_by_agent,
                quorum=quorum,
                allowed_clock_skew_seconds=allowed_clock_skew_seconds,
                why="cancellation digest from a foreign round",
            )
        # CANCELLED != PARTIAL QUORUM (kein Parameter ueberstimmt das).
        return _refuse_no_quorum(
            member_keys=member_keys,
            proposal_digest=proposal_digest, epoch=epoch, now=now,
            min_sequence_by_agent=min_sequence_by_agent,
            quorum=quorum,
            allowed_clock_skew_seconds=allowed_clock_skew_seconds,
            why="round cancelled: whole round invalid",
        )

    if cancelled is not False and cancelled is not None:
        raise BatchQuorumGateError("cancelled must be a boolean, not guessed")

    # Nicht abgebrochen: echte Auswertung auf dem normalen Pfad (REUSE).
    return evaluate_consensus(
        list(batch.votes),
        member_keys=member_keys,
        proposal_digest=proposal_digest,
        epoch=epoch,
        now=now,
        min_sequence_by_agent=min_sequence_by_agent,
        quorum=quorum,
        allowed_clock_skew_seconds=allowed_clock_skew_seconds,
    )
