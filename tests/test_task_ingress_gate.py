import hashlib
import hmac
import json

import pytest

from controller.task_ingress_gate import TaskIngressGate


KEY = b"test-only-provider-secret-at-least-32-bytes"
PROVIDER = "provider-test"


class TestKeyProvider:
    def get_active_key(self, provider_id: str) -> bytes | None:
        return KEY if provider_id == PROVIDER else None


@pytest.fixture
def gate():
    return TaskIngressGate(TestKeyProvider())


def signed(payload):
    body = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hmac.new(KEY, body, hashlib.sha256).hexdigest()


def task(classification="HUMANITARIAN", sector="WATER", description="civilian supply"):
    return {
        "task_id": "task-001",
        "provider_id": PROVIDER,
        "purpose": {
            "classification": classification,
            "sector": sector,
            "description": description,
        },
    }


def test_bad_signature_rejected(gate):
    result = gate.validate(task(), "0" * 64)
    assert result.status == "REJECT_UNAUTHORIZED"
    assert result.execution_authorized is False


def test_signed_restricted_domain_blocked(gate):
    payload = task("TARGETING", "WATER", "humanitarian aid")
    result = gate.validate(payload, signed(payload))
    assert result.status == "BLOCK"
    assert result.execution_authorized is False


def test_signed_critical_supply_requires_independent_review(gate):
    payload = task("CRITICAL_SUPPLY_PROTECTION", "MEDICINE")
    result = gate.validate(payload, signed(payload))
    assert result.status == "REVIEW_REQUIRED"
    assert result.execution_authorized is False


def test_signed_civilian_noncritical_domain_still_does_not_authorize(gate):
    payload = task("EDUCATION", "OTHER")
    result = gate.validate(payload, signed(payload))
    assert result.status == "REVIEW_REQUIRED"
    assert result.execution_authorized is False


def test_missing_or_unknown_domain_fails_closed(gate):
    payload = task("NOT_A_DOMAIN", "OTHER")
    result = gate.validate(payload, signed(payload))
    assert result.status == "REVIEW_REQUIRED"
    assert result.use_domain == "UNKNOWN"


def test_signature_binds_every_payload_field(gate):
    payload = task("HUMANITARIAN", "WATER", "approved")
    signature = signed(payload)
    payload["purpose"]["description"] = "changed after signing"
    result = gate.validate(payload, signature)
    assert result.status == "REJECT_UNAUTHORIZED"


def test_unavailable_provider_key_rejected(gate):
    payload = task()
    payload["provider_id"] = "unknown-provider"
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    signature = hmac.new(KEY, body, hashlib.sha256).hexdigest()
    result = gate.validate(payload, signature)
    assert result.status == "REJECT_UNAUTHORIZED"


def test_non_json_values_rejected(gate):
    payload = task()
    payload["unexpected"] = float("nan")
    result = gate.validate(payload, "0" * 64)
    assert result.status == "REJECT_INVALID"
