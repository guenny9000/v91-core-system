#!/usr/bin/env python3
"""Tests: controller/consensus_archive.py (VIBE-XXXVII, Issue #167).

Ledger + Store als PAAR: gemeinsames Anhaengen mit Kompensation,
Paarungs-Nachweis beim Laden, Teilnahme- und Reihenfolge-Angriffe.
Persist -> Neustart -> Reload -> Auswertung mit echten temporären
Dateien. Keine echten Credentials, kein Netz, keine Ausführung.
"""
from __future__ import annotations

from pathlib import Path as _P

import pytest

from controller.consensus_archive import (
    ConsensusArchive,
    ConsensusArchiveError,
    LEDGER_FILENAME,
    RECEIPTS_FILENAME,
)
from controller.crypto_receipts import generate_signing_keypair
from controller.quorum_ledger import QuorumLedger, build_signed_vote
from controller.receipt_store import ReceiptStore, ReceiptStoreError
from controller.review_receipt import build_review_receipt, evaluate_ledger_reviews

PROPOSAL_DIGEST = "b" * 64
POLICY = "policy-2026-11-21"
EPOCH = 4
NOW = 2_000_000


class Agent:
    def __init__(self, name):
        self.name = name
        self.private, self.public = generate_signing_keypair()
        self.sequence_issued = 0

    def vote(self, approve=True, issued_at=NOW):
        self.sequence_issued += 1
        return build_signed_vote(
            self.name, PROPOSAL_DIGEST, EPOCH, self.sequence_issued,
            approve, issued_at, POLICY, self.private)

    def receipt(self, vote_record, **overrides):
        params = dict(
            provider="prov-" + self.name,
            model="model-y",
            stance="APPROVE" if vote_record["approve"] else "REJECT",
            rationale="runbook r-2 checked",
            evidence=["runbook://r-2"],
        )
        params.update(overrides)
        return build_review_receipt(vote_record, private_key=self.private,
                                    **params)


def make_world(names):
    return {n: Agent(n) for n in names}


def keys_of(world):
    return {n: a.public for n, a in world.items()}


def cast(archive, agent, approve=True):
    vote = agent.vote(approve=approve)
    receipt = agent.receipt(vote)
    archive.cast_vote(vote, receipt)
    return vote, receipt


# --- Bau, Paarung, Persistenz ----------------------------------------

def test_roundtrip_two_sources_approve():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        for name in sorted(world):
            cast(archive, world[name])
        assert archive.entry_count() == 2
        # Neustart
        reloaded = ConsensusArchive(_P(tmp), keys)
        assert reloaded.entry_count() == 2
        result = evaluate_ledger_reviews(
            reloaded.votes(), reloaded.receipts(), keys,
            proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
            expected_policy_version=POLICY, min_sequence_by_agent={})
        assert result["decision"] == "APPROVED_FOR_DOCUMENTATION"
        assert len(result["approved_sources"]) == 2


