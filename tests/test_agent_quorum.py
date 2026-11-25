import hashlib

from controller.agent_consensus import Decision, Vote, sign_vote
from controller.agent_quorum import ReviewRequest, proposal_digest, review_with_quorum

KEYS = {"agent-a": b"a" * 32, "agent-b": b"b" * 32, "agent-c": b"c" * 32}
IDS = ("agent-a", "agent-b", "agent-c")
REQUEST = ReviewRequest(
    proposal={"action": "local_read_only_check", "scope": "test-fixture"},
    policy_version="v1",
    evidence=({"id": "fixture-1", "source": "synthetic"},),
    deadline=1200,
    epoch=4,
    now=1000,
)
FLOORS = {agent: 0 for agent in IDS}


def adapter(agent_id, approve=True, sequence=1, issued_at=None):
    def review(digest, epoch, policy_version, evidence, deadline):
        assert policy_version == "v1"
        assert evidence == REQUEST.evidence
        assert deadline == REQUEST.deadline
        return sign_vote(
            agent_id=agent_id, proposal_digest=digest, epoch=epoch,
            sequence=sequence, issued_at=REQUEST.now if issued_at is None else issued_at, approve=approve,
            agent_key=KEYS[agent_id],
        )
    return review


def run(reviewers, now_provider=lambda: REQUEST.now):
    return review_with_quorum(
        REQUEST, reviewer_ids=IDS, reviewers=reviewers,
        member_keys=KEYS, min_sequence_by_agent=FLOORS,
        now_provider=now_provider,
    )


def test_digest_changes_when_policy_changes():
    changed = ReviewRequest(
        proposal=REQUEST.proposal, policy_version="v2",
        evidence=REQUEST.evidence, deadline=REQUEST.deadline,
        epoch=REQUEST.epoch, now=REQUEST.now,
    )
    assert proposal_digest(REQUEST) != proposal_digest(changed)


def test_two_matching_approvals_do_not_call_third():
    result = run({
        "agent-a": adapter("agent-a", True),
        "agent-b": adapter("agent-b", True),
        "agent-c": adapter("agent-c", True),
    })
    assert result.decision is Decision.ACCEPT
    assert result.votes_requested == ("agent-a", "agent-b")
    assert result.execution_permitted is False


def test_disagreement_requests_third_and_uses_majority():
    result = run({
        "agent-a": adapter("agent-a", True),
        "agent-b": adapter("agent-b", False),
        "agent-c": adapter("agent-c", True),
    })
    assert result.decision is Decision.ACCEPT
    assert result.votes_requested == IDS


def test_disagreement_without_third_quorum_fails_closed():
    def unavailable(*args):
        raise TimeoutError("synthetic provider timeout")
    result = run({
        "agent-a": adapter("agent-a", True),
        "agent-b": adapter("agent-b", False),
        "agent-c": unavailable,
    })
    assert result.decision is Decision.NO_QUORUM
    assert result.votes_requested == IDS
    assert result.execution_permitted is False


def test_invalid_first_vote_causes_third_review():
    def tampered(*args):
        valid = adapter("agent-a", True)(*args)
        return Vote(**{**valid.__dict__, "approve": False})
    result = run({
        "agent-a": tampered,
        "agent-b": adapter("agent-b", True),
        "agent-c": adapter("agent-c", True),
    })
    assert result.decision is Decision.ACCEPT
    assert result.votes_requested == IDS


def test_same_identity_cannot_fill_multiple_slots():
    reviewers = {
        "agent-a": adapter("agent-a", True),
        "agent-b": adapter("agent-a", True),
        "agent-c": adapter("agent-c", True),
    }
    result = run(reviewers)
    assert result.decision is Decision.NO_QUORUM
    assert result.votes_requested == IDS


def test_bad_reviewer_configuration_rejected():
    try:
        review_with_quorum(
            REQUEST, reviewer_ids=("agent-a", "agent-a", "agent-c"),
            reviewers={}, member_keys=KEYS, min_sequence_by_agent=FLOORS,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate reviewer identities must fail closed")


def test_deadline_expired_before_first_call_contacts_no_provider():
    called = []
    def provider(agent):
        def call(*args):
            called.append(agent)
            return adapter(agent)(*args)
        return call
    result = run({agent: provider(agent) for agent in IDS}, now_provider=lambda: REQUEST.deadline)
    assert result.decision is Decision.NO_QUORUM
    assert result.votes_requested == ()
    assert result.votes_received == 0
    assert result.deadline_expired is True
    assert called == []


def test_response_returning_at_deadline_is_discarded_and_third_is_not_called():
    times = iter([1198, 1199, 1199, 1200, 1200])
    reviewers = {
        "agent-a": adapter("agent-a", True, issued_at=1198),
        "agent-b": adapter("agent-b", True, issued_at=1199),
        "agent-c": adapter("agent-c", True, issued_at=1199),
    }
    result = run(reviewers, now_provider=lambda: next(times))
    assert result.decision is Decision.NO_QUORUM
    assert result.votes_requested == ("agent-a", "agent-b")
    assert result.votes_received == 1
    assert result.deadline_expired is True


def test_votes_received_before_deadline_remain_evaluable_after_deadline():
    times = iter([1198, 1198, 1198, 1199, 1201])
    reviewers = {
        "agent-a": adapter("agent-a", True, issued_at=1198),
        "agent-b": adapter("agent-b", True, issued_at=1198),
        "agent-c": adapter("agent-c", True, issued_at=1198),
    }
    result = run(reviewers, now_provider=lambda: next(times))
    assert result.decision is Decision.ACCEPT
    assert result.votes_requested == ("agent-a", "agent-b")
    assert result.votes_received == 2
    assert result.deadline_expired is True


def test_signed_vote_issued_at_deadline_is_rejected():
    reviewers = {
        "agent-a": adapter("agent-a", True, issued_at=REQUEST.deadline),
        "agent-b": adapter("agent-b", True, issued_at=REQUEST.deadline),
        "agent-c": adapter("agent-c", True, issued_at=REQUEST.deadline),
    }
    result = run(reviewers)
    assert result.decision is Decision.NO_QUORUM
    assert result.votes_received == 0


def test_fresh_clock_must_not_move_backwards():
    times = iter([1001, 1000])
    try:
        run({agent: adapter(agent) for agent in IDS}, now_provider=lambda: next(times))
    except ValueError as exc:
        assert "moved backwards" in str(exc)
    else:
        raise AssertionError("backwards clock must fail closed")
