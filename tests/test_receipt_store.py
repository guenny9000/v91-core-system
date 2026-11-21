#!/usr/bin/env python3
"""Tests: controller/receipt_store.py (VIBE-XXXVI, Issue #167).

Persist -> Neustart -> Reload -> Auswertung mit ECHTEM temporärem
ReceiptStore UND echtem temporärem QuorumLedger plus Fake-Providern.
Keine echten Credentials, kein Netz, keine Ausführung.
"""
from __future__ import annotations

from pathlib import Path as _P

import pytest

from controller.crypto_receipts import generate_signing_keypair
from controller.quorum_ledger import QuorumLedger, build_signed_vote
from controller.receipt_store import GENESIS, ReceiptStore, ReceiptStoreError
from controller.review_receipt import (
    ReviewReceiptError,
    build_review_receipt,
    evaluate_ledger_reviews,
)

PROPOSAL_DIGEST = "a" * 64
POLICY = "policy-2026-11-21"
EPOCH = 3
NOW = 1_000_000
SKEW = 60


class Agent:
    def __init__(self, name):
        self.name = name
        self.private, self.public = generate_signing_keypair()
        self.sequence_issued = 0

    def vote(self, approve=True, issued_at=NOW, digest=PROPOSAL_DIGEST,
             epoch=EPOCH, policy=POLICY):
        self.sequence_issued += 1
        return build_signed_vote(
            self.name, digest, epoch, self.sequence_issued, approve,
            issued_at, policy, self.private)

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


# --- Bau, Verifikation, Persistenz -----------------------------------

def test_roundtrip_append_and_reload():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        store = ReceiptStore(_P(tmp) / "r.jsonl", keys)
        assert store.head_hash() == GENESIS
        for name, agent in sorted(world.items()):
            vote = agent.vote()
            store.append_receipt(agent.receipt(vote), vote)
        assert store.entry_count() == 2
        reloaded = ReceiptStore(_P(tmp) / "r.jsonl", keys)
        assert reloaded.entry_count() == 2
        assert reloaded.records() == store.records()
        assert reloaded.head_hash() == store.head_hash()


