from ragnarok.engine import build_plan


def test_empty_inventory_is_honest_and_side_effect_free():
    result = build_plan([])
    assert result["mode"] == "read_only_proposal"
    assert result["external_systems_inspected"] is False
    assert result["actions_executed"] is False
    assert result["proposals"] == []


def test_missing_evidence_stays_unknown_and_is_prioritized():
    result = build_plan([{"name": "unseen-system", "evidence": []}])
    proposal = result["proposals"][0]
    assert proposal["action"] == "collect_evidence"
    assert proposal["priority"] == 100
    assert proposal["status"] == "PROPOSAL_ONLY"
    assert proposal["execution_performed"] is False


def test_evidence_does_not_grant_authorization():
    result = build_plan([{
        "name": "service-a",
        "evidence": ["read-only health report"],
        "authorized": False,
        "reversible": True,
        "baseline": 10,
        "measured_benefit": 1,
    }])
    assert result["proposals"][0]["action"] == "recommend_only"


def test_irreversible_change_requires_independent_review():
    result = build_plan([{
        "name": "service-b",
        "evidence": ["approved inventory record"],
        "authorized": True,
        "reversible": False,
        "baseline": 10,
        "measured_benefit": 1,
    }])
    assert result["proposals"][0]["action"] == "request_independent_review"


def test_missing_baseline_prevents_productivity_claim():
    result = build_plan([{
        "name": "service-c",
        "evidence": ["configuration snapshot"],
        "authorized": True,
        "reversible": True,
    }])
    assert result["proposals"][0]["action"] == "measure_baseline"
    assert result["status"] == "DOCUMENTED_INPUT_ONLY"


def test_fully_evidenced_candidate_still_only_gets_isolated_test():
    result = build_plan([{
        "name": "service-d",
        "evidence": ["test report", "configuration snapshot"],
        "authorized": True,
        "reversible": True,
        "baseline": {"latency_ms": 100},
        "measured_benefit": {"latency_ms": 90},
    }])
    proposal = result["proposals"][0]
    assert proposal["action"] == "isolated_test"
    assert proposal["execution_performed"] is False


def test_invalid_input_fails_closed():
    try:
        build_plan({"name": "not-a-list"})
    except TypeError:
        pass
    else:
        raise AssertionError("non-list input must be rejected")
