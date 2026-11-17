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


def test_duplicate_valid_votes_exclude_that_voter():
    result = evaluate([vote("node-a"), vote("node-a", sequence=2)])
    assert result.valid_approvals == 0
    assert result.accepted_agents == ()
    assert any("duplicate valid votes" in item for item in result.invalid_votes)


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



def test_invalid_vote_does_not_block_later_valid_vote_from_same_agent():
    valid = vote("node-a")
    tampered = type(valid)(**{**valid.__dict__, "approve": False})
    result = evaluate([tampered, valid, vote("node-b")])
    assert result.decision is Decision.ACCEPT
    assert result.valid_approvals == 2


def test_multiple_valid_votes_from_one_agent_are_excluded_independent_of_order():
    approval = vote("node-a", True, sequence=1)
    rejection = vote("node-a", False, sequence=2)
    for ordered in ([approval, rejection, vote("node-b")],
                    [rejection, approval, vote("node-b")]):
        result = evaluate(ordered)
        assert result.valid_approvals == 1
        assert result.valid_rejections == 0
        assert result.accepted_agents == ("node-b",)
        assert result.decision is Decision.NO_QUORUM
        assert any("duplicate valid votes" in item for item in result.invalid_votes)


def test_negative_issued_at_is_rejected():
    original = vote("node-a")
    malformed = type(original)(**{**original.__dict__, "issued_at": -1})
    result = evaluate([malformed], now=0, allowed_clock_skew_seconds=2000)
    assert result.decision is Decision.NO_QUORUM
    assert any("timestamp outside allowed window" in item for item in result.invalid_votes)
