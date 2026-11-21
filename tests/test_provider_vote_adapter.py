import hashlib

import pytest

from controller.agent_consensus import Vote, sign_vote
from controller.provider_vote_adapter import (
    Proposal, Provider, collect_provider_votes,
)


DIGEST = hashlib.sha256(b"immutable proposal").hexdigest()
PROPOSAL = Proposal(DIGEST, 4)
KEY_A = b"a" * 32
KEY_B = b"b" * 32


def signed(agent, key, proposal=PROPOSAL):
    return sign_vote(
        agent_id=agent,
        proposal_digest=proposal.digest,
        epoch=proposal.epoch,
        sequence=1,
        issued_at=100,
        approve=True,
        agent_key=key,
    )


def test_collects_independently_signed_votes_without_executing_actions():
    calls = []
    providers = [
        Provider("agent-a", "boundary-a", lambda p: calls.append("a") or signed("agent-a", KEY_A, p)),
        Provider("agent-b", "boundary-b", lambda p: calls.append("b") or signed("agent-b", KEY_B, p)),
    ]
    batch = collect_provider_votes(PROPOSAL, providers)
    assert calls == ["a", "b"]
    assert [vote.agent_id for vote in batch.votes] == ["agent-a", "agent-b"]
    assert batch.failures == ()


def test_provider_exception_is_fail_closed():
    providers = [
        Provider("agent-a", "boundary-a", lambda p: (_ for _ in ()).throw(TimeoutError())),
        Provider("agent-b", "boundary-b", lambda p: signed("agent-b", KEY_B, p)),
    ]
    batch = collect_provider_votes(PROPOSAL, providers)
    assert [vote.agent_id for vote in batch.votes] == ["agent-b"]
    assert batch.failures == ("agent-a: provider error: TimeoutError",)


def test_wrong_signed_identity_is_rejected():
    batch = collect_provider_votes(
        PROPOSAL,
        [Provider("agent-a", "boundary-a", lambda p: signed("agent-b", KEY_B, p))],
    )
    assert batch.votes == ()
    assert batch.failures == ("agent-a: signed agent identity mismatch",)


def test_wrong_proposal_is_rejected():
    other = Proposal(hashlib.sha256(b"other").hexdigest(), 4)
    batch = collect_provider_votes(
        PROPOSAL,
        [Provider("agent-a", "boundary-a", lambda p: signed("agent-a", KEY_A, other))],
    )
    assert batch.votes == ()
    assert batch.failures == ("agent-a: proposal identity mismatch",)


def test_duplicate_agent_or_independence_boundary_is_rejected():
    same_agent = [
        Provider("agent-a", "boundary-a", lambda p: signed("agent-a", KEY_A, p)),
        Provider("agent-a", "boundary-b", lambda p: signed("agent-a", KEY_A, p)),
    ]
    same_boundary = [
        Provider("agent-a", "shared", lambda p: signed("agent-a", KEY_A, p)),
        Provider("agent-b", "shared", lambda p: signed("agent-b", KEY_B, p)),
    ]
    with pytest.raises(ValueError, match="duplicate agent_id"):
        collect_provider_votes(PROPOSAL, same_agent)
    with pytest.raises(ValueError, match="duplicate independence_id"):
        collect_provider_votes(PROPOSAL, same_boundary)


def test_invalid_provider_configuration_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        collect_provider_votes(PROPOSAL, [])
    with pytest.raises(ValueError, match="callable"):
        collect_provider_votes(PROPOSAL, [Provider("agent-a", "boundary-a", None)])


def test_non_vote_response_is_not_approval():
    batch = collect_provider_votes(
        PROPOSAL, [Provider("agent-a", "boundary-a", lambda p: {"approve": True})]
    )
    assert batch.votes == ()
    assert batch.failures == ("agent-a: returned value is not a Vote",)
