#!/usr/bin/env python3
"""V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
E2E-Runden-Matrix fur den API-gestutzten Review-Quorum (VIBE-XL,
Issue #167 Betriebsteile). Kein neues Orchestrierungsmodul: die
Matrix verdrahtet NUR bestehende Systeme (NO_DUPLICATE_SYSTEMS):

  provider_health        Advisory-Gate + kooperative Abbruch-Sichtung
  provider_vote_adapter  Stimmensammlung mit Fehlerisolation
  agent_consensus        fail-closed Auswertung (ACCEPT/REJECT/NO_QUORUM)
  consensus_archive      gepaarte Persistenz (Ed25519-Stimmen + Receipts)

Ursprung: externer Matrix-Entwurf (T-01 bis T-07, simulierter
Runner). Der Standalone-Runner wurde bewusst NICHT uebernommen, weil
er provider_health/provider_vote_adapter/agent_consensus als zweite,
schwaechere Kopie neben die echten Module stellen wuerde. Erhalten
ist die Matrix der Pruefszenarien, ausgefuehrt gegen die realen
Vertraege. Zwei bewusste Korrekturen gegenueber dem Entwurf:

1. UNKNOWN wird NICHT gesperrt, sondern erlaubt einen Cold-Start-Call
   und bleibt Status erster Klasse: das Advisory erlaubt den Anruf,
   behauptet aber nie Gesundheit (UNKNOWN != HEALTHY).
2. Persistenz erzeugt kein Runner, sondern bleibt Rufer-Pflicht: nur
   eine Runde mit Quorum wird gepaart im Archiv abgelegt;
   NO_QUORUM-Runden persistieren NICHTS.

Ehrliche Grenzen:
- UNIT_TESTED != API_INTEGRATION_VERIFIED: alle Provider simuliert,
  kein Netz, keine Credentials, keine echten APIs.
- ENTSCHEIDUNG != AUSFUEHRUNG: ACCEPT autorisiert nichts.
- SIGNATUR != WAHRHEIT: HMAC/Ed25519 beweisen Urheberschaft, nicht
  die Richtigkeit einer Bewertung.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path as _P

import pytest

from controller.agent_consensus import Decision, evaluate_consensus, sign_vote
from controller.consensus_archive import ConsensusArchive
from controller.crypto_receipts import generate_signing_keypair
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
from controller.quorum_ledger import build_signed_vote
from controller.review_receipt import build_review_receipt

DIGEST = hashlib.sha256(b"xl matrix immutable proposal").hexdigest()
EPOCH = 4
VOTE_NOW = 100          # Uhr fuer Stimmen (issued_at)
ROUND_NOW = 1           # Uhr fuer Health-Advisory (eigene Skala)
PROPOSAL = Proposal(DIGEST, EPOCH)

MEMBERS = {
    "agent-a": b"a" * 32,
    "agent-b": b"b" * 32,
    "agent-c": b"c" * 32,
    "agent-d": b"d" * 32,
    "agent-e": b"e" * 32,
}
FLOORS = {name: 0 for name in MEMBERS}


def _vote(agent: str, sequence: int = 1, approve: bool = True):
    return sign_vote(
        agent_id=agent,
        proposal_digest=DIGEST,
        epoch=EPOCH,
        sequence=sequence,
        issued_at=VOTE_NOW,
        approve=approve,
        agent_key=MEMBERS[agent],
    )


def ok_provider(agent: str, calls: list, sequence: int = 1) -> Provider:
    def invoke(proposal: Proposal):
        calls.append(agent)
        return _vote(agent, sequence=sequence)
    return Provider(agent, "boundary-" + agent, invoke)


def fault_provider(agent: str, calls: list, fault: Exception) -> Provider:
    def invoke(proposal: Proposal):
        calls.append(agent)
        raise fault
    return Provider(agent, "boundary-" + agent, invoke)


def run_round(providers, *, health=None, cancel_scope=None, quorum=2):
    """Kette sammeln -> auswerten, so wie der Rufer sie ordnen muss."""
    if health is not None:
        batch = collect_provider_votes(
            PROPOSAL, providers,
            health=health, now=ROUND_NOW, cancel_scope=cancel_scope,
        )
    else:
        batch = collect_provider_votes(
            PROPOSAL, providers, cancel_scope=cancel_scope,
        )
    # VIBE-XLI CANCEL-GUARD (Rufer-Vertrag aus VoteBatch.cancelled):
    # Eine abgebrochene Runde ist GESCHEITERT, egal wie viele gueltige
    # Stimmen vorher gesammelt wurden. Teilquorums sind unzulaessig,
    # deshalb werden die Stimmen einer abgebrochenen Runde NIE ausgewertet
    # (CANCELLED != PARTIAL QUORUM), und es wird nichts persistiert.
    effective_votes = [] if batch.cancelled else list(batch.votes)
    result = evaluate_consensus(
        effective_votes,
        member_keys=MEMBERS,
        proposal_digest=DIGEST,
        epoch=EPOCH,
        now=VOTE_NOW,
        min_sequence_by_agent=FLOORS,
        quorum=quorum,
    )
    return batch, result


# --- T-01: UNKNOWN ist nie HEALTHY (Cold-Start erlaubt, keine Behauptung) ---

def test_t01_unknown_status_allows_cold_start_but_never_claims_health():
    pol = ProviderHealthPolicy()
    advisory = pol.advisory("agent-a", now=ROUND_NOW)
    assert advisory.status is HealthStatus.UNKNOWN
    assert advisory.status is not HealthStatus.HEALTHY   # UNKNOWN != HEALTHY
    assert advisory.allow is True                        # Cold-Start erlaubt
    snapshot = pol.snapshot("agent-a")
    assert snapshot["known"] is False                    # keine Claim-Lage
    calls: list = []
    _, result = run_round([ok_provider("agent-a", calls)], health=pol, quorum=1)
    assert calls == ["agent-a"]                          # Call fand statt
    # Erst das aufgezeichnete OK-Ereignis begründet HEALTHY; behauptet
    # wurde es von keinem Advisory.
    assert pol.status("agent-a", now=ROUND_NOW) is HealthStatus.HEALTHY
    assert result.decision is Decision.ACCEPT


# --- T-02: Gesundheitsuebergaenge, Besitzer-Reset statt Selbstheilung ---

def test_t02_degraded_after_failures_and_owner_only_clear():
    pol = ProviderHealthPolicy(degraded_after=2, unavailable_after=4)
    # Zwei harte Fehler -> COOLDOWN (Retriedruck sinkt, Call gesperrt),
    # nach Ablauf der Cooldown-Frist DEGRADED (wachsam erlaubt).
    for _ in range(2):
        pol.record("agent-a", HealthEvent(HealthEventKind.PROVIDER_ERROR, now=1), now=1)
    assert pol.status("agent-a", now=1) is HealthStatus.COOLDOWN
    assert pol.advisory("agent-a", now=1).allow is False
    assert pol.status("agent-a", now=62) is HealthStatus.DEGRADED
    assert pol.advisory("agent-a", now=62).allow is True
    # Vier harte Fehler gesamt -> UNAVAILABLE, Advisory sperrt dauerhaft
    # fail-closed (keine stille Selbstheilung).
    for _ in range(2):
        pol.record("agent-a", HealthEvent(HealthEventKind.PROVIDER_ERROR, now=62), now=62)
    assert pol.status("agent-a", now=62) is HealthStatus.UNAVAILABLE
    assert pol.advisory("agent-a", now=62).allow is False
    # Besitzer-Reset statt Selbstheilung, danach offen.
    pol.clear("agent-a")
    # VIBE-XLI REGRESSION: clear() erzeugt keine Gesundheitsevidenz:
    # ohne ein einziges OK bleibt der Zustand UNKNOWN (CLEAR != HEALTH-PROOF).
    assert pol.status("agent-a", now=62) is HealthStatus.UNKNOWN


# --- T-03: Abbruch vor der Runde -> kein Call, kein Quorum -------------

def test_t03_pre_cancelled_round_contacts_no_provider_and_yields_no_quorum():
    calls: list = []
    scope = CancelScope()
    scope.cancel(DIGEST, reason="operator stop")
    batch, result = run_round(
        [ok_provider("agent-a", calls), ok_provider("agent-b", calls)],
        cancel_scope=scope, quorum=2,
    )
    assert calls == []                                   # kein Kontakt
    assert batch.votes == ()
    assert all("round cancelled" in f for f in batch.failures)
    assert result.decision is Decision.NO_QUORUM
    assert result.valid_approvals == 0


# --- T-04: Abbruch waehrend der Runde -> kein falsches Quorum -----------

def test_t04_mid_round_cancel_stops_remaining_providers_no_false_quorum():
    calls: list = []
    scope = CancelScope()
    first_agent, late_agent = "agent-a", "agent-b"
    inner = ok_provider(first_agent, calls)

    def cancelling_invoke(proposal: Proposal):
        result = inner.invoke(proposal)
        scope.cancel(proposal.digest, reason="mid-round stop")
        return result

    first = Provider(first_agent, inner.independence_id, cancelling_invoke)
    late = ok_provider(late_agent, calls)
    batch, result = run_round([first, late], cancel_scope=scope, quorum=2)
    assert calls == [first_agent]                        # agent-b unberuehrt
    assert [v.agent_id for v in batch.votes] == [first_agent]
    assert any("round cancelled" in f for f in batch.failures)
    # VIBE-XLI: Die Teilstimme bleibt im Batch belegtbar, zaehlt aber NICHT:
    # die abgebrochene Runde wird nie ausgewertet (guard in run_round).
    assert batch.cancelled is True
    assert batch.cancellation_digest == DIGEST
    assert result.decision is Decision.NO_QUORUM
    assert result.valid_approvals == 0


# --- T-05: Providerausfall = fehlende Stimme, nie Vetozahl --------------

@pytest.mark.parametrize("fault", [
    RuntimeError("simulated outage"),
    TimeoutError("deadline exceeded"),
])
def test_t05_provider_fault_is_missing_vote_not_veto(fault):
    calls: list = []
    pol = ProviderHealthPolicy()
    bad = fault_provider("agent-a", calls, fault)
    good = ok_provider("agent-b", calls)
    batch, result = run_round([bad, good], health=pol, quorum=2)
    assert calls == ["agent-a", "agent-b"]
    assert [v.agent_id for v in batch.votes] == ["agent-b"]
    assert len(batch.failures) == 1
    assert result.decision is Decision.NO_QUORUM
    assert result.valid_approvals == 1
    # Ausfall wird beim Provider angerechnet, nie als Stimme gezaehlt.
    snap = pol.snapshot("agent-a")
    assert snap["total_failures"] == 1
    assert snap["last_event"] == "PROVIDER_ERROR"


# --- T-06: Kapazitaetsunterdeckung erzwingt NO_QUORUM -------------------

def test_t06_capacity_shortfall_forces_no_quorum_on_real_chain():
    calls: list = []
    pol = ProviderHealthPolicy()
    for name in ("agent-c", "agent-d", "agent-e"):
        pol.exclude(name, reason="maintenance")
    providers = [ok_provider(name, calls) for name in sorted(MEMBERS)]
    # Pre-Flight: weniger erlaubte Provider als Quorum-Schwelle.
    capacity = pol.quorum_capacity(tuple(sorted(MEMBERS)), now=ROUND_NOW)
    assert capacity == ("agent-a", "agent-b")
    assert len(capacity) < 3                             # 3 gefordert
    batch, result = run_round(providers, health=pol, quorum=3)
    assert sorted(calls) == ["agent-a", "agent-b"]       # Gesperrte unberuehrt
    assert len(batch.votes) == 2
    assert len(batch.failures) == 3
    assert all("health advisory" in f for f in batch.failures)
    assert result.decision is Decision.NO_QUORUM
    assert result.valid_approvals == 2


# --- T-07: Persistenz nur bei Quorum (Rufer-Pflicht, gepaartes Archiv) --

POLICY_XL = "policy-xl"


def _ledger_world(names):
    world = {}
    for name in names:
        private, public = generate_signing_keypair()
        world[name] = (private, public)
    return world


def _ledger_vote(world, name, sequence, approve=True, epoch=EPOCH):
    private, _ = world[name]
    return build_signed_vote(
        name, DIGEST, epoch, sequence, approve, VOTE_NOW, POLICY_XL, private)


def _ledger_receipt(world, name, vote_record):
    private, _ = world[name]
    return build_review_receipt(
        vote_record, provider="prov-" + name, model="model-xl",
        stance="APPROVE" if vote_record["approve"] else "REJECT",
        rationale="runbook r-xl checked",
        evidence=["runbook://r-xl"], private_key=private)


def test_t07_only_quorum_rounds_are_persisted_by_the_caller():
    world = _ledger_world(["alpha", "beta"])
    keys = {name: world[name][1] for name in world}
    with tempfile.TemporaryDirectory() as tmp:
        archive = ConsensusArchive(_P(tmp), keys)
        # Runde 1 (Epoche 4): zwei Zustimmungen -> Rufer persistiert
        # die gepaarten Belege, Archiv bleibt fail-closed ladbar.
        sequence = 0
        for name in sorted(world):
            sequence += 1
            vote = _ledger_vote(world, name, sequence)
            archive.cast_vote(vote, _ledger_receipt(world, name, vote))
        accepted = archive.evaluate_reviews(
            proposal_digest=DIGEST, epoch=EPOCH, now=VOTE_NOW,
            expected_policy_version=POLICY_XL, min_sequence_by_agent={},
        )
        assert accepted["decision"] == "APPROVED_FOR_DOCUMENTATION"
        assert archive.entry_count() == 2
        # Runde 2 (Epoche 5, gespalten in der Simulation): der Rufer
        # entschliesst sich NICHT zum Persistieren, weil kein Quorum
        # feststeht. Das Archiv erzeugt deshalb keine Eintraege und
        # erlaubt fuer Epoche 5 keine Approval-Behauptung.
        skipped = archive.evaluate_reviews(
            proposal_digest=DIGEST, epoch=5, now=VOTE_NOW,
            expected_policy_version=POLICY_XL, min_sequence_by_agent={},
        )
        assert skipped["decision"] != "APPROVED_FOR_DOCUMENTATION"
        assert skipped["archive_entry_count"] == 2
        # Keine neue Quorum-Runde -> Zaehler unveraendert, Reload sauber.
        reloaded = ConsensusArchive(_P(tmp), keys)
        assert reloaded.entry_count() == 2


# --- T-08: Fremde Stimme bleibt Sondermuell, blockiert keinen Slot ------

def test_t08_foreign_vote_is_invalid_and_blocks_no_slot():
    calls: list = []
    foreign = Provider(
        "agent-x", "boundary-x",
        lambda proposal: sign_vote(
            agent_id="agent-x", proposal_digest=DIGEST, epoch=EPOCH,
            sequence=1, issued_at=VOTE_NOW, approve=True,
            agent_key=b"x" * 32),
    )
    _, result = run_round(
        [foreign, ok_provider("agent-a", calls)], quorum=1)
    assert any("unknown member" in r for r in result.invalid_votes)
    # Ordnungsunabhaengigkeit: die fremde Stimme hat den Slot von
    # agent-a nie blockiert; die gueltige Stimme entscheidet allein.
    assert result.decision is Decision.ACCEPT
    assert result.valid_approvals == 1
    assert result.accepted_agents == ("agent-a",)


# --- T-11: Abbruch trotz erreichtem Teilquorum (Q=1) -> NO_QUORUM -------

def test_t11_mid_round_cancel_with_quorum_one_never_accepts_partial_vote():
    """VIBE-XLI REGRESSION (externer Gegenbefund): Bei quorum=1 duerfen
    vor dem Abbruch gesammelte Stimmen kein ACCEPT erzeugen. Der VoteBatch
    trägt das bindende Abbruchkennzeichen, der Rufer-Guard wertet die
    Stimmen einer abgebrochenen Runde nie aus."""
    calls: list = []
    scope = CancelScope()
    inner = ok_provider("agent-a", calls)

    def cancelling_invoke(proposal: Proposal):
        result = inner.invoke(proposal)
        scope.cancel(proposal.digest, reason="stop after first vote")
        return result

    first = Provider("agent-a", inner.independence_id, cancelling_invoke)
    ok_agent = ok_provider("agent-b", calls)
    batch, result = run_round([first, ok_agent], cancel_scope=scope, quorum=1)
    assert calls == ["agent-a"]                     # die Stimme wurde real gesammelt
    assert [v.agent_id for v in batch.votes] == ["agent-a"]
    assert batch.cancelled is True
    assert batch.cancellation_digest == DIGEST
    # Genau hier lag die Luecke: Q=1 + eine Teilstimme != ACCEPT.
    assert result.decision is Decision.NO_QUORUM
    assert result.valid_approvals == 0


# --- T-12: Abbruch-Digest-Bindung: falscher Digest wird offengelegt -----

def test_t12_cancellation_digest_mismatch_is_disclosed_and_fail_closed():
    """Ein fuer einen ANDEREN Proposal-Digest gesetzter Abbruch stoppt
    die Runde trotzdem (fail-closed), wird aber nie verschwiegen."""
    scope = CancelScope()
    scope.cancel("f" * 64, reason="cancel token from a different round")
    batch, result = run_round(
        [ok_provider("agent-a", [], 1)], cancel_scope=scope, quorum=1,
    )
    assert batch.cancelled is True
    assert batch.cancellation_digest == "f" * 64
    assert any("digest mismatch" in f for f in batch.failures)
    assert result.decision is Decision.NO_QUORUM


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
