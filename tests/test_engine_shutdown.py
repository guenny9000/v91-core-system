from ragnarok.engine_shutdown import plan_cleanup


def test_empty_inventory_does_not_claim_global_purge():
    result = plan_cleanup([])
    assert result["status"] == "PROPOSAL_ONLY"
    assert result["global_shutdown_performed"] is False
    assert result["real_world_changes_performed"] is False
    assert result["proposals"] == []


def test_missing_evidence_stays_unknown_even_if_authorized():
    result = plan_cleanup([{
        "target": "claimed-global-system",
        "area": "war_related_activity",
        "evidence": [],
        "authorized": True,
        "reversible": True,
    }])
    proposal = result["proposals"][0]
    assert proposal["status"] == "UNKNOWN"
    assert proposal["action"] == "collect_read_only_evidence"
    assert proposal["execution_performed"] is False
    assert result["global_shutdown_performed"] is False


def test_evidence_without_authorization_only_recommends_review():
    result = plan_cleanup([{
        "target": "service-a",
        "area": "overproduction",
        "evidence": ["read-only inventory snapshot"],
        "authorized": False,
        "reversible": True,
        "baseline": 10,
        "measured_impact": 2,
    }])
    assert result["proposals"][0]["action"] == "recommend_for_human_review"


def test_irreversible_change_needs_independent_review():
    result = plan_cleanup([{
        "target": "service-b",
        "area": "luxury_overhead",
        "evidence": ["configuration snapshot"],
        "authorized": True,
        "reversible": False,
        "baseline": 10,
        "measured_impact": 2,
    }])
    assert result["proposals"][0]["action"] == "request_independent_review"


def test_measured_and_authorized_candidate_still_only_gets_isolated_test():
    result = plan_cleanup([{
        "target": "service-c",
        "area": "redundant_waiting",
        "evidence": ["test report"],
        "authorized": True,
        "reversible": True,
        "baseline": {"cpu_percent": 10},
        "measured_impact": {"cpu_percent": 8},
    }])
    proposal = result["proposals"][0]
    assert proposal["action"] == "propose_isolated_test"
    assert proposal["status"] == "PROPOSAL_ONLY"
    assert proposal["execution_performed"] is False


def test_invalid_input_fails_closed():
    try:
        plan_cleanup({"target": "not-a-list"})
    except TypeError:
        pass
    else:
        raise AssertionError("non-list input must be rejected")
