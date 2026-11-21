#!/usr/bin/env python3
"""Tests: controller/review_receipt.py (VIBE-XXXV, Issue #167).

Persist -> reload -> verify -> independence-aware evaluation, mit ECHTEM
temporarem QuorumLedger (Datei, Hash-Kette, Replay-Floors) und Fake-
Providern. Keine echten Credentials, kein Netz, keine Ausfuehrung.
"""
from __future__ import annotations

import pytest

from controller.crypto_receipts import generate_signing_keypair
from controller.quorum_ledger import QuorumLedger, build_signed_vote
from controller.review_receipt import (
    RECEIPT_SCHEMA_VERSION,
    ReviewReceiptError,
    build_review_receipt,
    evaluate_ledger_reviews,
    receipt_binds_to_vote,
    receipt_fields_valid,
    verify_review_receipt,
)

PROPOSAL_DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64
POLICY = "policy-2026-11-21"
EPOCH = 3
NOW = 1_000_000
SKEW = 60


class Agent:
    def __init__(self, name):
        self.name = name
        self.private, self.public = generate_signing_keypair()

    def vote(self, sequence, approve, issued_at=NOW, digest=PROPOSAL_DIGEST,
             epoch=EPOCH, policy=POLICY):
        return build_signed_vote(
            self.name, digest, epoch, sequence, approve, issued_at,
            policy, self.private)

    def receipt(self, vote_record, **overrides):
        params = dict(
            provider="prov-" + self.name,
            model="model-x",
            stance="APPROVE" if vote_record["approve"] else "REJECT",
            rationale="checked against runbook r-1",
            evidence=["runbook://r-1"],
        )
        params.update(overrides)
        return build_review_receipt(vote_record, private_key=self.private,
                                    **params)


def make_world(names):
    return {n: Agent(n) for n in names}


# --- Umschlag-Bau und -Verifikation ----------------------------------

def test_receipt_roundtrip_valid():
    a = Agent("a1")
    vote = a.vote(1, True)
    receipt = a.receipt(vote)
    assert receipt["receipt_schema_version"] == RECEIPT_SCHEMA_VERSION
    assert receipt_fields_valid(receipt)
    assert verify_review_receipt(receipt, a.public)
    assert receipt_binds_to_vote(receipt, vote)


def test_unknown_stance_rejected():
    a = Agent("a1")
    vote = a.vote(1, True)
    with pytest.raises(ReviewReceiptError):
        a.receipt(vote, stance="ENTHUSIASTIC")


def test_stance_approve_mismatch_rejected():
    a = Agent("a1")
    vote = a.vote(1, False)
    with pytest.raises(ReviewReceiptError):
        a.receipt(vote, stance="APPROVE")


def test_abstain_requires_signed_no():
    a = Agent("a1")
    vote = a.vote(1, True)
    with pytest.raises(ReviewReceiptError):
        a.receipt(vote, stance="ABSTAIN")
    ok_vote = a.vote(2, False)
    receipt = a.receipt(ok_vote, stance="ABSTAIN", evidence=[])
    assert receipt["stance"] == "ABSTAIN"


def test_empty_rationale_rejected():
    a = Agent("a1")
    vote = a.vote(1, True)
    with pytest.raises(ReviewReceiptError):
        a.receipt(vote, rationale=" ")


def test_missing_evidence_for_stance_rejected():
    a = Agent("a1")
    vote = a.vote(1, True)
    with pytest.raises(ReviewReceiptError):
        a.receipt(vote, evidence=[])


def test_unsigned_vote_rejected_for_receipt():
    a = Agent("a1")
    vote = a.vote(1, True)
    unsigned = {k: v for k, v in vote.items() if k != "receipt_signature"}
    with pytest.raises(ReviewReceiptError):
        a.receipt(unsigned)


def test_tampered_receipt_fails_verification():
    a = Agent("a1")
    vote = a.vote(1, True)
    receipt = a.receipt(vote)
    receipt["provider"] = "other-provider"
    assert not verify_review_receipt(receipt, a.public)


def test_wrong_key_fails_verification():
    a, b = Agent("a1"), Agent("a2")
    vote = a.vote(1, True)
    receipt = a.receipt(vote)
    assert not verify_review_receipt(receipt, b.public)


def test_binding_breaks_when_vote_changed():
    a = Agent("a1")
    vote = a.vote(1, True)
    receipt = a.receipt(vote)
    tampered = dict(vote)
    tampered["issued_at"] = vote["issued_at"] + 1
    assert not receipt_binds_to_vote(receipt, tampered)


