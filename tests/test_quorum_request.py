#!/usr/bin/env python3
"""Tests fuer controller/quorum_request.py (Issue #167, Teilschritt 1).

Decken: kanonischen Review-Auftrag, deterministischen Digest, injizierbare
Uhr, persistentes SHA-256-verkettetes Voteledger, Replay-/Backslide-
Ablehnung, Manipulationserkennung (fail-closed) und die Integration mit
agent_consensus (2-aus-3: zwei dich stimmige Stimmen akzeptieren ein
Ergebnis, Widerspruch oder Ungueltigkeit bleibt NO_QUORUM).
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller.agent_consensus import Decision, sign_vote
from controller.quorum_request import (
    QuorumRequestError,
    VoteLedger,
    build_review_request,
    request_digest,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
KEY_A = b"A" * 32
KEY_B = b"B" * 32
KEY_C = b"C" * 32
NOW = 1_700_000_000
DEADLINE = NOW + 600
EPOCH = 7


class ReviewRequestTests(unittest.TestCase):
    def test_request_is_canonical_and_deterministic(self) -> None:
        r1 = build_review_request(
            proposal_digest=DIGEST_A, evidence_bundle_id="evd-001",
            policy_version="p-1.0", epoch=EPOCH, deadline_utc=DEADLINE,
            now_utc=NOW)
        r2 = build_review_request(
            proposal_digest=DIGEST_A, evidence_bundle_id="evd-001",
            policy_version="p-1.0", epoch=EPOCH, deadline_utc=DEADLINE,
            now_utc=NOW)
        self.assertEqual(r1, r2)
        d1, d2 = request_digest(r1), request_digest(r2)
        self.assertEqual(d1, d2)
        self.assertEqual(64, len(d1))
        self.assertEqual(
            hashlib.sha256(json.dumps(r1, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest(),
            d1)

    def test_missing_or_empty_fields_fail_closed(self) -> None:
        with self.assertRaises(QuorumRequestError):
            build_review_request(proposal_digest="nothex",
                                 evidence_bundle_id="evd", policy_version="p",
                                 epoch=EPOCH, deadline_utc=DEADLINE, now_utc=NOW)
        with self.assertRaises(QuorumRequestError):
            build_review_request(proposal_digest=DIGEST_A, evidence_bundle_id=" ",
                                 policy_version="p", epoch=EPOCH,
                                 deadline_utc=DEADLINE, now_utc=NOW)
        with self.assertRaises(QuorumRequestError):
            build_review_request(proposal_digest=DIGEST_A, evidence_bundle_id="e",
                                 policy_version="", epoch=EPOCH,
                                 deadline_utc=DEADLINE, now_utc=NOW)

    def test_deadline_in_past_fails_with_injected_clock(self) -> None:
        with self.assertRaises(QuorumRequestError):
            build_review_request(proposal_digest=DIGEST_A,
                                 evidence_bundle_id="evd", policy_version="p",
                                 epoch=EPOCH, deadline_utc=NOW - 1, now_utc=NOW)
        with self.assertRaises(QuorumRequestError):
            build_review_request(proposal_digest=DIGEST_A,
                                 evidence_bundle_id="evd", policy_version="p",
                                 epoch=EPOCH, deadline_utc=NOW, now_utc=NOW)


class VoteLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Path(self._tmp.name) / "ledger" / "votes.jsonl"
        self.ledger = VoteLedger(self.store)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _vote(self, agent: str, key: bytes, seq: int, approve: bool,
              digest: str = DIGEST_A, issued_at: int = NOW):
        return sign_vote(agent_id=agent, proposal_digest=digest, epoch=EPOCH,
                         sequence=seq, issued_at=issued_at, approve=approve,
                         agent_key=key)

    def test_rejects_relative_paths(self) -> None:
        with self.assertRaises(QuorumRequestError):
            VoteLedger("relative/path.jsonl")

    def test_append_and_persist_restart_safe(self) -> None:
        self.ledger.append_vote(self._vote("agent-a", KEY_A, 1, True),
                               now_utc=NOW)
        self.ledger.append_vote(self._vote("agent-b", KEY_B, 1, True),
                               now_utc=NOW)
        reopened = VoteLedger(self.store)
        floors = reopened.sequence_floors()
        self.assertEqual({"agent-a": 1, "agent-b": 1}, floors)

    def test_replay_and_backslide_rejected(self) -> None:
        self.ledger.append_vote(self._vote("agent-a", KEY_A, 2, True),
                               now_utc=NOW)
        with self.assertRaises(QuorumRequestError):
            self.ledger.append_vote(self._vote("agent-a", KEY_A, 2, True),
                                    now_utc=NOW)
        with self.assertRaises(QuorumRequestError):
            self.ledger.append_vote(self._vote("agent-a", KEY_A, 1, True),
                                    now_utc=NOW)

    def test_tampered_line_fails_closed_on_load(self) -> None:
        self.ledger.append_vote(self._vote("agent-a", KEY_A, 1, True),
                               now_utc=NOW)
        lines = self.store.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[0])
        record["vote"]["approve"] = False
        lines[0] = json.dumps(record, sort_keys=True)
        lines.append('{"prev": "' + "f" * 64 + '", "vote": {}, '
                     '"entry_sha256": "' + "e" * 64 + '"}')
        self.store.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaises(QuorumRequestError):
            VoteLedger(self.store).sequence_floors()

    def test_truncated_file_fails_closed(self) -> None:
        self.ledger.append_vote(self._vote("agent-a", KEY_A, 1, True),
                               now_utc=NOW)
        text = self.store.read_text(encoding="utf-8")
        self.store.write_text(text[: len(text) // 2], encoding="utf-8")
        with self.assertRaises(QuorumRequestError):
            VoteLedger(self.store).sequence_floors()


class ConsensusIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Path(self._tmp.name) / "votes.jsonl"
        self.ledger = VoteLedger(self.store)
        self.members = {"agent-a": KEY_A, "agent-b": KEY_B, "agent-c": KEY_C}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _vote(self, agent: str, key: bytes, seq: int, approve: bool):
        return sign_vote(agent_id=agent, proposal_digest=DIGEST_A, epoch=EPOCH,
                         sequence=seq, issued_at=NOW, approve=approve,
                         agent_key=key)

    def test_two_matching_approvals_accept(self) -> None:
        self.ledger.append_vote(self._vote("agent-a", KEY_A, 1, True),
                               now_utc=NOW)
        self.ledger.append_vote(self._vote("agent-b", KEY_B, 1, True),
                               now_utc=NOW)
        result = self.ledger.evaluate(member_keys=self.members,
                                      proposal_digest=DIGEST_A, epoch=EPOCH,
                                      now_utc=NOW)
        self.assertEqual(Decision.ACCEPT, result.decision)
        self.assertEqual(2, result.quorum_required)

    def test_two_rejections_reject(self) -> None:
        self.ledger.append_vote(self._vote("agent-a", KEY_A, 1, False),
                               now_utc=NOW)
        self.ledger.append_vote(self._vote("agent-b", KEY_B, 1, False),
                               now_utc=NOW)
        result = self.ledger.evaluate(member_keys=self.members,
                                      proposal_digest=DIGEST_A, epoch=EPOCH,
                                      now_utc=NOW)
        self.assertEqual(Decision.REJECT, result.decision)

    def test_disagreement_stays_no_quorum(self) -> None:
        self.ledger.append_vote(self._vote("agent-a", KEY_A, 1, True),
                               now_utc=NOW)
        self.ledger.append_vote(self._vote("agent-b", KEY_B, 1, False),
                               now_utc=NOW)
        result = self.ledger.evaluate(member_keys=self.members,
                                      proposal_digest=DIGEST_A, epoch=EPOCH,
                                      now_utc=NOW)
        self.assertEqual(Decision.NO_QUORUM, result.decision)

    def test_wrong_epoch_or_digest_is_no_quorum(self) -> None:
        self.ledger.append_vote(self._vote("agent-a", KEY_A, 1, True),
                               now_utc=NOW)
        result = self.ledger.evaluate(member_keys=self.members,
                                      proposal_digest=DIGEST_B, epoch=EPOCH,
                                      now_utc=NOW)
        self.assertEqual(Decision.NO_QUORUM, result.decision)

    def test_forged_signature_is_no_quorum(self) -> None:
        vote = self._vote("agent-a", KEY_A, 1, True)
        forged = sign_vote(agent_id="agent-a", proposal_digest=DIGEST_A,
                           epoch=EPOCH, sequence=1, issued_at=NOW,
                           approve=True, agent_key=b"X" * 32)
        self.ledger.append_vote(vote, now_utc=NOW)
        self.store.write_text("", encoding="utf-8")
        self.ledger.append_vote(forged, now_utc=NOW)
        result = self.ledger.evaluate(member_keys=self.members,
                                      proposal_digest=DIGEST_A, epoch=EPOCH,
                                      now_utc=NOW)
        self.assertEqual(Decision.NO_QUORUM, result.decision)

    def test_unicode_agent_id_roundtrip(self) -> None:
        # Byte-Vertrag-Kontrolle (PR #166): die kanonischen Bytes im Ledger
        # muessen identisch zu agent_consensus._payload sein, sonst scheitert
        # die Signaturpruefung bei Nicht-ASCII-Identitaeten.
        umlaut_agent = "agent-\u00e4\u00f6\u00fc"
        vote = sign_vote(agent_id=umlaut_agent, proposal_digest=DIGEST_A,
                         epoch=EPOCH, sequence=1, issued_at=NOW,
                         approve=True, agent_key=KEY_A)
        self.ledger.append_vote(vote, now_utc=NOW)
        result = self.ledger.evaluate(
            member_keys={umlaut_agent: KEY_A},
            proposal_digest=DIGEST_A, epoch=EPOCH, now_utc=NOW, quorum=1)
        self.assertEqual(Decision.ACCEPT, result.decision)


if __name__ == "__main__":
    unittest.main()
