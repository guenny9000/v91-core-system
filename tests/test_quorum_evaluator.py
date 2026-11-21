"""V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Unit tests for controller/quorum_evaluator.py (Issue #167 slice 1).
Kernel callables and keys are injected; no network, no files, no
execution. UNKNOWN never passes; evaluation authorises nothing.
"""
from __future__ import annotations

import unittest

from controller import agent_consensus
from controller.quorum_evaluator import (
    IndependentQuorumResult,
    QuorumEvaluatorError,
    ReviewDecision,
    ReviewVote,
    evaluate_independent_quorum,
)

KEY_A = b"a" * 32
KEY_B = b"b" * 32
KEY_C = b"c" * 32
MEMBERS = {"agent-a": KEY_A, "agent-b": KEY_B, "agent-c": KEY_C}
DIGEST = "a" * 64
FLOORS = {"agent-a": 0, "agent-b": 0, "agent-c": 0}
EPOCH = 7
NOW = 1_000


def make_vote(agent: str, approve: bool, key: bytes, seq: int = 1,
              digest: str = DIGEST, epoch: int = EPOCH, issued_at: int = NOW):
    return agent_consensus.sign_vote(
        agent_id=agent, proposal_digest=digest, epoch=epoch,
        sequence=seq, issued_at=issued_at, approve=approve, agent_key=key)


def make_review(agent: str, provider: str, model: str, stance: str,
                evidence=("evidence://repo-commit-1234",), seq: int = 1,
                digest: str = DIGEST, key: bytes = None, rationale="checked"):
    vote = make_vote(agent, stance == "APPROVE", key or MEMBERS[agent], seq=seq,
                     digest=digest)
    return ReviewVote(vote=vote, provider=provider, model=model, stance=stance,
                      rationale=rationale, evidence=tuple(evidence))


def run_quorum(reviews, **overrides):
    kwargs = dict(member_keys=MEMBERS, proposal_digest=DIGEST, epoch=EPOCH,
                  now=NOW, min_sequence_by_agent=FLOORS)
    kwargs.update(overrides)
    return evaluate_independent_quorum(reviews, **kwargs)


class QuorumEvaluatorConfigTests(unittest.TestCase):
    def test_empty_reviews_fail_closed(self):
        with self.assertRaises(QuorumEvaluatorError):
            run_quorum([])

    def test_required_sources_below_two_is_rejected(self):
        with self.assertRaises(QuorumEvaluatorError):
            run_quorum([make_review("agent-a", "prov-1", "cat-1", "APPROVE")],
                       independent_sources_required=1)


class QuorumEvaluatorAgreementTests(unittest.TestCase):
    def test_two_independent_approvals_pass_documentation_level(self):
        reviews = [make_review("agent-a", "prov-1", "cat-1", "APPROVE"),
                   make_review("agent-b", "prov-2", "dog-2", "APPROVE")]
        result = run_quorum(reviews)
        self.assertEqual(result.decision, ReviewDecision.APPROVED_FOR_DOCUMENTATION)
        self.assertEqual(len(result.approved_sources), 2)

    def test_result_discloses_that_evaluation_authorises_nothing(self):
        result = run_quorum([make_review("agent-a", "prov-1", "cat-1", "APPROVE"),
                             make_review("agent-b", "prov-2", "dog-2", "APPROVE")])
        self.assertIn("NONE", result.as_dict()["authorization"])

    def test_two_independent_rejections_reject(self):
        result = run_quorum([make_review("agent-a", "prov-1", "cat-1", "REJECT"),
                             make_review("agent-b", "prov-2", "dog-2", "REJECT")])
        self.assertEqual(result.decision, ReviewDecision.REJECTED)
        self.assertEqual(len(result.rejected_sources), 2)

    def test_disagreement_requires_third_review(self):
        result = run_quorum([make_review("agent-a", "prov-1", "cat-1", "APPROVE"),
                             make_review("agent-b", "prov-2", "dog-2", "REJECT")])
        self.assertEqual(result.decision, ReviewDecision.THIRD_REVIEW_REQUIRED)

    def test_same_provider_and_model_collapse_to_one_source(self):
        result = run_quorum([make_review("agent-a", "Prov-1", "cat-1", "APPROVE"),
                             make_review("agent-b", "prov-1", "CAT-1", "APPROVE")])
        self.assertEqual(result.decision, ReviewDecision.NO_QUORUM)
        self.assertEqual(len(result.approved_sources), 1)

    def test_abstain_gives_no_contribution(self):
        result = run_quorum([make_review("agent-a", "prov-1", "cat-1", "APPROVE"),
                             make_review("agent-b", "prov-2", "dog-2", "ABSTAIN",
                                         evidence=())])
        self.assertEqual(result.decision, ReviewDecision.NO_QUORUM)
        self.assertEqual(result.abstained_sources and 1, 1)

    def test_conflicting_stances_within_one_source_void_it(self):
        first = make_review("agent-a", "prov-1", "cat-1", "APPROVE")
        second = make_review("agent-b", "prov-1", "cat-1", "REJECT", seq=2)
        third = make_review("agent-c", "prov-2", "dog-2", "APPROVE", seq=3)
        result = run_quorum([first, second, third])
        self.assertEqual(result.decision, ReviewDecision.NO_QUORUM)
        self.assertEqual(len(result.voided_sources), 1)

    def test_order_independence_of_sources(self):
        reviews = [make_review("agent-a", "prov-1", "cat-1", "APPROVE"),
                   make_review("agent-b", "prov-2", "dog-2", "REJECT")]
        first = run_quorum(reviews)
        second = run_quorum(list(reversed(reviews)))
        self.assertEqual(first.decision, second.decision)
        self.assertEqual(first.invalid_reasons, second.invalid_reasons)