def test_binding_breaks_on_foreign_vote():
    a, b = Agent("a1"), Agent("a2")
    va, vb = a.vote(1, True), b.vote(1, True)
    receipt = a.receipt(va)
    assert not receipt_binds_to_vote(receipt, vb)


def test_structural_invalid_receipt_detected():
    a = Agent("a1")
    vote = a.vote(1, True)
    receipt = a.receipt(vote)
    del receipt["provider"]
    assert not receipt_fields_valid(receipt)
    assert not verify_review_receipt(receipt, a.public)


# --- End-to-End mit echtem temporärem Ledger --------------------------

def test_persist_reload_approve_two_sources(tmp_path=None):
    import tempfile
    from pathlib import Path
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.jsonl"
        ledger = QuorumLedger(path, keys)
        receipts = []
        for i, (name, agent) in enumerate(sorted(world.items())):
            vote = agent.vote(i + 1, True)
            assert ledger.append_vote(vote)
            receipts.append(agent.receipt(vote))
        assert ledger.entry_count() == 2
        # Neustart: Reload von Platte mit voller Verifikation
        reloaded = QuorumLedger(path, keys)
        assert reloaded.entry_count() == 2
        result = evaluate_ledger_reviews(
            reloaded.records(), receipts, keys,
            proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
            expected_policy_version=POLICY,
            min_sequence_by_agent={"alpha": 0, "beta": 0})
        assert result["decision"] == "APPROVED_FOR_DOCUMENTATION"
        assert len(result["approved_sources"]) == 2
        assert result["authorization"].startswith("NONE")


def test_same_provider_model_collapses_to_one_source():
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    votes, receipts = [], []
    for i, (name, agent) in enumerate(sorted(world.items())):
        vote = agent.vote(i + 1, True)
        votes.append(vote)
        receipts.append(agent.receipt(vote, provider="samecloud", model="m1"))
    result = evaluate_ledger_reviews(
        votes, receipts, keys,
        proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
        expected_policy_version=POLICY, min_sequence_by_agent={})
    assert result["decision"] == "NO_QUORUM"
    assert len(result["approved_sources"]) == 1


def test_conflicting_stances_within_source_voided():
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    va = world["alpha"].vote(1, True)
    vb = world["beta"].vote(1, False)
    receipts = [
        world["alpha"].receipt(va, provider="samecloud", model="m1", stance="APPROVE"),
        world["beta"].receipt(vb, provider="samecloud", model="m1", stance="REJECT"),
    ]
    result = evaluate_ledger_reviews(
        [va, vb], receipts, keys,
        proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
        expected_policy_version=POLICY, min_sequence_by_agent={})
    assert result["decision"] == "NO_QUORUM"
    assert len(result["voided_sources"]) == 1


def test_dissent_triggers_third_review():
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    va = world["alpha"].vote(1, True)
    vb = world["beta"].vote(1, False)
    receipts = [world["alpha"].receipt(va), world["beta"].receipt(vb)]
    result = evaluate_ledger_reviews(
        [va, vb], receipts, keys,
        proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
        expected_policy_version=POLICY, min_sequence_by_agent={})
    assert result["decision"] == "THIRD_REVIEW_REQUIRED"


def test_two_rejections_reject():
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    votes = [world["alpha"].vote(1, False), world["beta"].vote(1, False)]
    receipts = [world["alpha"].receipt(votes[0]), world["beta"].receipt(votes[1])]
    result = evaluate_ledger_reviews(
        votes, receipts, keys,
        proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
        expected_policy_version=POLICY, min_sequence_by_agent={})
    assert result["decision"] == "REJECTED"


def test_vote_without_receipt_never_counts():
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    va = world["alpha"].vote(1, True)
    vb = world["beta"].vote(1, True)
    result = evaluate_ledger_reviews(
        [va, vb], [world["alpha"].receipt(va)], keys,
        proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
        expected_policy_version=POLICY, min_sequence_by_agent={})
    assert result["decision"] == "NO_QUORUM"  # nur EINE Quelle mit Disclosure
    assert any("UNSIGNED SIDECAR" in r for r in result["invalid_reasons"])


