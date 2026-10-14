import importlib.util
from pathlib import Path
import sys
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

MODULE_PATH = Path(__file__).resolve().parents[1] / "controller" / "cooperation.py"
SPEC = importlib.util.spec_from_file_location("v91_cooperation_crypto_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Cannot load V91 cooperation module from {MODULE_PATH}")
cooperation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cooperation
SPEC.loader.exec_module(cooperation)


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


def sign_offer(private_key, offer):
    message = cooperation.canonical_offer_bytes(offer)
    if message is None:
        raise ValueError("Offer cannot be canonically serialized")
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return public_key, private_key.sign(message)


class Ed25519PeerOfferTests(unittest.TestCase):
    def setUp(self):
        self.private_key = ed25519.Ed25519PrivateKey.generate()

    def test_valid_ed25519_signature_allows_scoped_read_only_offer(self):
        offer = valid_offer()
        public_key, signature = sign_offer(self.private_key, offer)
        decision = cooperation.evaluate_signed_peer_offer(
            offer, public_key_bytes=public_key, signature_bytes=signature, now_epoch=1000
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.allowed_capabilities, ("describe", "share_public_metadata"))

    def test_modified_offer_is_denied_after_signature_creation(self):
        offer = valid_offer()
        public_key, signature = sign_offer(self.private_key, offer)
        offer["consent"] = False
        decision = cooperation.evaluate_signed_peer_offer(
            offer, public_key_bytes=public_key, signature_bytes=signature, now_epoch=1000
        )
        self.assertFalse(decision.allowed)
        self.assertIn("PEER_SIGNATURE_NOT_VERIFIED", decision.reasons)

    def test_invalid_signature_fails_closed(self):
        offer = valid_offer()
        public_key, _ = sign_offer(self.private_key, offer)
        decision = cooperation.evaluate_signed_peer_offer(
            offer, public_key_bytes=public_key, signature_bytes=b"not-a-valid-signature", now_epoch=1000
        )
        self.assertFalse(decision.allowed)
        self.assertIn("PEER_SIGNATURE_NOT_VERIFIED", decision.reasons)

    def test_wrong_public_key_fails_closed(self):
        offer = valid_offer()
        _, signature = sign_offer(self.private_key, offer)
        other_key = ed25519.Ed25519PrivateKey.generate().public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        decision = cooperation.evaluate_signed_peer_offer(
            offer, public_key_bytes=other_key, signature_bytes=signature, now_epoch=1000
        )
        self.assertFalse(decision.allowed)
        self.assertIn("PEER_SIGNATURE_NOT_VERIFIED", decision.reasons)

    def test_expired_but_correctly_signed_offer_is_denied(self):
        offer = valid_offer(expires_at=999)
        public_key, signature = sign_offer(self.private_key, offer)
        decision = cooperation.evaluate_signed_peer_offer(
            offer, public_key_bytes=public_key, signature_bytes=signature, now_epoch=1000
        )
        self.assertFalse(decision.allowed)
        self.assertIn("OFFER_EXPIRED", decision.reasons)

    def test_unknown_capability_is_denied_even_with_valid_signature(self):
        offer = valid_offer(requested_capabilities=["describe", "train_remote_model"])
        public_key, signature = sign_offer(self.private_key, offer)
        decision = cooperation.evaluate_signed_peer_offer(
            offer, public_key_bytes=public_key, signature_bytes=signature, now_epoch=1000
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(any(reason.startswith("UNKNOWN_CAPABILITIES_REQUESTED") for reason in decision.reasons))

    def test_unserializable_offer_fails_closed(self):
        offer = valid_offer(untrusted_extra=object())
        decision = cooperation.evaluate_signed_peer_offer(
            offer, public_key_bytes=b"invalid", signature_bytes=b"invalid", now_epoch=1000
        )
        self.assertFalse(decision.allowed)
        self.assertIn("PEER_SIGNATURE_NOT_VERIFIED", decision.reasons)


if __name__ == "__main__":
    unittest.main()
