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
    options = {
        "member_keys": KEYS,
        "proposal_digest": DIGEST,
        "epoch": 7,
        "now": 1000,
        "min_sequence_by_agent": {"node-a": 0, "node-b": 0, "node-c": 0},
    }
    options.update(kwargs)
    return evaluate_consensus(votes, **options)


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


def test_boolean_epoch_is_rejected_even_when_equal_to_integer():
    original = sign_vote(agent_id="node-a", proposal_digest=DIGEST, epoch=1,
                         sequence=1, issued_at=1000, approve=True, agent_key=KEYS["node-a"])
    malformed = type(original)(**{**original.__dict__, "epoch": True})
    result = evaluate([malformed], epoch=1)
    assert result.decision is Decision.NO_QUORUM


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


@pytest.mark.parametrize("bad_keys", [
    {"node-a": None},
    {1: b"x" * 32},
    {"node-a": "x" * 32},
])
def test_malformed_member_configuration_rejected(bad_keys):
    with pytest.raises(ValueError):
        evaluate_consensus(
            [], member_keys=bad_keys, proposal_digest=DIGEST, epoch=1, now=1000,
            min_sequence_by_agent={}
        )


def test_non_mapping_sequence_floors_rejected():
    with pytest.raises(ValueError):
        evaluate_consensus(
            [], member_keys=KEYS, proposal_digest=DIGEST, epoch=1, now=1000,
            min_sequence_by_agent=None
        )


def test_invalid_vote_envelope_is_counted_as_invalid():
    result = evaluate([object()])
    assert result.decision is Decision.NO_QUORUM
    assert result.invalid_votes == ("malformed vote envelope",)


def test_invalid_quorum_rejected():
    with pytest.raises(ValueError):
        evaluate([vote("node-a")], quorum=4)


def _tampered(agent):
    original = vote(agent)
    return type(original)(**{**original.__dict__, "approve": not original.approve})


def test_invalid_vote_does_not_block_later_valid_vote_from_same_agent():
    result = evaluate([_tampered("node-a"), vote("node-a"), vote("node-b")])
    assert result.decision is Decision.ACCEPT
    assert "node-a" in result.accepted_agents
    assert result.valid_approvals == 2
    assert any("signature verification failed" in item for item in result.invalid_votes)


def test_result_is_independent_of_vote_order():
    votes_forward = [_tampered("node-a"), vote("node-a"), vote("node-b")]
    votes_backward = [vote("node-b"), vote("node-a"), _tampered("node-a")]
    forward = evaluate(votes_forward)
    backward = evaluate(votes_backward)
    assert forward.decision is backward.decision is Decision.ACCEPT
    assert forward.valid_approvals == backward.valid_approvals
    assert forward.accepted_agents == backward.accepted_agents
    assert forward.invalid_votes == backward.invalid_votes


def test_duplicate_still_detected_after_valid_vote():
    # A tampered vote fails on its own merits (signature first) and therefore
    # never reaches the duplicate check; duplicate detection is proven with a
    # second fully valid vote from the same agent.
    result = evaluate([vote("node-a"), vote("node-a", sequence=2), vote("node-b")])
    assert result.decision is Decision.ACCEPT
    assert result.valid_approvals == 2
    assert any("duplicate vote" in item for item in result.invalid_votes)


def test_tampered_vote_after_valid_vote_fails_on_signature_merits():
    result = evaluate([vote("node-a"), _tampered("node-a"), vote("node-b")])
    assert result.decision is Decision.ACCEPT
    assert result.valid_approvals == 2
    assert any("signature verification failed" in item for item in result.invalid_votes)
