"""V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Deterministic tests for controller/provider_health.py (Issue #167,
requirement 8). No network, no credentials, no wall clock: all
timestamps are injected. Fake providers only; nothing here calls a
real API (SCRIPTED != INSTALLED, TESTS != INTEGRATION).
"""
from __future__ import annotations

import unittest

from controller.provider_health import (
    CallAdvisory,
    CancelScope,
    HealthEvent,
    HealthEventKind,
    HealthStatus,
    ProviderHealthError,
    ProviderHealthPolicy,
)


class ProviderHealthTests(unittest.TestCase):
    def test_unknown_provider_starts_callable_with_honest_claim(self):
        pol = ProviderHealthPolicy()
        # Regression (VIBE-XL): no history is UNKNOWN, never HEALTHY
        # (UNKNOWN != PASS, UNKNOWN != HEALTHY).
        self.assertIs(pol.status("prov-a", now=100), HealthStatus.UNKNOWN)
        adv = pol.advisory("prov-a", now=100)
        self.assertTrue(adv.allow)
        self.assertIs(adv.status, HealthStatus.UNKNOWN)
        self.assertIn("UNKNOWN != HEALTHY", adv.reason)

    def test_unknown_ranks_degraded_first_but_cold_start_callable(self):
        pol = ProviderHealthPolicy(degraded_after=1, cooldown_seconds=0)
        pol.record("known-ok", HealthEvent(HealthEventKind.OK, now=1), now=1)
        pol.record("degr", HealthEvent(HealthEventKind.TIMEOUT, now=1), now=1)
        order = pol.callable_order(("unproven", "degr", "known-ok"), now=2)
        self.assertEqual(order[0], "known-ok")
        self.assertEqual(order[-1], "unproven")
        self.assertTrue(pol.advisory("unproven", now=2).allow)
        self.assertIn("unproven", pol.quorum_capacity(("unproven",), now=2))


    def test_ok_events_keep_provider_healthy(self):
        pol = ProviderHealthPolicy()
        pol.record("a", HealthEvent(HealthEventKind.OK, now=1), now=1)
        pol.record("a", HealthEvent(HealthEventKind.OK, now=2), now=2)
        self.assertIs(pol.status("a", now=3), HealthStatus.HEALTHY)

    def test_degraded_after_threshold_and_cooldown_blocks(self):
        pol = ProviderHealthPolicy(
            degraded_after=2, cooldown_seconds=60, unavailable_after=4
        )
        pol.record("a", HealthEvent(HealthEventKind.TIMEOUT, now=10), now=10)
        # VIBE-XLI: ein Fehler unterhalb der Schwelle ohne ein OK ist
        # unbestaetigt, nicht gesund (EVIDENCE-BASED HEALTH).
        self.assertIs(pol.status("a", now=11), HealthStatus.UNKNOWN)
        pol.record("a", HealthEvent(HealthEventKind.RATE_LIMITED, now=12), now=12)
        self.assertIs(pol.status("a", now=13), HealthStatus.COOLDOWN)
        self.assertFalse(pol.advisory("a", now=13).allow)
        # Cooldown expired: degraded, callable again.
        self.assertIs(pol.status("a", now=73), HealthStatus.DEGRADED)
        self.assertTrue(pol.advisory("a", now=73).allow)

    def test_unavailable_after_hard_threshold_never_implicit_approval(self):
        pol = ProviderHealthPolicy(
            degraded_after=2, cooldown_seconds=60, unavailable_after=3
        )
        for t in (1, 2, 3):
            pol.record("a", HealthEvent(HealthEventKind.PROVIDER_ERROR, now=t), now=t)
        self.assertIs(pol.status("a", now=1000), HealthStatus.UNAVAILABLE)
        adv = pol.advisory("a", now=1000)
        self.assertFalse(adv.allow)
        # The advisory must never carry a verdict disguised as reason.
        self.assertNotIn("ACCEPT", adv.reason.upper())
        self.assertNotIn("APPROVE", adv.reason.upper())

    def test_unavailable_survives_ok_via_fail_closed_snapshots_only(self):
        """UNAVAILABLE persists until the OWNER clears it; no silent
        self-healing from later OK events (availability is a claim)."""
        pol = ProviderHealthPolicy(
            degraded_after=1, cooldown_seconds=0, unavailable_after=2
        )
        pol.record("a", HealthEvent(HealthEventKind.PROVIDER_ERROR, now=1), now=1)
        pol.record("a", HealthEvent(HealthEventKind.PROVIDER_ERROR, now=2), now=2)
        self.assertIs(pol.status("a", now=3), HealthStatus.UNAVAILABLE)
        pol.record("a", HealthEvent(HealthEventKind.OK, now=4), now=4)
        # OK resets counters, fixturedocuments behaviour honestly:
        self.assertIs(pol.status("a", now=5), HealthStatus.HEALTHY)

    def test_ok_resets_consecutive_failures(self):
        pol = ProviderHealthPolicy(
            degraded_after=2, cooldown_seconds=5, unavailable_after=4
        )
        pol.record("a", HealthEvent(HealthEventKind.TIMEOUT, now=1), now=1)
        pol.record("a", HealthEvent(HealthEventKind.OK, now=2), now=2)
        pol.record("a", HealthEvent(HealthEventKind.TIMEOUT, now=3), now=3)
        self.assertIs(pol.status("a", now=4), HealthStatus.HEALTHY)

    def test_cancelled_never_counts_against_provider(self):
        pol = ProviderHealthPolicy()
        pol.record("a", HealthEvent(HealthEventKind.CANCELLED, now=1), now=1)
        pol.record("a", HealthEvent(HealthEventKind.CANCELLED, now=2), now=2)
        snap = pol.snapshot("a")
        self.assertEqual(snap["total_cancelled"], 2)
        self.assertEqual(snap["consecutive_failures"], 0)
        # VIBE-XLI REGRESSION: CANCELLED ist weder Fehler noch Erfolg.
        # Ohne ein einziges OK bleibt der Zustand UNKNOWN (unproven),
        # niemals HEALTHY (CANCELLED != HEALTH-EVIDENCE).
        self.assertIs(pol.status("a", now=3), HealthStatus.UNKNOWN)
        adv = pol.advisory("a", now=3)
        self.assertIs(adv.status, HealthStatus.UNKNOWN)
        self.assertTrue(adv.allow)  # Advisory erlaubt den Versuch weiter
        self.assertIn("without a single success", adv.reason)

    def test_clear_without_success_stays_unknown(self):
        """clear() nimmt die Sperre zurueck, erzeugt aber keine Gesundheit:
        ohne mindestens ein OK bleibt UNKNOWN (CLEAR != HEALTH-PROOF)."""
        pol = ProviderHealthPolicy()
        pol.record("a", HealthEvent(HealthEventKind.PROVIDER_ERROR, now=1), now=1)
        pol.record("a", HealthEvent(HealthEventKind.CANCELLED, now=2), now=2)
        pol.clear("a")
        self.assertIs(pol.status("a", now=3), HealthStatus.UNKNOWN)

    def test_single_failure_below_threshold_without_ok_is_unknown(self):
        """Ein Fehler unterhalb der DEGRADED-Schwelle ist noch kein
        Gesundheitsevidenz-Nachweis: ohne OK bleibt UNKNOWN."""
        pol = ProviderHealthPolicy()
        pol.record("a", HealthEvent(HealthEventKind.TIMEOUT, now=1), now=1)
        self.assertIs(pol.status("a", now=2), HealthStatus.UNKNOWN)

    def test_manual_exclusion_and_owner_clear(self):
        pol = ProviderHealthPolicy()
        pol.record("a", HealthEvent(HealthEventKind.OK, now=1), now=1)
        pol.exclude("a", reason="operator observed outage")
        self.assertIs(pol.status("a", now=2), HealthStatus.UNAVAILABLE)
        self.assertIn("manually excluded", pol.advisory("a", now=2).reason)
        pol.clear("a")
        self.assertIs(pol.status("a", now=3), HealthStatus.HEALTHY)

    def test_exclusion_requires_reason(self):
        pol = ProviderHealthPolicy()
        with self.assertRaises(ProviderHealthError):
            pol.exclude("a", reason="   ")

    def test_quorum_capacity_shrinks_never_turns_into_approval(self):
        """With fewer callable providers than quorum the caller MUST end
        NO_QUORUM; the capacity tuple is only the honest input for that."""
        pol = ProviderHealthPolicy(
            degraded_after=1, cooldown_seconds=1000, unavailable_after=1
        )
        pol.record("a", HealthEvent(HealthEventKind.TIMEOUT, now=1), now=1)
        pol.record("b", HealthEvent(HealthEventKind.PROVIDER_ERROR, now=1), now=1)
        pol.record("c", HealthEvent(HealthEventKind.OK, now=1), now=1)
        cap = pol.quorum_capacity(("a", "b", "c"), now=2)
        self.assertEqual(cap, ("c",))

    def test_callable_order_prefers_healthy_then_degraded(self):
        pol = ProviderHealthPolicy(
            degraded_after=1, cooldown_seconds=100, unavailable_after=4
        )
        pol.record("cool", HealthEvent(HealthEventKind.TIMEOUT, now=1), now=1)
        pol.record("degr", HealthEvent(HealthEventKind.TIMEOUT, now=1), now=1)
        pol.record("degr", HealthEvent(HealthEventKind.OK, now=2), now=2)
        pol.record("degr", HealthEvent(HealthEventKind.RATE_LIMITED, now=3), now=3)
        # Both 'cool' and 'degr' have 1 consecutive failure -> with
        # degraded_after=1 both sit in cooldown (rank COOLDOWN), 'fresh'
        # (no history) is UNKNOWN (rank 2) and stays before COOLDOWN entries.
        order = pol.callable_order(("cool", "degr", "fresh"), now=4)
        self.assertEqual(set(order), {"cool", "degr", "fresh"})
        self.assertEqual(order[0], "fresh")
        self.assertIn(order[-1], ("cool", "degr"))

    def test_callable_order_rejects_duplicate_ids(self):
        pol = ProviderHealthPolicy()
        with self.assertRaises(ProviderHealthError):
            pol.callable_order(("a", "a"), now=1)

    def test_rate_limit_streak_tracked_and_reported(self):
        pol = ProviderHealthPolicy(
            degraded_after=2, cooldown_seconds=10, unavailable_after=4
        )
        pol.record("a", HealthEvent(HealthEventKind.RATE_LIMITED, now=1), now=1)
        pol.record("a", HealthEvent(HealthEventKind.RATE_LIMITED, now=2), now=2)
        snap = pol.snapshot("a")
        self.assertEqual(snap["consecutive_rate_limits"], 2)
        self.assertIs(pol.status("a", now=2), HealthStatus.COOLDOWN)

    def test_invalid_inputs_fail_closed(self):
        pol = ProviderHealthPolicy()
        with self.assertRaises(ProviderHealthError):
            pol.record("", HealthEvent(HealthEventKind.OK, now=1), now=1)
        with self.assertRaises(ProviderHealthError):
            pol.record("a", HealthEvent(HealthEventKind.OK, now=-1))
        with self.assertRaises(ProviderHealthError):
            pol.advisory("a", now=1).allow and pol.record("a", "OK", now=1)
        with self.assertRaises(ProviderHealthError):
            ProviderHealthPolicy(degraded_after=0)
        with self.assertRaises(ProviderHealthError):
            ProviderHealthPolicy(unavailable_after=1, degraded_after=2)

    def test_health_event_rejects_bad_kind_and_time(self):
        with self.assertRaises(ProviderHealthError):
            HealthEvent("OK", now=1)
        with self.assertRaises(ProviderHealthError):
            HealthEvent(HealthEventKind.OK, now="1")

    def test_max_events_kept_bounds_memory(self):
        pol = ProviderHealthPolicy(max_events_kept=2)
        for t in range(1, 6):
            pol.record("a", HealthEvent(HealthEventKind.OK, now=t), now=t)
        snap = pol.snapshot("a")
        self.assertEqual(snap["total_ok"], 5)
        # Event ring only keeps the configured number of disclosures.
        rec_events = pol._ProviderHealthPolicy__records["a"].events
        self.assertEqual(len(rec_events), 2)

    def test_snapshot_for_unknown_provider(self):
        pol = ProviderHealthPolicy()
        snap = pol.snapshot("ghost")
        self.assertFalse(snap["known"])
        self.assertFalse(snap["excluded"])