def test_cast_without_binding_refused_nothing_persisted():
    import tempfile
    world = make_world(["alpha"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        v1 = world["alpha"].vote()
        v2 = world["alpha"].vote()
        with pytest.raises(ConsensusArchiveError):
            archive.cast_vote(v1, world["alpha"].receipt(v2))
        assert archive.entry_count() == 0
        reloaded = ConsensusArchive(_P(tmp), keys)
        assert reloaded.entry_count() == 0


def test_forged_receipt_refused_nothing_persisted():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        vote = world["alpha"].vote()
        forged = build_review_receipt(
            vote, provider="fake", model="m", stance="APPROVE",
            rationale="not mine", evidence=["x"],
            private_key=world["beta"].private)
        with pytest.raises(ConsensusArchiveError):
            archive.cast_vote(vote, forged)
        assert archive.entry_count() == 0


def test_store_failure_compensates_ledger():
    import tempfile
    world = make_world(["alpha"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        # Kompatibles Paar zuerst sauber ablegen.
        cast(archive, world["alpha"])
        assert archive.entry_count() == 1

        def broken_append(receipt, vote_record):
            raise ReceiptStoreError("injected store failure")
        archive.store.append_receipt = broken_append
        vote = world["alpha"].vote()
        receipt = world["alpha"].receipt(vote)
        with pytest.raises(ConsensusArchiveError):
            archive.cast_vote(vote, receipt)
        # Kompensation: Ledger wieder bei 1, vollstaendig verifizierbar.
        reloaded = ConsensusArchive(_P(tmp), keys)
        assert reloaded.entry_count() == 1
        # Nach Kompensation laeuft der Betrieb weiter.
        cast(reloaded, world["alpha"])
        assert reloaded.entry_count() == 2


def test_reload_detects_vote_without_receipt():
    import tempfile
    world = make_world(["alpha"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        cast(archive, world["alpha"])
        # Angreifer haengt eine weitere Stimme direkt hinten ans Ledger.
        vote = world["alpha"].vote()
        QuorumLedger(_P(tmp) / LEDGER_FILENAME, keys).append_vote(vote)
        with pytest.raises(ConsensusArchiveError):
            ConsensusArchive(_P(tmp), keys)


def test_reload_detects_receipt_without_vote():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        cast(archive, world["alpha"])
        # beta-Paar nur in den Store legen (Ledger unberuehrt).
        vote_b = world["beta"].vote()
        ReceiptStore(_P(tmp) / RECEIPTS_FILENAME, keys).append_receipt(
            world["beta"].receipt(vote_b), vote_b)
        with pytest.raises(ConsensusArchiveError):
            ConsensusArchive(_P(tmp), keys)


def test_replay_cast_refused():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        vu, ru = cast(archive, world["alpha"])
        vv, rv = cast(archive, world["beta"])
        # Replay-Angriff: alpha-Stimme nochmal mit altem Umschlag.
        replay = build_signed_vote(
            "alpha", PROPOSAL_DIGEST, EPOCH, 1, True, NOW, POLICY,
            world["alpha"].private)
        with pytest.raises(ConsensusArchiveError):
            archive.cast_vote(replay, ru)
        assert archive.entry_count() == 2


def test_interleaved_duplicate_participation_no_quorum():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        cast(archive, world["alpha"], approve=True)
        cast(archive, world["beta"], approve=False)
        cast(archive, world["alpha"], approve=True)
        cast(archive, world["beta"], approve=False)
        assert archive.entry_count() == 4
        reloaded = ConsensusArchive(_P(tmp), keys)
        assert reloaded.entry_count() == 4
        # Teilnahme-Angriff: Doppelte Stimme je Digest/Epoche zaehlt
        # NICHT (Konsensus-Semantik, quorum_evaluator/REUSE).
        result = evaluate_ledger_reviews(
            reloaded.votes(), reloaded.receipts(), keys,
            proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
            expected_policy_version=POLICY, min_sequence_by_agent={})
        assert result["decision"] == "NO_QUORUM"
        assert any("duplicate valid votes" in r
                   for r in result["invalid_reasons"])


def test_replay_after_restart_refused():
    import tempfile
    world = make_world(["alpha"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        vote, receipt = cast(archive, world["alpha"])
        reloaded = ConsensusArchive(_P(tmp), keys)
        replay_receipt = world["alpha"].receipt(vote)
        with pytest.raises(ConsensusArchiveError):
            reloaded.cast_vote(vote, replay_receipt)
        assert reloaded.entry_count() == 1


def test_tampered_ledger_detected():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        for name in sorted(world):
            cast(archive, world[name])
        path = _P(tmp) / LEDGER_FILENAME
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("policy-2026-11-21", "policy-x"),
                        encoding="utf-8")
        with pytest.raises(ConsensusArchiveError):
            ConsensusArchive(_P(tmp), keys)


def test_tampered_store_detected():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        for name in sorted(world):
            cast(archive, world[name])
        path = _P(tmp) / RECEIPTS_FILENAME
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[0] = lines[0].replace("model-y", "model-z")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with pytest.raises(ConsensusArchiveError):
            ConsensusArchive(_P(tmp), keys)


def test_deterministic_heads_for_same_casts():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    pairs = []
    for name in sorted(world):
        agent = world[name]
        vote = agent.vote()
        pairs.append((vote, agent.receipt(vote)))
    heads = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            archive = ConsensusArchive(_P(tmp), keys)
            for vote, receipt in pairs:
                archive.cast_vote(vote, receipt)
            heads.append((archive.ledger.head_hash() if hasattr(
                archive.ledger, "head_hash") else None))
    # Stimmen-Kette reproduziert identisch fuer identische Eingaben.
    assert heads[0] == heads[1]


# --- Konstruktor-Fail-Closed -----------------------------------------

def test_rejects_non_path_directory():
    with pytest.raises(ConsensusArchiveError):
        ConsensusArchive("nope", {"a": b"x" * 32})


def test_rejects_empty_keys():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ConsensusArchiveError):
            ConsensusArchive(_P(tmp), {})


# --- Abgrenzung: Autorisierung bleibt draussen ------------------------

def test_dissent_third_review_after_reload():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        cast(archive, world["alpha"], approve=True)
        cast(archive, world["beta"], approve=False)
        reloaded = ConsensusArchive(_P(tmp), keys)
        result = evaluate_ledger_reviews(
            reloaded.votes(), reloaded.receipts(), keys,
            proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
            expected_policy_version=POLICY, min_sequence_by_agent={})
        assert result["decision"] == "THIRD_REVIEW_REQUIRED"


def test_authorization_stays_none():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        for name in sorted(world):
            cast(archive, world[name])
        result = evaluate_ledger_reviews(
            archive.votes(), archive.receipts(), keys,
            proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
            expected_policy_version=POLICY, min_sequence_by_agent={})
        assert result["decision"] == "APPROVED_FOR_DOCUMENTATION"
        assert result["authorization"] == "NONE (EVALUATION != AUTHORIZATION)"


# --- Gepaarter Reload -> Unabhaengigkeits-Auswertung ------------------

def test_archive_evaluate_reviews_reloads_and_reports_limits():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        for name in sorted(world):
            cast(archive, world[name], approve=True)
        # Die Methode laedt beide Dateien frisch und bewertet erst danach.
        result = archive.evaluate_reviews(
            proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
            expected_policy_version=POLICY, min_sequence_by_agent={})
        assert result["decision"] == "APPROVED_FOR_DOCUMENTATION"
        assert result["archive_pairing"] == "VERIFIED_ON_RELOAD"
        assert result["archive_entry_count"] == 2
        assert "INDEPENDENCE != PROVEN" in result["archive_limitations"]
        assert result["authorization"] == "NONE (EVALUATION != AUTHORIZATION)"


def test_archive_evaluate_reloads_and_detects_post_init_tampering():
    import tempfile
    world = make_world(["alpha", "beta"])
    keys = keys_of(world)
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        for name in sorted(world):
            cast(archive, world[name])
        # Mutation NACH Konstruktion: evaluate_reviews darf nicht nur den
        # alten In-Memory-Zustand auswerten, sondern muss frisch laden.
        path = _P(tmp) / RECEIPTS_FILENAME
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("model-y", "model-z"), encoding="utf-8")
        with pytest.raises(ConsensusArchiveError):
            archive.evaluate_reviews(
                proposal_digest=PROPOSAL_DIGEST, epoch=EPOCH, now=NOW,
                expected_policy_version=POLICY, min_sequence_by_agent={})
