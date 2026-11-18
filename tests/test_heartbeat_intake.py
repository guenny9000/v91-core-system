#!/usr/bin/env python3
"""Tests for controller/heartbeat_intake.py (Issue #37, stage 3).

Loopback evidence: two fully separated test instances (own keypair,
own peer directory, own cooperation register, own intake) exchange
signed heartbeats in both directions. Every claim below is fail-closed.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller import crypto_receipts
from controller.cooperation_register import CooperationRegister
from controller.peer_directory import PeerDirectory
from controller.signed_heartbeat import (
    DEFAULT_MAX_FUTURE_SECONDS,
    DEFAULT_TTL_SECONDS,
    ORIGIN_REJECTED,
    ORIGIN_VERIFIED,
    build_heartbeat,
)
from controller.heartbeat_intake import (
    FALLBACK_SOFTWARE_VERSION,
    STATUS_PRE_REGISTER,
    HeartbeatIntake,
    HeartbeatIntakeError,
    IntakeOutcome,
)


class _Clock:
    def __init__(self) -> None:
        self.now = 2_000_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _Instance:
    """One isolated V91 test instance: own keys, trust, register, intake."""

    def __init__(self, tmp: str, peer_id: str, clock: _Clock) -> None:
        self.peer_id = peer_id
        self.clock = clock
        self.directory = PeerDirectory(
            os.path.join(tmp, f"{peer_id}-peers.sqlite"),
            now_provider=clock)
        self.priv, pub = crypto_receipts.generate_signing_keypair()
        self.public_hex = pub.hex()
        self.register = CooperationRegister(now_provider=clock)
        self.intake = None  # wired in wire()

    def trust(self, other: "_Instance", expires_at: int) -> None:
        self.directory.add_peer(peer_id=other.peer_id,
                                public_key_hex=other.public_hex,
                                expires_at=expires_at)

    def wire(self) -> None:
        self.intake = HeartbeatIntake(
            peer_directory=self.directory, register=self.register,
            now_provider=self.clock)

    def emit(self, metrics=None, nonce=None) -> dict:
        return build_heartbeat(
            self.priv, peer_id=self.peer_id, key_id=f"{self.peer_id}-k1",
            metrics=metrics if metrics is not None else {
                "software_version": "v91-test-1",
                "capabilities": "heartbeat,intake",
            },
            nonce=nonce, now_provider=self.clock)


def _pair():
    tmp = tempfile.TemporaryDirectory()
    clock = _Clock()
    a = _Instance(tmp.name, "node-alpha", clock)
    b = _Instance(tmp.name, "node-beta", clock)
    a.trust(b, expires_at=int(clock.now) + 3600)
    b.trust(a, expires_at=int(clock.now) + 3600)
    a.wire()
    b.wire()
    return tmp, clock, a, b


class IntakeConstructorTests(unittest.TestCase):
    def test_requires_directory_and_register(self) -> None:
        with self.assertRaises(HeartbeatIntakeError):
            HeartbeatIntake(peer_directory=None,
                            register=CooperationRegister())
        with self.assertRaises(HeartbeatIntakeError):
            HeartbeatIntake(peer_directory="not-a-directory",
                            register=None)


class LoopbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp, self.clock, self.alpha, self.beta = _pair()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_bidirectional_loopback_records_views_both_sides(self) -> None:
        for sender, receiver in ((self.alpha, self.beta),
                                 (self.beta, self.alpha)):
            outcome = receiver.intake.receive(sender.emit())
            self.assertEqual(ORIGIN_VERIFIED,
                             outcome.verification.state)
            self.assertEqual("VERIFIED_RECORDED", outcome.status)
            self.assertTrue(outcome.view_updated)
            view = receiver.register.view(sender.peer_id)
            self.assertEqual("ALIVE_VERIFIED", view["recorded_state"])
            self.assertEqual("ALIVE_VERIFIED", view["health"])
            self.assertEqual("v91-test-1", view["software_version"])
            self.assertEqual(["heartbeat", "intake"],
                             list(view["capabilities"]))
            self.assertEqual(1, view["verified_observations"])
            self.assertEqual(0, view["failed_attempts"])

    def test_receiver_assigned_sequence_is_monotonic(self) -> None:
        for expected_sequence in (1, 2, 3):
            outcome = self.beta.intake.receive(self.alpha.emit())
            self.assertEqual(expected_sequence, outcome.sequence)
        view = self.beta.register.view("node-alpha")
        self.assertEqual(3, view["last_sequence"])

    def test_replayed_heartbeat_is_failed_attempt_not_view_upgrade(self) -> None:
        envelope = self.alpha.emit()
        self.assertEqual("VERIFIED_RECORDED",
                         self.beta.intake.receive(envelope).status)
        second = self.beta.intake.receive(dict(envelope))
        self.assertEqual(ORIGIN_REJECTED, second.verification.state)
        self.assertEqual("NOT_VERIFIED", second.status)
        self.assertFalse(second.view_updated)
        view = self.beta.register.view("node-alpha")
        self.assertEqual(1, view["verified_observations"])
        self.assertEqual(1, view["failed_attempts"])

    def test_tampered_envelope_is_failed_attempt(self) -> None:
        envelope = self.alpha.emit()
        envelope["metrics"]["software_version"] = "v91-evil"
        outcome = self.beta.intake.receive(envelope)
        self.assertEqual(ORIGIN_REJECTED, outcome.verification.state)
        self.assertEqual("NOT_VERIFIED", outcome.status)
        view = self.beta.register.view("node-alpha")
        self.assertEqual("UNKNOWN", view["recorded_state"])
        self.assertEqual(1, view["failed_attempts"])

    def test_unknown_peer_files_failed_attempt(self) -> None:
        ghost = _Instance(self.tmp.name, "node-ghost", self.clock)
        # nobody trusts the ghost; it never wired an intake of its own
        outcome = self.beta.intake.receive(ghost.emit())
        self.assertEqual("NOT_VERIFIED", outcome.status)
        # the ghost's own view list on beta: failed attempt recorded
        view = self.beta.register.view("node-ghost")
        self.assertEqual(1, view["failed_attempts"])
        self.assertEqual("UNKNOWN", view["recorded_state"])

    def test_shape_invalid_envelope_rejected_before_register(self) -> None:
        for bad in (None, 42, "text", {}, {"peer_id": "x"},
                    {"peer_id": "node-alpha", "kind": "nope"}):
            outcome = self.beta.intake.receive(bad)
            self.assertEqual(STATUS_PRE_REGISTER, outcome.status)
        self.assertEqual({}, self.beta.register.overview()["peers"])

    def test_revoked_peer_view_keeps_last_verified(self) -> None:
        self.assertEqual("VERIFIED_RECORDED",
                         self.beta.intake.receive(self.alpha.emit()).status)
        self.beta.directory.revoke_peer(peer_id="node-alpha",
                                       reason="revoked mid-test")
        outcome = self.beta.intake.receive(self.alpha.emit())
        self.assertEqual("NOT_VERIFIED", outcome.status)
        view = self.beta.register.view("node-alpha")
        # ISOLATE_NOT_DESTROY: last verified view untouched
        self.assertEqual("ALIVE_VERIFIED", view["recorded_state"])
        self.assertEqual(1, view["verified_observations"])

    def test_stale_and_future_heartbeats_are_failed_attempts(self) -> None:
        stale = self.alpha.emit()
        self.clock.advance(DEFAULT_TTL_SECONDS + 1)
        self.beta.intake.receive(stale)
        future = build_heartbeat(self.alpha.priv, peer_id="node-alpha",
                                 key_id="node-alpha-k1", metrics={},
                                 now_provider=lambda: self.clock.now
                                 + DEFAULT_MAX_FUTURE_SECONDS + 10)
        future_outcome = self.beta.intake.receive(future)
        self.assertEqual("NOT_VERIFIED", future_outcome.status)
        view = self.beta.register.view("node-alpha")
        self.assertEqual(2, view["failed_attempts"])
        self.assertEqual("UNKNOWN", view["recorded_state"])

    def test_health_degrades_to_stale_at_read_time(self) -> None:
        self.beta.intake.receive(self.alpha.emit())
        self.clock.advance(120)  # > register max_age_seconds (90)
        view = self.beta.register.view("node-alpha")
        self.assertEqual("STALE", view["health"])
        self.assertEqual("ALIVE_VERIFIED", view["recorded_state"])

    def test_missing_signed_metadata_falls_back(self) -> None:
        outcome = self.beta.intake.receive(
            self.alpha.emit(metrics={"load": 0.5}))
        self.assertEqual("VERIFIED_RECORDED", outcome.status)
        view = self.beta.register.view("node-alpha")
        self.assertEqual(FALLBACK_SOFTWARE_VERSION,
                         view["software_version"])
        self.assertEqual([], list(view["capabilities"]))

    def test_no_cross_talk_without_exchange(self) -> None:
        self.beta.intake.receive(self.alpha.emit())
        # alpha's register knows nothing about beta until beta emits
        self.assertIsNone(self.alpha.register.view("node-beta"))
        self.assertEqual(0, len(self.alpha.register.overview()["peers"]))

    def test_expired_trust_is_failed_attempt(self) -> None:
        self.clock.advance(7200)  # trust entries expired
        outcome = self.beta.intake.receive(self.alpha.emit())
        self.assertEqual("NOT_VERIFIED", outcome.status)
        self.assertIn("not trusted", outcome.verification.reason)


if __name__ == "__main__":
    unittest.main()
