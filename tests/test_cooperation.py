import unittest

from controller.cooperation import evaluate_peer_offer, public_decision_record


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
    def test_valid_signed_offer_allows_only_read_only_capabilities(self):
        decision = evaluate_peer_offer(valid_offer(), signature_verified=True, now_epoch=1000)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.allowed_capabilities, ("describe", "share_public_metadata"))

    def test_missing_signature_fails_closed(self):
        decision = evaluate_peer_offer(valid_offer(), now_epoch=1000)
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

    def test_audit_record_does_not_claim_ingestion_or_execution(self):
        offer = valid_offer()
        decision = evaluate_peer_offer(offer, signature_verified=True, now_epoch=1000)
        record = public_decision_record(offer, decision)
        self.assertFalse(record["data_ingested"])
        self.assertFalse(record["remote_actions_executed"])


if __name__ == "__main__":
    unittest.main()