def test_receipt_without_vote_refused():
    import tempfile
    world = make_world(["alpha"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        store = ReceiptStore(_P(tmp) / "r.jsonl", keys)
        vote = world["alpha"].vote()
        receipt = world["alpha"].receipt(vote)
        with pytest.raises(ReceiptStoreError):
            store.append_receipt(receipt, {"bogus": 1})


def test_receipt_with_wrong_vote_refused():
    import tempfile
    world = make_world(["alpha"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        store = ReceiptStore(_P(tmp) / "r.jsonl", keys)
        v1 = world["alpha"].vote()
        v2 = world["alpha"].vote()
        with pytest.raises(ReceiptStoreError):
            store.append_receipt(world["alpha"].receipt(v1), v2)


def test_forged_receipt_refused():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        store = ReceiptStore(_P(tmp) / "r.jsonl", keys)
        vote = world["alpha"].vote()
        forged = build_review_receipt(
            vote, provider="fake", model="m", stance="APPROVE",
            rationale="not mine", evidence=["x"],
            private_key=world["beta"].private)
        with pytest.raises(ReceiptStoreError):
            store.append_receipt(forged, vote)


def test_tampered_receipt_refused():
    import tempfile
    world = make_world(["alpha"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        store = ReceiptStore(_P(tmp) / "r.jsonl", keys)
        vote = world["alpha"].vote()
        receipt = world["alpha"].receipt(vote)
        receipt["provider"] = "other"
        with pytest.raises(ReceiptStoreError):
            store.append_receipt(receipt, vote)


def test_replay_sequence_refused():
    import tempfile
    world = make_world(["alpha"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        store = ReceiptStore(_P(tmp) / "r.jsonl", keys)
        v1 = world["alpha"].vote()
        store.append_receipt(world["alpha"].receipt(v1), v1)
        replay_vote = build_signed_vote(
            "alpha", PROPOSAL_DIGEST, EPOCH, 1, True, NOW, POLICY,
            world["alpha"].private)
        replay_receipt = build_review_receipt(
            replay_vote, provider="prov-alpha", model="model-x",
            stance="APPROVE", rationale="r", evidence=["e"],
            private_key=world["alpha"].private)
        with pytest.raises(ReceiptStoreError):
            store.append_receipt(replay_receipt, replay_vote)


def test_replay_floor_survives_restart():
    import tempfile
    from pathlib import Path
    world = make_world(["alpha"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "r.jsonl"
        store = ReceiptStore(path, keys)
        v1 = world["alpha"].vote()
        store.append_receipt(world["alpha"].receipt(v1), v1)
        assert store.replay_floor("alpha") == 1
        reloaded = ReceiptStore(path, keys)
        assert reloaded.replay_floor("alpha") == 1
        stale = build_signed_vote(
            "alpha", PROPOSAL_DIGEST, EPOCH, 1, True, NOW, POLICY,
            world["alpha"].private)
        with pytest.raises(ReceiptStoreError):
            reloaded.append_receipt(world["alpha"].receipt(stale), stale)


def test_chain_tamper_detected_on_reload():
    import tempfile
    from pathlib import Path
    world = make_world(["alpha", "beta"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "r.jsonl"
        store = ReceiptStore(path, keys)
        for name, agent in sorted(world.items()):
            vote = agent.vote()
            store.append_receipt(agent.receipt(vote), vote)
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[0] = lines[0].replace("prov-alpha", "mallory")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with pytest.raises(ReceiptStoreError):
            ReceiptStore(path, keys)


def test_truncated_file_detected():
    import tempfile
    from pathlib import Path
    world = make_world(["alpha"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "r.jsonl"
        store = ReceiptStore(path, keys)
        vote = world["alpha"].vote()
        store.append_receipt(world["alpha"].receipt(vote), vote)
        text = path.read_text(encoding="utf-8")
        path.write_text(text[: len(text) // 2], encoding="utf-8")
        with pytest.raises(ReceiptStoreError):
            ReceiptStore(path, keys)


def test_removed_line_detected():
    import tempfile
    from pathlib import Path
    world = make_world(["alpha", "beta"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "r.jsonl"
        store = ReceiptStore(path, keys)
        for name, agent in sorted(world.items()):
            vote = agent.vote()
            store.append_receipt(agent.receipt(vote), vote)
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
        with pytest.raises(ReceiptStoreError):
            ReceiptStore(path, keys)


def test_unknown_agent_in_file_detected():
    import tempfile
    from pathlib import Path
    world = make_world(["alpha"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "r.jsonl"
        store = ReceiptStore(path, keys)
        other = Agent("mallory")
        vote = world["alpha"].vote()
        mallory_vote = build_signed_vote(
            "mallory", PROPOSAL_DIGEST, EPOCH, 1, True, NOW, POLICY,
            other.private)
        with pytest.raises(ReceiptStoreError):
            store.append_receipt(other.receipt(mallory_vote), mallory_vote)


# --- Konstruktor-Fail-Closed -----------------------------------------

def test_rejects_non_path():
    with pytest.raises(ReceiptStoreError):
        ReceiptStore("nope", {"a": b"x" * 32})


def test_rejects_empty_keys():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ReceiptStoreError):
            ReceiptStore(Path(tmp) / "r.jsonl", {})


def test_rejects_bad_key_length():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ReceiptStoreError):
            ReceiptStore(Path(tmp) / "r.jsonl", {"a": b"short"})


# --- End-to-End: Store + Ledger + Auswertung -------------------------

def test_end_to_end_two_sources_approve():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        from pathlib import Path
        ledger = QuorumLedger(Path(tmp) / "ledger.jsonl", keys)
        store = ReceiptStore(Path(tmp) / "receipts.jsonl", keys)
        for name, agent in sorted(world.items()):
            vote = agent.vote()
            ledger.append_vote(vote)
            store.append_receipt(agent.receipt(vote), vote)
        # Neustart: beide Dateien neu laden, volle Verifikation
        ledger2 = QuorumLedger(Path(tmp) / "ledger.jsonl", keys)
        store2 = ReceiptStore(Path(tmp) / "receipts.jsonl", keys)
        result = evaluate_ledger_reviews(
            ledger2.records(), store2.records(), keys,
            proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
            expected_policy_version=POLICY,
            min_sequence_by_agent={"alpha": 0, "beta": 0})
        assert result["decision"] == "APPROVED_FOR_DOCUMENTATION"
        assert len(result["approved_sources"]) == 2
        assert result["authorization"].startswith("NONE")


def test_end_to_end_store_without_ledger_vote_invalid():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        from pathlib import Path
        ledger = QuorumLedger(Path(tmp) / "ledger.jsonl", keys)
        store = ReceiptStore(Path(tmp) / "receipts.jsonl", keys)
        va = world["alpha"].vote()
        vb = world["beta"].vote()
        ledger.append_vote(va)
        store.append_receipt(world["alpha"].receipt(va), va)
        # beta-Umschlag liegt im Store, Stimme fehlt im Ledger:
        # die Auswertung darf beta niemals zaehlen.
        store.append_receipt(world["beta"].receipt(vb), vb)
        ledger2 = QuorumLedger(Path(tmp) / "ledger.jsonl", keys)
        store2 = ReceiptStore(Path(tmp) / "receipts.jsonl", keys)
        result = evaluate_ledger_reviews(
            ledger2.records(), store2.records(), keys,
            proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
            expected_policy_version=POLICY,
            min_sequence_by_agent={})
        assert result["decision"] == "NO_QUORUM"
        assert any("without matching ledger vote" in r
                   for r in result["invalid_reasons"])


def test_end_to_end_dissent_third_review():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = {n: a.public for n, a in world.items()}
    with tempfile.TemporaryDirectory() as tmp:
        from pathlib import Path
        ledger = QuorumLedger(Path(tmp) / "ledger.jsonl", keys)
        store = ReceiptStore(Path(tmp) / "receipts.jsonl", keys)
        pairs = [(world["alpha"], True), (world["beta"], False)]
        for agent, approve in pairs:
            vote = agent.vote(approve=approve)
            ledger.append_vote(vote)
            store.append_receipt(agent.receipt(vote), vote)
        ledger2 = QuorumLedger(Path(tmp) / "ledger.jsonl", keys)
        store2 = ReceiptStore(Path(tmp) / "receipts.jsonl", keys)
        result = evaluate_ledger_reviews(
            ledger2.records(), store2.records(), keys,
            proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
            expected_policy_version=POLICY,
            min_sequence_by_agent={})
        assert result["decision"] == "THIRD_REVIEW_REQUIRED"


def test_deterministic_chain_head():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = {n: a.public for n, a in world.items()}
    pairs = []
    for name, agent in sorted(world.items()):
        vote = agent.vote()
        pairs.append((vote, agent.receipt(vote)))
    heads = []
    for run in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            store = ReceiptStore(_P(tmp) / "r.jsonl", keys)
            for vote, receipt in pairs:
                store.append_receipt(receipt, vote)
            heads.append(store.head_hash())
    assert heads[0] == heads[1]
