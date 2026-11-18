"""Tests for controller/cooperation_register.py (Issue #37 items 4+7).

Stdlib only. Approval: local evidence tests, no production or global
health claims.
"""
import unittest

from controller.cooperation_register import (
    CONFLICT_DIVERGENT,
    CONFLICT_OUTDATED,
    HEALTHY_STATE,
    STALE_STATE,
    UNKNOWN_STATE,
    CooperationRegister,
    Observation,
    RegisterError,
    Verification,
    verification_from_result,
)

VERIFIED = Verification(state=HEALTHY_STATE, reason="signature and freshness verified")


class FakeResult:
    def __init__(self, state, reason):
        self.state = state
        self.reason = reason


def observation(**overrides):
    kwargs = dict(
        peer_id="VB-Lauterbach-02",
        key_id="key-2026-11",
        sequence=1,
        received_at=1000.0,
        software_version="v91-0.147",
        capabilities=("measurement", "verification"),
        state="READY",
        verification=VERIFIED,
    )
    kwargs.update(overrides)
    return Observation(**kwargs)


class RecordVerifiedTests(unittest.TestCase):
    def setUp(self):
        self.register = CooperationRegister(max_age_seconds=90.0, now_provider=lambda: 1000.0)

    def test_verified_observation_updates_view(self):
        outcome = self.register.record(observation())
        self.assertEqual(outcome.status, "VERIFIED_RECORDED")
        self.assertTrue(outcome.view_updated)
        view = self.register.view("VB-Lauterbach-02")
        self.assertEqual(view["health"], HEALTHY_STATE)
        self.assertEqual(view["software_version"], "v91-0.147")
        self.assertEqual(view["last_sequence"], 1)
        self.assertEqual(view["verified_observations"], 1)

    def test_unverified_state_never_upgrades_health(self):
        bad = observation(verification=Verification(
            state="INVALID", reason="signature verification failed",
            signature_checked=False, freshness_checked=True, replay_checked=True))
        outcome = self.register.record(bad)
        self.assertEqual(outcome.status, "NOT_VERIFIED")
        self.assertFalse(outcome.view_updated)
        view = self.register.view("VB-Lauterbach-02")
        self.assertEqual(view["health"], UNKNOWN_STATE)
        self.assertEqual(view["failed_attempts"], 1)
        self.assertEqual(view["verified_observations"], 0)

    def test_verification_with_bad_state_is_rejected_even_if_flags_true(self):
        sneaky = observation(verification=Verification(
            state="ALLEGEDLY_FINE", reason="claim without check",
            signature_checked=True, freshness_checked=True, replay_checked=True))
        outcome = self.register.record(sneaky)
        self.assertEqual(outcome.status, "NOT_VERIFIED")

    def test_identical_duplicate_is_idempotent(self):
        self.register.record(observation())
        outcome = self.register.record(observation())
        self.assertEqual(outcome.status, "IDEMPOTENT_REPLAY_KNOWN")
        self.assertFalse(outcome.view_updated)
        self.assertEqual(self.register.view("VB-Lauterbach-02")["verified_observations"], 1)

    def test_divergent_content_same_sequence_conflicts_without_overwrite(self):
        self.register.record(observation())
        divergent = observation(software_version="v91-0.999-tampered")
        outcome = self.register.record(divergent)
        self.assertEqual(outcome.status, "CONFLICT")
        self.assertTrue(outcome.conflict_recorded)
        view = self.register.view("VB-Lauterbach-02")
        self.assertEqual(view["software_version"], "v91-0.147")
        self.assertEqual(len(view["open_conflicts"]), 1)
        self.assertEqual(view["open_conflicts"][0]["kind"], CONFLICT_DIVERGENT)

    def test_outdated_sequence_conflicts_view_kept(self):
        self.register.record(observation(sequence=5))
        outcome = self.register.record(observation(sequence=4))
        self.assertEqual(outcome.status, "CONFLICT")
        view = self.register.view("VB-Lauterbach-02")
        self.assertEqual(view["last_sequence"], 5)
        self.assertEqual(view["open_conflicts"][0]["kind"], CONFLICT_OUTDATED)

    def test_higher_sequence_updates_legitimately(self):
        self.register.record(observation())
        outcome = self.register.record(observation(sequence=2, software_version="v91-0.148"))
        self.assertEqual(outcome.status, "VERIFIED_RECORDED")
        view = self.register.view("VB-Lauterbach-02")
        self.assertEqual(view["software_version"], "v91-0.148")
        self.assertEqual(view["last_sequence"], 2)
        self.assertEqual(view["verified_observations"], 2)

    def test_conflict_kept_across_later_legitimate_update(self):
        self.register.record(observation(sequence=5))
        self.register.record(observation(sequence=4))
        self.register.record(observation(sequence=6))
        view = self.register.view("VB-Lauterbach-02")
        self.assertEqual(view["last_sequence"], 6)
        self.assertEqual(len(view["open_conflicts"]), 1)


