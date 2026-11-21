#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Tests fuer die Health-/Cancellation-Verkabelung von
controller/provider_vote_adapter.py (VIBE-XL, Issue #167 Punkt 8).
Alle Provider simuliert, kein Netz, keine Credentials, keine echten
APIs (UNIT_TESTED != API_INTEGRATION_VERIFIED).
"""
from __future__ import annotations

import hashlib
import unittest

from controller.agent_consensus import sign_vote
from controller.provider_health import (
    CancelScope,
    HealthEventKind,
    HealthStatus,
    ProviderHealthPolicy,
)
from controller.provider_vote_adapter import (
    Proposal,
    Provider,
    collect_provider_votes,
)

DIGEST = hashlib.sha256(b"immutable proposal xl").hexdigest()
PROPOSAL = Proposal(DIGEST, 4)
KEY_A = b"a" * 32
KEY_B = b"b" * 32


def signed(agent: str, key: bytes, proposal: Proposal = PROPOSAL):
    return sign_vote(
        agent_id=agent,
        proposal_digest=proposal.digest,
        epoch=proposal.epoch,
        sequence=1,
        issued_at=100,
        approve=True,
        agent_key=key,
    )


def ok_provider(agent: str, key: bytes, calls: list) -> Provider:
    def invoke(proposal: Proposal):
        calls.append(agent)
        return signed(agent, key, proposal)
    return Provider(agent, "boundary-" + agent, invoke)


def failing_provider(agent: str, calls: list) -> Provider:
    def invoke(proposal: Proposal):
        calls.append(agent)
        raise RuntimeError("simulated outage")
    return Provider(agent, "boundary-" + agent, invoke)


class HealthWiringTests(unittest.TestCase):

    def test_clock_required_when_health_given(self):
        with self.assertRaises(ValueError):
            collect_provider_votes(
                PROPOSAL, [ok_provider("agent-a", KEY_A, [])],
                health=ProviderHealthPolicy(),
            )

    def test_valid_votes_record_ok_events(self):
        calls: list = []
        pol = ProviderHealthPolicy()
        batch = collect_provider_votes(
            PROPOSAL,
            [ok_provider("agent-a", KEY_A, calls), ok_provider("agent-b", KEY_B, calls)],
            health=pol, now=1,
        )
        self.assertEqual(len(batch.votes), 2)
        self.assertEqual(batch.failures, ())
        self.assertIs(pol.status("agent-a", now=2), HealthStatus.HEALTHY)
        self.assertIs(pol.status("agent-b", now=2), HealthStatus.HEALTHY)

    def test_provider_exception_records_error_and_is_missing_vote(self):
        calls: list = []
        pol = ProviderHealthPolicy()
        batch = collect_provider_votes(
            PROPOSAL,
            [failing_provider("agent-a", calls), ok_provider("agent-b", KEY_B, calls)],
            health=pol, now=1,
        )
        self.assertEqual([v.agent_id for v in batch.votes], ["agent-b"])
        self.assertEqual(len(batch.failures), 1)
        self.assertIn("provider error", batch.failures[0])
        snap = pol.snapshot("agent-a")
        self.assertEqual(snap["total_failures"], 1)
        self.assertEqual(snap["last_event"], "PROVIDER_ERROR")

    def test_blocked_advisory_skips_call_and_is_missing_vote(self):
        calls: list = []
        pol = ProviderHealthPolicy()
        pol.exclude("agent-a", reason="maintenance")
        batch = collect_provider_votes(
            PROPOSAL,
            [ok_provider("agent-a", KEY_A, calls), ok_provider("agent-b", KEY_B, calls)],
            health=pol, now=1,
        )
        # Outage ist eine FEHLENDE STIMME, nie ein verdict,
        # und der Provider wird nicht kontaktiert.
        self.assertEqual(calls, ["agent-b"])
        self.assertEqual([v.agent_id for v in batch.votes], ["agent-b"])
        self.assertEqual(len(batch.failures), 1)
        self.assertIn("health advisory", batch.failures[0])

    def test_insufficient_capacity_yields_no_quorum_material(self):
        calls: list = []
        pol = ProviderHealthPolicy()
        pol.exclude("agent-a", reason="outage")
        pol.exclude("agent-b", reason="outage")
        batch = collect_provider_votes(
            PROPOSAL,
            [ok_provider("agent-a", KEY_A, calls), ok_provider("agent-b", KEY_B, calls)],
            health=pol, now=1,
        )
        self.assertEqual(batch.votes, ())
        self.assertEqual(len(batch.failures), 2)
        # Der Caller entscheidet NO_QUORUM via quorum_capacity (REUSE).
        self.assertEqual(pol.quorum_capacity(("agent-a", "agent-b"), now=1), ())


class CancellationWiringTests(unittest.TestCase):

    def test_cancelled_round_contacts_no_provider(self):
        calls: list = []
        scope = CancelScope()
        scope.cancel(PROPOSAL.digest, reason="operator stop")
        batch = collect_provider_votes(
            PROPOSAL,
            [ok_provider("agent-a", KEY_A, calls), ok_provider("agent-b", KEY_B, calls)],
            cancel_scope=scope,
        )
        self.assertEqual(calls, [])
        self.assertEqual(batch.votes, ())
        self.assertEqual(len(batch.failures), 2)
        self.assertTrue(all("round cancelled" in f for f in batch.failures))

    def test_cancel_during_round_stops_remaining_providers(self):
        calls: list = []
        scope = CancelScope()
        late = ok_provider("agent-b", KEY_B, calls)
        first = ok_provider("agent-a", KEY_A, calls)
        original = first.invoke

        def cancelling_invoke(proposal: Proposal):
            result = original(proposal)
            scope.cancel(proposal.digest, reason="mid-round stop")
            return result

        first = Provider("agent-a", first.independence_id, cancelling_invoke)
        batch = collect_provider_votes(
            PROPOSAL, [first, late], cancel_scope=scope,
        )
        self.assertEqual(calls, ["agent-a"])  # agent-b bleibt unkontaktiert
        self.assertEqual([v.agent_id for v in batch.votes], ["agent-a"])
        self.assertEqual(len(batch.failures), 1)
        self.assertIn("round cancelled", batch.failures[0])

    def test_cancel_records_cancelled_events_without_blaming_provider(self):
        calls: list = []
        pol = ProviderHealthPolicy()
        scope = CancelScope()
        scope.cancel(PROPOSAL.digest, reason="stop")
        batch = collect_provider_votes(
            PROPOSAL,
            [ok_provider("agent-a", KEY_A, calls), ok_provider("agent-b", KEY_B, calls)],
            health=pol, cancel_scope=scope, now=5,
        )
        self.assertEqual(batch.votes, ())
        self.assertEqual(calls, [])
        for agent in ("agent-a", "agent-b"):
            snap = pol.snapshot(agent)
            self.assertEqual(snap["last_event"], "CANCELLED")
            self.assertEqual(snap["total_failures"], 0)  # keine Anlastung
            self.assertEqual(snap["consecutive_failures"], 0)

    def test_background_without_health_and_scope_unchanged(self):
        calls: list = []
        batch = collect_provider_votes(
            PROPOSAL, [ok_provider("agent-a", KEY_A, calls)],
        )
        self.assertEqual(len(batch.votes), 1)
        self.assertEqual(batch.failures, ())


if __name__ == "__main__":
    unittest.main()