def test_receipt_without_vote_invalid():
    world = make_world(["alpha"])
    keys = {n: w.public for n, w in world.items()}
    phantom = world["alpha"].vote(1, True)
    receipt = world["alpha"].receipt(phantom)
    result = evaluate_ledger_reviews(
        [], [receipt], keys,
        proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
        expected_policy_version=POLICY, min_sequence_by_agent={})
    assert result["decision"] == "NO_QUORUM"
    assert any("without matching ledger vote" in r for r in result["invalid_reasons"])


def test_stale_sequence_excluded():
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    va = world["alpha"].vote(1, True)
    vb = world["beta"].vote(1, True)
    receipts = [world["alpha"].receipt(va), world["beta"].receipt(vb)]
    result = evaluate_ledger_reviews(
        [va, vb], receipts, keys,
        proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
        expected_policy_version=POLICY,
        min_sequence_by_agent={"alpha": 1, "beta": 1})
    assert result["decision"] == "NO_QUORUM"


def test_timestamp_window_miss_excluded():
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    va = world["alpha"].vote(1, True, issued_at=NOW - 10_000)
    vb = world["beta"].vote(1, True)
    receipts = [world["alpha"].receipt(va), world["beta"].receipt(vb)]
    result = evaluate_ledger_reviews(
        [va, vb], receipts, keys,
        proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
        expected_policy_version=POLICY, min_sequence_by_agent={})
    assert result["decision"] == "NO_QUORUM"


def test_policy_version_mismatch_excluded():
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    va = world["alpha"].vote(1, True, policy="policy-old")
    vb = world["beta"].vote(1, True)
    receipts = [world["alpha"].receipt(va), world["beta"].receipt(vb)]
    result = evaluate_ledger_reviews(
        [va, vb], receipts, keys,
        proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
        expected_policy_version=POLICY, min_sequence_by_agent={})
    assert any("policy version mismatch" in r for r in result["invalid_reasons"])
    assert result["decision"] == "NO_QUORUM"


def test_abstain_never_approval():
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    va = world["alpha"].vote(1, True)
    vb = world["beta"].vote(1, False)
    receipts = [
        world["alpha"].receipt(va),
        world["beta"].receipt(vb, stance="ABSTAIN", rationale="insufficient data",
                              evidence=[]),
    ]
    result = evaluate_ledger_reviews(
        [va, vb], receipts, keys,
        proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
        expected_policy_version=POLICY, min_sequence_by_agent={})
    assert result["decision"] == "NO_QUORUM"
    assert len(result["abstained_sources"]) == 1


def test_receipt_forgery_by_other_agent_detected():
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    va = world["alpha"].vote(1, True)
    forged = build_review_receipt(
        va, provider="fake", model="m", stance="APPROVE",
        rationale="not mine", evidence=["x"], private_key=world["beta"].private)
    result = evaluate_ledger_reviews(
        [va], [forged], keys,
        proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
        expected_policy_version=POLICY, min_sequence_by_agent={})
    assert result["decision"] == "NO_QUORUM"
    assert any("receipt signature verification failed" in r
               for r in result["invalid_reasons"])


def test_ledger_refuses_replayed_sequence():
    world = make_world(["alpha"])
    keys = {n: w.public for n, w in world.items()}
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        ledger = QuorumLedger(Path(tmp) / "l.jsonl", keys)
        v1 = world["alpha"].vote(1, True)
        ledger.append_vote(v1)
        replay = world["alpha"].vote(1, True)
        with pytest.raises(Exception):
            ledger.append_vote(replay)
        assert ledger.replay_floor("alpha") == 1


def test_empty_inputs_fail_closed():
    world = make_world(["alpha"])
    with pytest.raises(ReviewReceiptError):
        evaluate_ledger_reviews("nope", [], {"alpha": world["alpha"].public},
                               proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH,
                               now=NOW, expected_policy_version=POLICY,
                               min_sequence_by_agent={})


def test_deterministic_repeat_evaluation():
    world = make_world(["alpha", "beta"])
    keys = {n: w.public for n, w in world.items()}
    va = world["alpha"].vote(1, True)
    vb = world["beta"].vote(1, True)
    receipts = [world["alpha"].receipt(va), world["beta"].receipt(vb)]
    kwargs = dict(proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
                 expected_policy_version=POLICY, min_sequence_by_agent={})
    r1 = evaluate_ledger_reviews([va, vb], receipts, keys, **kwargs)
    r2 = evaluate_ledger_reviews([va, vb], receipts, keys, **kwargs)
    assert r1 == r2