class ReadTimeFreshnessTests(unittest.TestCase):
    def test_peer_reads_stale_after_window(self):
        clock = {"now": 1000.0}
        register = CooperationRegister(max_age_seconds=90.0, now_provider=lambda: clock["now"])
        register.record(observation())
        self.assertEqual(register.view("VB-Lauterbach-02")["health"], HEALTHY_STATE)
        clock["now"] = 1091.0
        self.assertEqual(register.view("VB-Lauterbach-02")["health"], STALE_STATE)

    def test_health_is_never_assumed_only_reevaluated(self):
        register = CooperationRegister(max_age_seconds=90.0, now_provider=lambda: 1000.0)
        self.assertIsNone(register.view("unbekannter-peer"))
        overview = register.overview()
        self.assertEqual(overview["peers"], {})


class OperatorResolutionTests(unittest.TestCase):
    def setUp(self):
        self.register = CooperationRegister(max_age_seconds=90.0, now_provider=lambda: 1000.0)
        self.register.record(observation(sequence=5))
        self.register.record(observation(sequence=4))

    def test_explicit_resolution_closes_conflict(self):
        result = self.register.resolve_conflict(
            "VB-Lauterbach-02", resolution="keep-higher-sequence", reason="replay-attack ruled out")
        self.assertEqual(result["resolved"], 1)
        view = self.register.view("VB-Lauterbach-02")
        self.assertTrue(view["open_conflicts"][0]["resolved"])

    def test_resolution_requires_reason(self):
        with self.assertRaises(RegisterError):
            self.register.resolve_conflict("VB-Lauterbach-02", resolution="x", reason="   ")

    def test_resolution_without_conflict_refused(self):
        register = CooperationRegister(max_age_seconds=90.0, now_provider=lambda: 1000.0)
        register.record(observation())
        with self.assertRaises(RegisterError):
            register.resolve_conflict("VB-Lauterbach-02", resolution="x", reason="nothing open")


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.register = CooperationRegister(max_age_seconds=90.0, now_provider=lambda: 1000.0)

    def test_global_status_is_refused_by_design(self):
        overview = self.register.overview()
        self.assertIn("REFUSED", overview["global_status"])

    def test_adapter_never_fabricates_evidence(self):
        degraded = verification_from_result(FakeResult("INVALID", "nope"))
        self.assertFalse(degraded.signature_checked)
        broken = verification_from_result(object())
        self.assertEqual(broken.state, "INVALID")

    def test_adapter_carries_verified_result(self):
        evidence = verification_from_result(FakeResult(HEALTHY_STATE, "signature and freshness verified"))
        self.assertTrue(evidence.signature_checked)

    def test_invalid_shapes_rejected(self):
        with self.assertRaises(RegisterError):
            self.register.record(observation(sequence=0))
        with self.assertRaises(RegisterError):
            self.register.record(observation(software_version=""))
        with self.assertRaises(RegisterError):
            self.register.record(observation(capabilities=("",)))
        with self.assertRaises(RegisterError):
            self.register.record(observation(received_at=float("nan")))

    def test_event_log_preserves_history_isolate_not_destroy(self):
        self.register.record(observation(sequence=5))
        self.register.record(observation(sequence=4))
        self.register.resolve_conflict(
            "VB-Lauterbach-02", resolution="keep-5", reason="higher sequence verified")
        events = [e["event"] for e in self.register.event_log()]
        self.assertIn("VERIFIED", events)
        self.assertIn(CONFLICT_OUTDATED, events)
        self.assertIn("RESOLVED_BY_OPERATOR", events)

    def test_duplicate_capabilities_rejected(self):
        with self.assertRaises(RegisterError):
            self.register.record(observation(capabilities=("measurement", "measurement")))


if __name__ == "__main__":
    unittest.main()
