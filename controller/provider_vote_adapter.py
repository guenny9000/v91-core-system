"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Opt-in, injected provider adapter for proposal-only vote collection.

This module does not hold credentials, sign votes, persist replay floors, or
execute actions. Provider callables must return independently authenticated
Vote objects; callers remain responsible for provider authentication,
timeouts/cancellation, durable replay state, and consensus evaluation.

Honest limits (CLAIM != EVIDENCE):

1. ADAPTER != PROVIDER: no provider is contacted, loaded or configured
   here; every provider callable is injected and caller-owned.
2. COLLECTION != CONSENSUS: votes are collected, never evaluated; quorum
   logic stays in agent_quorum/quorum_ledger (NO_DUPLICATE_SYSTEMS).
3. SIGNATURE != TRUTH: a valid vote proves authorship, not correctness.
4. The configured independence boundary is an operator assertion; this
   module rejects duplicate identities but cannot prove that two
   providers are genuinely independent (UNKNOWN != PASS).
5. SCRIPTED != INSTALLED: no network I/O, no persistence, no daemon.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from controller.agent_consensus import Vote
from controller.provider_health import (
    CancelScope,
    HealthEvent,
    HealthEventKind,
    ProviderHealthPolicy,
)


@dataclass(frozen=True)
class Proposal:
    """Immutable proposal identity shared with every configured reviewer."""

    digest: str
    epoch: int


@dataclass(frozen=True)
class Provider:
    """An explicitly configured reviewer.

    independence_id must identify the independently provisioned reviewer
    boundary (not merely a display name). Reusing it is rejected.
    """

    agent_id: str
    independence_id: str
    invoke: Callable[[Proposal], Vote]


@dataclass(frozen=True)
class VoteBatch:
    votes: tuple[Vote, ...]
    failures: tuple[str, ...]


def collect_provider_votes(
    proposal: Proposal,
    providers: Iterable[Provider],
    *,
    health: ProviderHealthPolicy | None = None,
    cancel_scope: CancelScope | None = None,
    now: int | None = None,
) -> VoteBatch:
    """Collect signed votes only; never evaluates quorum or executes actions.

    Calls are synchronous and sequential. A provider that can hang must be
    wrapped by the caller in a timeout-capable worker/process.

    Optional health/cancellation wiring (VIBE-XL, Issue #167 point 8):

    - With `health`, every outcome is recorded per agent_id (OK on a valid
      accepted vote, PROVIDER_ERROR on exception or invalid response,
      CANCELLED when the round is stopped; CANCELLED never blames the
      provider). A blocked advisory skips the call: an outage stays a
      MISSING VOTE, never a verdict (FAIL != APPROVE).
    - With `cancel_scope`, the cooperative scope is checked before every
      provider call; a cancelled round stops without contacting the
      remaining providers.
    - `now` is REQUIRED when `health` is given (UNKNOWN is never defaulted;
      failing to pass a clock is a configuration error, not a guess).
    - NO_QUORUM capacity enforcement stays with agent_consensus via
      quorum_capacity (REUSE: COLLECTION != CONSENSUS); this adapter
      surfaces missing votes, it does not evaluate them.
    """
    configured = tuple(providers)
    if not configured:
        raise ValueError("at least one provider must be explicitly configured")

    agent_ids = [item.agent_id for item in configured]
    independence_ids = [item.independence_id for item in configured]
    if any(not isinstance(value, str) or not value.strip()
           for value in agent_ids + independence_ids):
        raise ValueError("provider and independence IDs must be non-empty")
    if len(set(agent_ids)) != len(agent_ids):
        raise ValueError("duplicate agent_id is not independent")
    if len(set(independence_ids)) != len(independence_ids):
        raise ValueError("duplicate independence_id is not independent")
    if any(not callable(item.invoke) for item in configured):
        raise ValueError("every provider requires an injected callable")
    if health is not None and (not isinstance(now, int) or now < 0):
        raise ValueError("now (clock) is required when health is given")

    def record(agent_id, kind, detail=""):
        if health is None:
            return
        health.record(agent_id, HealthEvent(kind, now=now, detail=detail), now=now)

    accepted: list[Vote] = []
    failures: list[str] = []
    for provider in configured:
        if cancel_scope is not None and cancel_scope.cancelled:
            reason = cancel_scope.cancellation.reason if cancel_scope.cancellation else ""
            failures.append(
                f"{provider.agent_id}: round cancelled: {reason}"
            )
            record(provider.agent_id, HealthEventKind.CANCELLED,
                   "round cancelled before call")
            continue

        if health is not None:
            adv = health.advisory(provider.agent_id, now=now)
            if not adv.allow:
                failures.append(
                    f"{provider.agent_id}: health advisory: {adv.reason}"
                )
                continue

        try:
            vote = provider.invoke(proposal)
        except Exception as exc:  # provider failure is data, not approval
            failures.append(f"{provider.agent_id}: provider error: {type(exc).__name__}")
            record(provider.agent_id, HealthEventKind.PROVIDER_ERROR,
                   type(exc).__name__)
            continue

        if not isinstance(vote, Vote):
            failures.append(f"{provider.agent_id}: returned value is not a Vote")
            record(provider.agent_id, HealthEventKind.PROVIDER_ERROR,
                   "not a Vote")
            continue
        if vote.agent_id != provider.agent_id:
            failures.append(f"{provider.agent_id}: signed agent identity mismatch")
            record(provider.agent_id, HealthEventKind.PROVIDER_ERROR,
                   "agent identity mismatch")
            continue
        if vote.proposal_digest != proposal.digest or vote.epoch != proposal.epoch:
            failures.append(f"{provider.agent_id}: proposal identity mismatch")
            record(provider.agent_id, HealthEventKind.PROVIDER_ERROR,
                   "proposal identity mismatch")
            continue
        accepted.append(vote)
        record(provider.agent_id, HealthEventKind.OK)

    return VoteBatch(tuple(accepted), tuple(failures))