class QuorumEvaluatorEvidenceTests(unittest.TestCase):
    def test_approve_without_evidence_is_invalid(self):
        result = run_quorum([make_review("agent-a", "prov-1", "cat-1", "APPROVE",
                                         evidence=()),
                             make_review("agent-b", "prov-2", "dog-2", "APPROVE")])
        self.assertEqual(result.decision, ReviewDecision.NO_QUORUM)
        self.assertTrue(any("evidence missing" in r for r in result.invalid_reasons))

    def test_empty_evidence_entries_are_invalid(self):
        result = run_quorum([make_review("agent-a", "prov-1", "cat-1", "APPROVE",
                                         evidence=("  ",)),
                             make_review("agent-b", "prov-2", "dog-2", "APPROVE")])
        self.assertTrue(any("evidence missing" in r for r in result.invalid_reasons))

    def test_missing_rationale_is_invalid(self):
        result = run_quorum([make_review("agent-a", "prov-1", "cat-1", "APPROVE",
                                         rationale="  "),
                             make_review("agent-b", "prov-2", "dog-2", "APPROVE")])
        self.assertTrue(any("rationale missing" in r for r in result.invalid_reasons))

    def test_abstain_with_signed_approve_is_invalid(self):
        bad = make_review("agent-a", "prov-1", "cat-1", "ABSTAIN", evidence=())
        vote = agent_consensus.sign_vote(
            agent_id="agent-a", proposal_digest=DIGEST, epoch=EPOCH,
            sequence=1, issued_at=NOW, approve=True, agent_key=KEY_A)
        bad_approve = ReviewVote(vote=vote, provider="prov-1", model="cat-1",
                                 stance="ABSTAIN", rationale="not sure",
                                 evidence=())
        result = run_quorum([bad, bad_approve,
                             make_review("agent-b", "prov-2", "dog-2", "ABSTAIN",
                                         evidence=())])
        self.assertTrue(any("ABSTAIN must carry approve=False" in r
                            for r in result.invalid_reasons))

    def test_stance_approve_must_not_carry_reject_signature_payload(self):
        reject_vote = make_vote("agent-a", False, KEY_A)
        review = ReviewVote(vote=reject_vote, provider="prov-1", model="cat-1",
                            stance="APPROVE", rationale="mislabeled",
                            evidence=("evidence://repo-commit-1234",))
        result = run_quorum([review])
        self.assertTrue(any("stance/approve mismatch" in r
                            for r in result.invalid_reasons))


class QuorumEvaluatorCryptoLayerTests(unittest.TestCase):
    def test_bad_signature_is_caught_by_agent_consensus(self):
        forged = make_vote("agent-a", True, b"x" * 32)
        reviews = [ReviewVote(vote=forged, provider="prov-1", model="cat-1",
                              stance="APPROVE", rationale="forged",
                              evidence=("evidence://repo-commit-1234",)),
                   make_review("agent-b", "prov-2", "dog-2", "APPROVE")]
        result = run_quorum(reviews)
        self.assertEqual(result.decision, ReviewDecision.NO_QUORUM)
        self.assertTrue(any("signature verification failed" in r
                            for r in result.invalid_reasons))

    def test_stale_sequence_is_caught_by_agent_consensus(self):
        reviews = [make_review("agent-a", "prov-1", "cat-1", "APPROVE", seq=0),
                   make_review("agent-b", "prov-2", "dog-2", "APPROVE")]
        result = run_quorum(reviews)
        self.assertTrue(any("stale or untracked sequence" in r
                            for r in result.invalid_reasons))

    def test_digest_mismatch_is_caught_by_agent_consensus(self):
        reviews = [make_review("agent-a", "prov-1", "cat-1", "APPROVE",
                               digest="b" * 64),
                   make_review("agent-b", "prov-2", "dog-2", "APPROVE")]
        result = run_quorum(reviews)
        self.assertTrue(any("proposal or epoch mismatch" in r
                            for r in result.invalid_reasons))


if __name__ == "__main__":
    unittest.main()
