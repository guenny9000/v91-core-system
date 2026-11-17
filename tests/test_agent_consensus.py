import hashlib
import pytest

from controller.agent_consensus import Decision, evaluate_consensus, sign_vote

KEYS = {"node-a": b"a" * 32, "node-b": b"b" * 32, "node-c": b"c" * 32}
DIGEST = hashlib.sha256(b"bounded test proposal").hexdigest()


def vote(agent, approve=True, sequence=1):
    return sign_vote(agent_id=agent, proposal_digest=DIGEST, epoch=7,
                     sequence=sequence, issued_at=1000, approve=approve,
                     agent_key=KEYS[agent])


def evaluate(votes, **kwargs):
    return evaluate_consensus(
        votes, member_keys=KEYS, proposal_digest=DIGEST, epoch=7, now=1000,
        min_sequence_by_agent={"node-a": 0, "node-b": 0, "node-c": 0}, **kwargs
    )


def test_majority_approval():
    assert evaluate([vote("node-a"), vote("node-b")]).decision is Decision.ACCEPT


def test_majority_rejection():
    assert evaluate([vote("node-a", False), vote("node-b", False)]).decision is Decision.REJECT


def test_single_vote_is_no_quorum():
    assert evaluate([vote("node-a")]).decision is Decision.NO_QUORUM


def test_tampered_vote_does_not_count():
    original = vote("node-a")
    tampered = type(original)(**{**original.__dict__, "approve": False})
    result = evaluate([tampered, vote("node-b")])
    assert result.decision is Decision.NO_QUORUM
    assert any("signature verification failed" in item for item in result.invalid_votes)


def test_duplicate_voter_counts_once():
    result = evaluate([vote("node-a"), vote("node-a", sequence=2)])
    assert result.valid_approvals == 1
    assert any("duplicate vote" in item for item in result.invalid_votes)


def test_stale_sequence_rejected():
    result = evaluate([vote("node-a")], min_sequence_by_agent={
        "node-a": 1, "node-b": 0, "node-c": 0
    })
    assert result.decision is Decision.NO_QUORUM


def test_wrong_epoch_rejected():
    original = vote("node-a")
    wrong = type(original)(**{**original.__dict__, "epoch": 8})
    assert evaluate([wrong]).decision is Decision.NO_QUORUM


def test_expired_vote_rejected():
    result = evaluate_consensus(
        [vote("node-a")], member_keys=KEYS, proposal_digest=DIGEST, epoch=7,
        now=2000, min_sequence_by_agent={"node-a": 0, "node-b": 0, "node-c": 0},
        allowed_clock_skew_seconds=30
    )
    assert result.decision is Decision.NO_QUORUM


def test_short_key_rejected():
    with pytest.raises(ValueError):
        sign_vote(agent_id="node-a", proposal_digest=DIGEST, epoch=1,
                  sequence=1, issued_at=1, approve=True, agent_key=b"short")


def test_invalid_quorum_rejected():
    with pytest.raises(ValueError):
        evaluate([vote("node-a")], quorum=4)
