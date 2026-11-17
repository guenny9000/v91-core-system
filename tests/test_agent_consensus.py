[object Object],[object Object]
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
    result = evaluate([vote("node-a"), _tampered("node-a"), vote("node-b")])
    assert result.decision is Decision.ACCEPT
    assert result.valid_approvals == 2
    assert any("duplicate vote" in item for item in result.invalid_votes)
