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
    proposal: Proposal, providers: Iterable[Provider]
) -> VoteBatch:
    """Collect signed votes only; never evaluates quorum or executes actions.

    Calls are synchronous and sequential. A provider that can hang must be
    wrapped by the caller in a timeout-capable worker/process.
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

    accepted: list[Vote] = []
    failures: list[str] = []
    for provider in configured:
        try:
            vote = provider.invoke(proposal)
        except Exception as exc:  # provider failure is data, not approval
            failures.append(f"{provider.agent_id}: provider error: {type(exc).__name__}")
            continue

        if not isinstance(vote, Vote):
            failures.append(f"{provider.agent_id}: returned value is not a Vote")
            continue
        if vote.agent_id != provider.agent_id:
            failures.append(f"{provider.agent_id}: signed agent identity mismatch")
            continue
        if vote.proposal_digest != proposal.digest or vote.epoch != proposal.epoch:
            failures.append(f"{provider.agent_id}: proposal identity mismatch")
            continue
        accepted.append(vote)

    return VoteBatch(tuple(accepted), tuple(failures))