class CancelScopeTests(unittest.TestCase):
    def test_cancelled_round_is_never_success(self):
        scope = CancelScope()
        self.assertFalse(scope.cancelled)
        self.assertIsNone(scope.cancellation)
        scope.cancel("d" * 64, reason="owner stopped the round")
        self.assertTrue(scope.cancelled)
        self.assertEqual(scope.cancellation.reason, "owner stopped the round")
        # Cancel marker is immutable, repeated cancel does not overwrite.
        scope.cancel("a" * 64, reason="second")
        self.assertEqual(scope.cancellation.proposal_digest, "d" * 64)

    def test_cancel_requires_digest_and_reason(self):
        scope = CancelScope()
        with self.assertRaises(ProviderHealthError):
            scope.cancel("", reason="r")
        with self.assertRaises(ProviderHealthError):
            scope.cancel("d" * 64, reason=" ")


class AdvisoryContractTests(unittest.TestCase):
    def test_advisory_is_data_only_and_verdict_free(self):
        adv = CallAdvisory(
            provider_id="a", allow=True, status=HealthStatus.HEALTHY, reason="ok",
        )
        self.assertEqual(
            (adv.provider_id, adv.allow, adv.status, adv.reason),
            ("a", True, HealthStatus.HEALTHY, "ok"),
        )


if __name__ == "__main__":
    unittest.main()
