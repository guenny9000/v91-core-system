#!/usr/bin/env python3
"""Tests for controller/signed_heartbeat.py (Issue #37, items 2+3+5+6).

Fail-closed expectations: every reject carries explicit evidence
flags; a nonce is burned only after a signature check passed; the
verification key never comes from the envelope.
"""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller import crypto_receipts
from controller.cooperation_register import Observation, Verification
from controller.cooperation_register import CooperationRegister
from controller.peer_directory import PeerDirectory
from controller.signed_heartbeat import (
    DEFAULT_MAX_SEEN_NONCES,
    DEFAULT_MAX_FUTURE_SECONDS,
    DEFAULT_TTL_SECONDS,
    HEARTBEAT_KIND,
    ORIGIN_REJECTED,
    ORIGIN_VERIFIED,
    SCHEMA_VERSION,
    SIGNATURE_FIELD,
    HeartbeatVerification,
    SignedHeartbeatError,
    SignedHeartbeatVerifier,
    build_heartbeat,
)


class _Clock:
    def __init__(self, start: float) -> None:
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _make_directory(clock):
    tmp = tempfile.TemporaryDirectory()
    directory = PeerDirectory(os.path.join(tmp.name, "peers.sqlite"),
                              now_provider=clock)
    priv, pub = crypto_receipts.generate_signing_keypair()
    directory.add_peer(peer_id="peer-a", public_key_hex=pub.hex(),
                            expires_at=int(clock()) + 3600)
    return tmp, directory, priv, pub


class BuildHeartbeatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = _Clock(1_000_000.0)
        self.tmp, self.directory, self.priv, self.pub = _make_directory(
            self.clock)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_build_heartbeat_shape_and_signature(self) -> None:
        envelope = build_heartbeat(
            self.priv, peer_id="peer-a", key_id="k1",
            metrics={"load": 0.5, "note": "ok", "count": 3},
            now_provider=self.clock)
        self.assertEqual(envelope["kind"], HEARTBEAT_KIND)
        self.assertEqual(envelope["schema_version"], SCHEMA_VERSION)
        self.assertEqual(envelope["peer_id"], "peer-a")
        self.assertEqual(envelope["key_id"], "k1")
        self.assertEqual(envelope["timestamp"], self.clock())
        self.assertEqual(8, len(bytes.fromhex(envelope["nonce"])))
        self.assertEqual(128, len(envelope[SIGNATURE_FIELD]))
        self.assertTrue(crypto_receipts.verify_record_signature(
            dict(envelope), self.pub))

    def test_build_rejects_bool_and_nan_metrics(self) -> None:
        with self.assertRaises(SignedHeartbeatError):
            build_heartbeat(self.priv, peer_id="peer-a", key_id="k1",
                           metrics={"flag": True}, now_provider=self.clock)
        with self.assertRaises(SignedHeartbeatError):
            build_heartbeat(self.priv, peer_id="peer-a", key_id="k1",
                           metrics={"bad": float("nan")},
                           now_provider=self.clock)
        with self.assertRaises(SignedHeartbeatError):
            build_heartbeat(self.priv, peer_id="peer-a", key_id="k1",
                           metrics={"empty": ""},
                           now_provider=self.clock)

    def test_build_rejects_bad_nonce_and_ids(self) -> None:
        with self.assertRaises(SignedHeartbeatError):
            build_heartbeat(self.priv, peer_id="", key_id="k1",
                           metrics={}, now_provider=self.clock)
        with self.assertRaises(SignedHeartbeatError):
            build_heartbeat(self.priv, peer_id="peer-a", key_id=" ",
                           metrics={}, now_provider=self.clock)
        for nonce in ("short", "zz" * 8, "00" * 33):
            with self.assertRaises(SignedHeartbeatError):
                build_heartbeat(self.priv, peer_id="peer-a", key_id="k1",
                               metrics={}, nonce=nonce,
                               now_provider=self.clock)

    def test_sign_record_rejects_prestamped_record(self) -> None:
        record = {"kind": HEARTBEAT_KIND}
        record[SIGNATURE_FIELD] = "00" * 64
        with self.assertRaises(crypto_receipts.CryptoReceiptError):
            crypto_receipts.sign_record(record, self.priv)


class VerifierLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = _Clock(1_000_000.0)
        self.tmp, self.directory, self.priv, self.pub = _make_directory(
            self.clock)
        self.verifier = SignedHeartbeatVerifier(
            peer_directory=self.directory, now_provider=self.clock)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _envelope(self, at_time=None, **overrides) -> dict:
        provider = self.clock if at_time is None else (lambda: float(at_time))
        envelope = build_heartbeat(self.priv, peer_id="peer-a", key_id="k1",
                                  metrics={"load": 0.25},
                                  now_provider=provider)
        envelope.update(overrides)
        return envelope

    def test_verified_origin_happy_path(self) -> None:
        result = self.verifier.verify(self._envelope())
        self.assertEqual(ORIGIN_VERIFIED, result.state)
        self.assertTrue(result.signature_checked)
        self.assertTrue(result.freshness_checked)
        self.assertTrue(result.replay_checked)
        self.assertEqual("peer-a", result.peer_id)

    def test_rejects_non_mapping_and_bad_shape(self) -> None:
        for bad in (None, 42, "text"):
            result = self.verifier.verify(bad)
            self.assertEqual(ORIGIN_REJECTED, result.state)
            self.assertFalse(result.signature_checked)
        for overrides in (
            {"kind": "OTHER"},
            {"schema_version": 2},
            {"peer_id": ""},
            {"timestamp": "soon"},
            {"nonce": "nothex"},
            {"metrics": {"x": True}},
            {SIGNATURE_FIELD: "ab" * 4},
            {SIGNATURE_FIELD: "zz" * 64},
        ):
            result = self.verifier.verify(self._envelope(**overrides))
            self.assertEqual(ORIGIN_REJECTED, result.state,
                             f"expected reject for {overrides}")
            self.assertFalse(result.signature_checked)

    def test_unknown_peer_rejected_before_signature(self) -> None:
        envelope = self._envelope(peer_id="intruder")
        result = self.verifier.verify(envelope)
        self.assertEqual(ORIGIN_REJECTED, result.state)
        self.assertIn("unknown peer", result.reason)
        self.assertFalse(result.signature_checked)
        self.assertEqual(0, len(self.verifier._seen))

    def test_revoked_peer_rejected(self) -> None:
        self.directory.revoke_peer(peer_id="peer-a",
                                   reason="test revocation")
        result = self.verifier.verify(self._envelope())
        self.assertEqual(ORIGIN_REJECTED, result.state)
        self.assertIn("not trusted", result.reason)

    def test_expired_peer_rejected(self) -> None:
        self.clock.advance(7200)
        result = self.verifier.verify(
            self._envelope(timestamp=self.clock() - 1))
        self.assertEqual(ORIGIN_REJECTED, result.state)
        self.assertIn("not trusted", result.reason)

    def test_bad_signature_rejected(self) -> None:
        envelope = self._envelope()
        envelope["metrics"]["load"] = 0.99  # tampered after signing
        result = self.verifier.verify(envelope)
        self.assertEqual(ORIGIN_REJECTED, result.state)
        self.assertFalse(result.freshness_checked)
        self.assertEqual(0, len(self.verifier._seen))

    def test_stale_and_future_rejected(self) -> None:
        result = self.verifier.verify(self._envelope(
            at_time=self.clock() - DEFAULT_TTL_SECONDS - 0.5))
        self.assertEqual(ORIGIN_REJECTED, result.state)
        self.assertTrue(result.signature_checked)
        self.assertTrue(result.freshness_checked)
        self.assertIn("stale", result.reason)

    def test_future_beyond_skew_rejected(self) -> None:
        result = self.verifier.verify(self._envelope(
            at_time=self.clock() + DEFAULT_MAX_FUTURE_SECONDS + 1.0))
        self.assertEqual(ORIGIN_REJECTED, result.state)
        self.assertTrue(result.signature_checked)
        self.assertFalse(result.freshness_checked)
        self.assertIn("future", result.reason)

    def test_replay_rejected_after_first_use(self) -> None:
        envelope = self._envelope()
        self.assertEqual(ORIGIN_VERIFIED,
                         self.verifier.verify(envelope).state)
        result = self.verifier.verify(dict(envelope))
        self.assertEqual(ORIGIN_REJECTED, result.state)
        self.assertTrue(result.replay_checked is False)
        self.assertIn("replayed nonce", result.reason)

    def test_forged_envelope_cannot_burn_nonce(self) -> None:
        envelope = self._envelope()
        forged = dict(envelope)
        forged["metrics"] = {"load": 9.9}
        result = self.verifier.verify(forged)
        self.assertEqual(ORIGIN_REJECTED, result.state)
        self.assertEqual(0, len(self.verifier._seen))
        self.assertEqual(ORIGIN_VERIFIED,
                         self.verifier.verify(envelope).state)

    def test_nonce_cache_bounded_and_evicts_old(self) -> None:
        verifier = SignedHeartbeatVerifier(
            peer_directory=self.directory, now_provider=self.clock,
            max_seen_nonces=3)
        for _ in range(5):
            verifier.verify(self._envelope())
        self.assertLessEqual(len(verifier._seen), 3)
        self.clock.advance(DEFAULT_TTL_SECONDS + DEFAULT_MAX_FUTURE_SECONDS
                          + 1)
        verifier.verify(self._envelope())
        # old entries evicted by time cutoff
        self.assertEqual(1, len(verifier._seen))

    def test_ctor_rejects_bad_limits(self) -> None:
        for kwargs in ({"ttl_seconds": 0}, {"ttl_seconds": -1.0},
                       {"max_future_seconds": -2.0},
                       {"max_seen_nonces": 0},
                       {"max_seen_nonces": True}):
            with self.assertRaises(SignedHeartbeatError):
                SignedHeartbeatVerifier(peer_directory=self.directory,
                                        **kwargs)
        with self.assertRaises(SignedHeartbeatError):
            SignedHeartbeatVerifier(peer_directory=object())

    def test_same_nonce_different_peer_is_no_collision(self) -> None:
        priv_b, pub_b = crypto_receipts.generate_signing_keypair()
        self.directory.add_peer(peer_id="peer-b",
                                public_key_hex=pub_b.hex(),
                                expires_at=int(self.clock()) + 3600)
        shared = os.urandom(8).hex()
        for peer_id, key in (("peer-a", self.priv), ("peer-b", priv_b)):
            envelope = build_heartbeat(key, peer_id=peer_id, key_id="k1",
                                       metrics={}, nonce=shared,
                                       now_provider=self.clock)
            self.assertEqual(ORIGIN_VERIFIED,
                             self.verifier.verify(envelope).state,
                             f"peer {peer_id} should pass with shared nonce")


class RegisterIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = _Clock(1_000_000.0)
        self.tmp, self.directory, self.priv, self.pub = _make_directory(
            self.clock)
        self.verifier = SignedHeartbeatVerifier(
            peer_directory=self.directory, now_provider=self.clock)
        self.register = CooperationRegister(now_provider=self.clock)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _observation(self, result: HeartbeatVerification) -> Observation:
        return Observation(
            peer_id=result.peer_id, key_id="k1", sequence=1,
            received_at=self.clock(), software_version="v91-test",
            capabilities=("heartbeat",), state=result.state,
            verification=result.as_register_verification())

    def test_verified_heartbeat_feed_updates_register_view(self) -> None:
        envelope = build_heartbeat(self.priv, peer_id="peer-a", key_id="k1",
                                  metrics={"load": 0.4},
                                  now_provider=self.clock)
        result = self.verifier.verify(envelope)
        self.assertEqual(ORIGIN_VERIFIED, result.state)
        outcome = self.register.record(self._observation(result))
        view = self.register.view("peer-a")
        self.assertEqual("ALIVE_VERIFIED", view["recorded_state"])
        self.assertIsInstance(outcome.status, str)

    def test_rejected_heartbeat_degrades_to_invalid_evidence(self) -> None:
        envelope = build_heartbeat(self.priv, peer_id="ghost", key_id="k1",
                                  metrics={}, now_provider=self.clock)
        result = self.verifier.verify(envelope)
        self.assertEqual(ORIGIN_REJECTED, result.state)
        evidence = result.as_register_verification()
        self.assertEqual("INVALID", evidence.state)
        self.assertFalse(evidence.replay_checked)
        self.assertIsInstance(evidence, Verification)


if __name__ == "__main__":
    unittest.main()
