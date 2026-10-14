import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "controller" / "cooperation.py"
SPEC = importlib.util.spec_from_file_location("v91_cooperation", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Cannot load V91 cooperation module from {MODULE_PATH}")
cooperation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cooperation
SPEC.loader.exec_module(cooperation)

# These tests isolate policy behavior. Public callers must use the signed API.
evaluate_peer_offer = cooperation._evaluate_peer_offer_policy
public_evaluate_peer_offer = cooperation.evaluate_peer_offer
public_decision_record = cooperation.public_decision_record


def valid_offer(**overrides):
    offer = {
        "protocol_version": "v1",
        "peer_id": "peer-example",
        "consent": True,
        "share_public_metadata": True,
        "requested_capabilities": ["describe", "share_public_metadata"],
        "expires_at": 2000,
    }
    offer.update(overrides)
    return offer


class CooperativeHandshakeTests(unittest.TestCase):
    def test_public_entry_point_denies_without_cryptographic_proof(self):
        decision = public_evaluate_peer_offer(valid_offer(), now_epoch=1000)
        self.assertFalse(decision.allowed)
        self.assertIn("PEER_SIGNATURE_NOT_VERIFIED", decision.reasons)

    def test_valid_verified_offer_policy_allows_only_read_only_capabilities(self):
        decision = evaluate_peer_offer(valid_offer(), signature_verified=True, now_epoch=1000)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.allowed_capabilities, ("describe", "share_public_metadata"))

    def test_missing_signature_fails_closed(self):
        decision = evaluate_peer_offer(valid_offer(), signature_verified=False, now_epoch=1000)
        self.assertFalse(decision.allowed)
        self.assertIn("PEER_SIGNATURE_NOT_VERIFIED", decision.reasons)

    def test_no_consent_denied(self):
        decision = evaluate_peer_offer(valid_offer(consent=False), signature_verified=True, now_epoch=1000)
        self.assertFalse(decision.allowed)
        self.assertIn("EXPLICIT_CONSENT_MISSING", decision.reasons)

    def test_remote_execution_is_never_allowed(self):
        decision = evaluate_peer_offer(
            valid_offer(requested_capabilities=["describe", "execute"]),
            signature_verified=True,
            now_epoch=1000,
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(any(reason.startswith("FORBIDDEN_CAPABILITIES_REQUESTED") for reason in decision.reasons))

    def test_expired_offer_denied(self):
        decision = evaluate_peer_offer(valid_offer(expires_at=999), signature_verified=True, now_epoch=1000)
        self.assertFalse(decision.allowed)
        self.assertIn("OFFER_EXPIRED", decision.reasons)

    def test_default_clock_path_denies_expired_offer(self):
        with patch("v91_cooperation.time.time", return_value=1000):
            decision = evaluate_peer_offer(valid_offer(expires_at=999), signature_verified=True)
        self.assertFalse(decision.allowed)
        self.assertIn("OFFER_EXPIRED", decision.reasons)

    def test_default_clock_path_uses_current_time(self):
        with patch("v91_cooperation.time.time", return_value=1000):
            decision = evaluate_peer_offer(valid_offer(), signature_verified=True)
        self.assertTrue(decision.allowed)

    def test_unavailable_clock_fails_closed(self):
        with patch("v91_cooperation.time.time", side_effect=OSError("clock unavailable")):
            decision = evaluate_peer_offer(valid_offer(), signature_verified=True)
        self.assertFalse(decision.allowed)
        self.assertIn("CURRENT_TIME_UNAVAILABLE", decision.reasons)

    def test_boolean_expiry_is_not_accepted_as_integer(self):
        decision = evaluate_peer_offer(valid_offer(expires_at=True), signature_verified=True, now_epoch=0)
        self.assertFalse(decision.allowed)
        self.assertIn("INVALID_EXPIRY", decision.reasons)

    def test_audit_record_does_not_claim_ingestion_or_execution(self):
        offer = valid_offer()
        decision = evaluate_peer_offer(offer, signature_verified=True, now_epoch=1000)
        record = public_decision_record(offer, decision)
        self.assertFalse(record["data_ingested"])
        self.assertFalse(record["remote_actions_executed"])


if __name__ == "__main__":
    unittest.main()
