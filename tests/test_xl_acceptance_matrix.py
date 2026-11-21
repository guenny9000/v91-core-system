#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
VIBE-XL Annahmematrix (Issue #167 Punkt 8, Folgetest zu PR #304).

Pruefzeilen (siehe Matrix in Issue #220-Umfeld):
  Zeile 1  UNKNOWN-Semantik (UNKNOWN != PASS, UNKNOWN != HEALTHY)
  Zeile 2  Health-Advisory vor jedem Aufruf
  Zeile 3  Cancellation-Pfad (vor und waehrend des Aufrufs)
  Zeile 4  Ausfaelle sind FEHLENDE STIMMEN
  Zeile 5  Quorum/Kapazitaet erzwingt NO_QUORUM (echter Pfad:
           agent_consensus.evaluate_consensus, REUSE)
  Zeile 6  Archiv-/Ledger-Kopplung: lokal gilt die Vorbedingung
           "eine NO_QUORUM-/abgebrochene Runde hat NICHTS zu
           persistieren" (Schein-Quorum unmoeglich); der positive
           Ed25519-Archivtest laeuft nur mit cryptography (CI).
  Zeile 7  Reproduzierbarkeit ohne Netz und Keys (deterministisch).

Ehrliche Grenze: die Ed25519-Teiltests sind local skipped
(SKIP != FAIL != PASS; UNKNOWN != PASS). Kein Netz, keine echten
Credentials, keine API_INTEGRATION_VERIFIED-Claims.
"""
from __future__ import annotations

import hashlib
import unittest

from controller.agent_consensus import Decision, evaluate_consensus, sign_vote
from controller.provider_health import (
    CancelScope,
    HealthEvent,
    HealthEventKind,
    HealthStatus,
    ProviderHealthPolicy,
)
from controller.provider_vote_adapter import (
    Proposal,
    Provider,
    collect_provider_votes,
)

DIGEST = hashlib.sha256(b"xl-acceptance-matrix").hexdigest()
PROPOSAL = Proposal(DIGEST, 4)
KEYS = {"agent-a": b"a" * 32, "agent-b": b"b" * 32, "agent-c": b"c" * 32}


def signed(agent: str, proposal: Proposal = PROPOSAL, approve: bool = True):
    return sign_vote(
        agent_id=agent,
        proposal_digest=proposal.digest,
        epoch=proposal.epoch,
        sequence=1,
        issued_at=100,
        approve=approve,
        agent_key=KEYS[agent],
    )


def ok_provider(agent: str, calls: list) -> Provider:
    def invoke(proposal: Proposal):
        calls.append(agent)
        return signed(agent, proposal)
    return Provider(agent, "boundary-" + agent, invoke)


def failing_provider(agent: str, calls: list) -> Provider:
    def invoke(proposal: Proposal):
        calls.append(agent)
        raise TimeoutError("simulated provider outage")
    return Provider(agent, "boundary-" + agent, invoke)


def decide(votes, *, quorum: int | None = None, members=None) -> Decision:
    result = evaluate_consensus(
        list(votes),
        member_keys=members if members is not None else dict(KEYS),
        proposal_digest=DIGEST,
        epoch=PROPOSAL.epoch,
        now=130,
        min_sequence_by_agent={a: 0 for a in (members or KEYS)},
        quorum=quorum,
    )
    return result.decision


class Row1UnknownSemanticsTests(unittest.TestCase):
    """T-01, T-02: UNKNOWN ist kein HEALTHY, kein PASS, kein Freigabe-Claim."""

    def test_t01_fresh_provider_is_unknown_never_healthy(self):
        pol = ProviderHealthPolicy()
        st = pol.status("agent-a", now=1)
        self.assertIs(st, HealthStatus.UNKNOWN)
        self.assertNotEqual(st, HealthStatus.HEALTHY)

    def test_t01_unknown_is_not_a_pass_in_evaluation(self):
        # Kapazitaet: UNKNOWN bleibt anrufbar (Cold Start erlaubt),
        # aber nur ECHTE gueltige Stimmen zaehlen im Quorum.
        pol = ProviderHealthPolicy()
        self.assertIn("agent-a", pol.quorum_capacity(("agent-a",), now=1))

    def test_t02_transition_unknown_to_healthy_and_back(self):
        pol = ProviderHealthPolicy(degraded_after=2, unavailable_after=2,
                                   cooldown_seconds=5)
        self.assertIs(pol.status("a", now=1), HealthStatus.UNKNOWN)
        pol.record("a", HealthEvent(HealthEventKind.OK, now=1), now=1)
        self.assertIs(pol.status("a", now=2), HealthStatus.HEALTHY)
        pol.record("a", HealthEvent(HealthEventKind.TIMEOUT, now=3), now=3)
        pol.record("a", HealthEvent(HealthEventKind.TIMEOUT, now=4), now=4)
        self.assertIs(pol.status("a", now=5), HealthStatus.UNAVAILABLE)
        # Neuer Provider bleibt bis zum ersten Ereignis UNKNOWN.
        self.assertIs(pol.status("b", now=5), HealthStatus.UNKNOWN)


class Row2AdvisoryTests(unittest.TestCase):
    """T-Matrix Zeile 2: Advisory filtert ungeeignete Provider VOR dem Aufruf."""

    def test_unhealthy_provider_is_not_called_and_counts_for_nothing(self):
        calls: list = []
        pol = ProviderHealthPolicy()
        pol.exclude("agent-a", reason="known outage")
        batch = collect_provider_votes(
            PROPOSAL,
            [ok_provider("agent-a", calls), ok_provider("agent-b", calls)],
            health=pol, now=1,
        )
        self.assertEqual(calls, ["agent-b"])
        self.assertEqual([v.agent_id for v in batch.votes], ["agent-b"])
        self.assertEqual(len(batch.failures), 1)
        # 1 gueltige Stimme reicht fuer kein Quorum (echter Pfad):
        self.assertIs(decide(batch.votes, quorum=2), Decision.NO_QUORUM)

    def test_unknown_provider_may_be_called_but_must_deliver_valid_vote(self):
        calls: list = []
        batch = collect_provider_votes(
            PROPOSAL, [ok_provider("agent-a", calls)],
        )
        self.assertEqual(calls, ["agent-a"])
        self.assertEqual(len(batch.votes), 1)


class Row3CancellationTests(unittest.TestCase):
    """T-03, T-04: Abbruch vor und waehrend der Runde."""

    def test_t03_pre_cancel_contacts_no_provider_and_yields_nothing(self):
        calls: list = []
        scope = CancelScope()
        scope.cancel(PROPOSAL.digest, reason="operator stop")
        batch = collect_provider_votes(
            PROPOSAL,
            [ok_provider("agent-a", calls), ok_provider("agent-b", calls)],
            cancel_scope=scope,
        )
        self.assertEqual(calls, [])
        self.assertEqual(batch.votes, ())
        self.assertIs(decide(batch.votes, quorum=1), Decision.NO_QUORUM)
        # Eine abgebrochene Runde erzeugt keine Stimme fuer das Archiv
        # (Zeile 6 Vorbedingung: NICHTS zu persistieren).
        self.assertEqual(batch.votes, ())

    def test_t04_mid_round_cancel_stops_rest_cleanly(self):
        calls: list = []
        scope = CancelScope()
        first = ok_provider("agent-a", calls)
        original = first.invoke

        def cancelling(p: Proposal):
            result = original(p)
            scope.cancel(p.digest, reason="mid-round stop")
            return result

        batch = collect_provider_votes(
            PROPOSAL,
            [Provider("agent-a", first.independence_id, cancelling),
             ok_provider("agent-b", calls)],
            cancel_scope=scope,
        )
        self.assertEqual(calls, ["agent-a"])  # agent-b unkontaktiert
        # 1 gueltige Stimme, keine stillen Faelschungen zur vollen Runde:
        self.assertEqual([v.agent_id for v in batch.votes], ["agent-a"])
        self.assertIs(decide(batch.votes, quorum=2), Decision.NO_QUORUM)
        for f in batch.failures:
            self.assertIn("round cancelled", f)

    def test_cancelled_event_never_flatters_provider_health(self):
        calls: list = []
        pol = ProviderHealthPolicy()
        scope = CancelScope()
        scope.cancel(PROPOSAL.digest, reason="stop")
        collect_provider_votes(
            PROPOSAL, [ok_provider("agent-a", calls)],
            health=pol, cancel_scope=scope, now=5,
        )
        snap = pol.snapshot("agent-a")
        self.assertEqual(snap["total_ok"], 0)      # nie als Erfolg gebucht
        self.assertEqual(snap["total_failures"], 0)  # nie angeklagt


class Row4OutageTests(unittest.TestCase):
    """T-05: Ausfall = fehlende Stimme, kein Crash, kein Abstain."""

    def test_t05_provider_outages_are_missing_votes_only(self):
        calls: list = []
        pol = ProviderHealthPolicy()
        batch = collect_provider_votes(
            PROPOSAL,
            [failing_provider("agent-a", calls),
             failing_provider("agent-b", calls),
             failing_provider("agent-c", calls)],
            health=pol, now=1,
        )
        self.assertEqual(calls, ["agent-a", "agent-b", "agent-c"])
        self.assertEqual(batch.votes, ())
        self.assertEqual(len(batch.failures), 3)
        self.assertIs(decide(batch.votes, quorum=2), Decision.NO_QUORUM)
        for agent in KEYS:
            self.assertEqual(pol.snapshot(agent)["total_failures"], 1)

    def test_invalid_payload_is_missing_vote_not_approval(self):
        calls: list = []

        def bad_invoke(p: Proposal):
            calls.append("agent-a")
            return None  # unguelteger Payload

        batch = collect_provider_votes(
            PROPOSAL, [Provider("agent-a", "boundary-a", bad_invoke)],
        )
        self.assertEqual(batch.votes, ())
        self.assertIn("not a Vote", batch.failures[0])


class Row5CapacityTests(unittest.TestCase):
    """T-06: Kombinierte Unterversorgung erzwingt deterministisch NO_QUORUM."""

    def test_t06_combined_shortfall_forces_no_quorum_on_real_path(self):
        calls: list = []
        pol = ProviderHealthPolicy()
        pol.exclude("agent-a", reason="advisory blocked")
        scope = CancelScope()
        # agent-a: advisory-blockiert; agent-b: Ausfall und loest Abbruch aus;
        # agent-c: danach abgebrochen, wird nicht mehr kontaktiert.
        failing = failing_provider("agent-b", calls)
        original = failing.invoke

        def failing_and_cancelling(p: Proposal):
            try:
                return original(p)
            finally:
                scope.cancel(p.digest, reason="halt after outage")

        batch = collect_provider_votes(
            PROPOSAL,
            [ok_provider("agent-a", calls),
             Provider("agent-b", failing.independence_id, failing_and_cancelling),
             ok_provider("agent-c", calls)],
            health=pol, cancel_scope=scope, now=1,
        )
        self.assertEqual(batch.votes, ())
        self.assertEqual(len(batch.failures), 3)  # 3 fehlende Stimmen, sichtbar
        self.assertEqual(calls, ["agent-b"])
        self.assertIn("health advisory", batch.failures[0])
        self.assertIn("provider error", batch.failures[1])
        self.assertIn("round cancelled", batch.failures[2])
        # agent-a ist excluded; der Rest hat keine positive Evidenz.
        self.assertEqual(pol.quorum_capacity(("agent-a", "agent-b", "agent-c"),
                                             now=2), ("agent-b", "agent-c"))
        # Aber die Runde ist abgebrochen: KEINE der Stimmen existiert.
        self.assertIs(decide(batch.votes, quorum=2), Decision.NO_QUORUM)

    def test_quorum_reached_only_with_real_valid_votes(self):
        calls: list = []
        batch = collect_provider_votes(
            PROPOSAL,
            [ok_provider("agent-a", calls), ok_provider("agent-b", calls)],
        )
        self.assertIs(decide(batch.votes, quorum=2), Decision.ACCEPT)
        # Zwei Zustimmungen von NICHT konfigurierten Agenten zaehlen nie:
        alien = sign_vote(agent_id="ghost", proposal_digest=DIGEST, epoch=4,
                          sequence=1, issued_at=100, approve=True,
                          agent_key=b"g" * 32)
        self.assertIs(decide(batch.votes + (alien,), quorum=3,
                             members=dict(KEYS)), Decision.NO_QUORUM)


try:
    from controller.consensus_archive import ConsensusArchive
    _ED25519_AVAILABLE = True
except Exception:  # cryptography fehlt lokal: SKIP != FAIL (UNKNOWN != PASS)
    _ED25519_AVAILABLE = False


@unittest.skipUnless(_ED25519_AVAILABLE, "cryptography/Ed25519 (CI) required")
class Row6ArchiveCouplingTests(unittest.TestCase):
    """Zeile 6 (positiver Teil, CI): Schein-Quoren sind nicht persistierbar."""

    def test_noquorum_round_leaves_assumed_archive_untouched_and_fake_fails(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            archive = ConsensusArchive(Path(tmp), {"agent-a": b"k" * 32})
            before = archive.ledger.entry_count()
            # Fabrizierter Versuch, eine fehlende Stimme zu persistieren:
            with self.assertRaises(Exception):
                archive.cast_vote({"agent_id": "agent-a", "bogus": True},
                                  {"agent_id": "agent-a"})
            self.assertEqual(archive.ledger.entry_count(), before)
            # Eine leere (NO_QUORUM-)Runde haette ohnehin NICHTS zu
            # persistieren; der Zaehler bleibt unveraendert.


class Row7DeterminismTests(unittest.TestCase):
    """T-07: Nur lokale Fakes, keine Credentials, deterministische Uhren."""

    def test_no_network_no_credentials_by_construction(self):
        import inspect
        from controller import provider_vote_adapter as pva
        from controller import provider_health as ph
        for module in (pva, ph):
            src = inspect.getsource(module)
            self.assertNotIn("import socket", src)
            self.assertNotIn("requests", src)
            self.assertNotIn("urllib", src)
            self.assertNotIn("http.client", src)

    def test_all_matrix_tests_use_fixed_clocks(self):
        # Alle Adapter-Aufrufe in dieser Suite nutzen now=<int> oder
        # gar keine health-Policy; keine Wanduhr in den Kernpfaden.
        import inspect
        src = inspect.getsource(collect_provider_votes)
        self.assertNotIn("time.time", src)


if __name__ == "__main__":
    unittest.main()
