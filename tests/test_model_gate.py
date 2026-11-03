import pytest

from controller.model_gate import ModelGateError, evaluate_server_model


def available_model(**overrides):
    model = {
        "available": True,
        "authorization_valid": True,
        "safety_check": "VERIFIED",
        "metrics": None,
    }
    model.update(overrides)
    return model


def test_unavailable_model_is_blocked():
    assert evaluate_server_model(available_model(available=False)).decision == "BLOCKED_UNAVAILABLE"


def test_string_availability_is_not_true():
    assert evaluate_server_model(available_model(available="yes")).decision == "BLOCKED_UNAVAILABLE"


def test_unauthorized_model_is_blocked():
    assert evaluate_server_model(available_model(authorization_valid=False)).decision == "BLOCKED_UNAUTHORIZED"


def test_failed_safety_is_blocked():
    result = evaluate_server_model(available_model(safety_check="FAILED"))
    assert result.decision == "BLOCKED_SAFETY_FAILED"


def test_unknown_safety_is_blocked_fail_closed():
    # The charter: safety UNKNOWN is not PASS.
    result = evaluate_server_model(available_model(safety_check="UNKNOWN"))
    assert result.decision == "BLOCKED_SAFETY_UNKNOWN"
    assert result.safety_status == "UNKNOWN"


def test_invalid_safety_value_raises():
    with pytest.raises(ModelGateError):
        evaluate_server_model(available_model(safety_check="VERMUTLICH_OK"))


def test_missing_safety_key_raises():
    model = available_model()
    del model["safety_check"]
    with pytest.raises(ModelGateError):
        evaluate_server_model(model)


def test_metrics_none_allows_with_honest_unknown():
    result = evaluate_server_model(available_model(metrics=None))
    assert result.decision == "ALLOW_WITHOUT_METRICS"
    assert result.metrics_status == "UNKNOWN"
    assert result.performance_status == "UNVERIFIED"
    assert result.safety_status == "VERIFIED"


def test_metrics_present_allows_with_metrics():
    result = evaluate_server_model(available_model(metrics={"energy": 1.2}))
    assert result.decision == "ALLOW_WITH_METRICS"
    assert result.performance_status == "VERIFIED"


def test_metrics_wrong_type_raises():
    with pytest.raises(ModelGateError):
        evaluate_server_model(available_model(metrics="fast"))


def test_evaluation_does_not_mutate_input():
    model = available_model()
    snapshot = dict(model)
    evaluate_server_model(model)
    assert model == snapshot


def test_non_mapping_input_raises():
    with pytest.raises(ModelGateError):
        evaluate_server_model("model")
