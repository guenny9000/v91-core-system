#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Tests fuer controller/batch_quorum_gate.py (VIBE-XLII). Deterministisch,
simulierte Provider, kein Netz, keine Credentials.
Kernfall: abgebrochene Runde mit EINER vollstaendig gueltigen Stimme
und quorum=1 muss NO_QUORUM bleiben (CANCELLED != PARTIAL QUORUM).
"""
from __future__ import annotations

import hashlib
import unittest

from controller.agent_consensus import Decision, sign_vote
from controller.batch_quorum_gate import (
    BatchQuorumGateError,
    decide_vote_batch,
)
from controller.provider_health import CancelScope
from controller.provider_vote_adapter import (
    Proposal,
    Provider,
    VoteBatch,
    collect_provider_votes,
)

DIGEST = hashlib.sha256(b"xl2-batch-gate").hexdigest()
PROPOSAL = Proposal(DIGEST, 4)
KEYS = {"agent-a": b"a" * 32, "agent-b": b"b" * 32}


def signed(agent: str, proposal: Proposal = PROPOSAL):
    return sign_vote(
        agent_id=agent,
        proposal_digest=proposal.digest,
        epoch=proposal.epoch,
        sequence=1,
        issued_at=100,
        approve=True,
        agent_key=KEYS[agent],
    )


def ok_provider(agent: str, calls: list) -> Provider:
    def invoke(p: Proposal):
        calls.append(agent)
        return signed(agent, p)
    return Provider(agent, "boundary-" + agent, invoke)


def decide(batch, *, quorum=None, digest=DIGEST, keys=None, members=None):
    m = keys if keys is not None else dict(KEYS)
    ids = members if members is not None else list(m)
    return decide_vote_batch(
        batch,
        member_keys=m,
        proposal_digest=digest,
        epoch=PROPOSAL.epoch,
        now=130,
        min_sequence_by_agent={a: 0 for a in ids},
        quorum=quorum,
    )


class CancelledBatchTests(unittest.TestCase):

    def test_mid_round_cancel_with_valid_vote_is_never_quorum(self):
        # DER Kernfall aus dem Audit: abgebrochene Runde, EINE gueltige
        # Stimme, quorum=1 -> NO_QUORUM, nicht ACCEPT (GANZHEIT VOR TEIL).
        calls: list = []
        scope = CancelScope()

        def cancelling(p: Proposal):
            vote = signed("agent-a", p)
            scope.cancel(p.digest, reason="mid-round stop")
            return vote

        batch = collect_provider_votes(
            PROPOSAL, [Provider("agent-a", "boundary-a", cancelling)],
            cancel_scope=scope,
        )
        self.assertTrue(batch.cancelled)
        self.assertEqual(len(batch.votes), 1)  # Evidence bleibt erhaltbar
        self.assertIs(decide(batch, quorum=1).decision, Decision.NO_QUORUM)

    def test_cancelled_batch_by_hand_never_quorum(self):
        batch = VoteBatch(
            votes=(signed("agent-a"),), failures=(),
            cancelled=True, cancellation_digest=DIGEST,
        )
        self.assertIs(decide(batch, quorum=1).decision, Decision.NO_QUORUM)

    def test_foreign_cancellation_digest_is_no_quorum(self):
        # Abbruch-Token aus einer FREMDEN Runde: Bindung versagt.
        batch = VoteBatch(
            votes=(signed("agent-a"),), failures=(),
            cancelled=True, cancellation_digest="f" * 64,
        )
        self.assertIs(decide(batch, quorum=1).decision, Decision.NO_QUORUM)

    def test_no_parameter_overrides_cancelled(self):
        # Es gibt keinen Weg, ein cancelled=True in ein Quorum zu drehen:
        # auch quorum=1 mit allen Mitgliedern bleibt NO_QUORUM.
        batch = VoteBatch(
            votes=(signed("agent-a"), signed("agent-b")), failures=(),
            cancelled=True, cancellation_digest=DIGEST,
        )
        for q in (1, 2):
            self.assertIs(decide(batch, quorum=q).decision,
                           Decision.NO_QUORUM)

    def test_cancelled_batch_with_zero_votes_also_no_quorum(self):
        batch = VoteBatch(votes=(), failures=("a: round cancelled",),
                          cancelled=True, cancellation_digest=DIGEST)
        self.assertIs(decide(batch, quorum=1).decision, Decision.NO_QUORUM)


class NormalBatchTests(unittest.TestCase):

    def test_uncancelled_quorum_still_reached(self):
        calls: list = []
        batch = collect_provider_votes(
            PROPOSAL, [ok_provider("agent-a", calls),
                       ok_provider("agent-b", calls)],
        )
        self.assertFalse(batch.cancelled)
        self.assertIs(decide(batch, quorum=2).decision, Decision.ACCEPT)

    def test_missing_votes_yield_no_quorum(self):
        calls: list = []
        batch = collect_provider_votes(
            PROPOSAL, [ok_provider("agent-a", calls)],
        )
        self.assertIs(decide(batch, quorum=2).decision, Decision.NO_QUORUM)

    def test_uncancelled_defaults_are_consistent(self):
        batch = VoteBatch(votes=(signed("agent-a"),), failures=())
        self.assertIs(decide(batch, quorum=1).decision, Decision.ACCEPT)


class FailClosedInputTests(unittest.TestCase):

    def test_non_batch_input_refused(self):
        with self.assertRaises(BatchQuorumGateError):
            decide({"votes": []})  # type: ignore[arg-type]
        with self.assertRaises(BatchQuorumGateError):
            decide([signed("agent-a")])  # type: ignore[arg-type]

    def test_none_batch_refused_never_guessed(self):
        with self.assertRaises(BatchQuorumGateError):
            decide(None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
