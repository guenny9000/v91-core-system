"""V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Provider-Health-Policy and cooperative cancellation for the API-backed
review quorum (Issue #167, requirement 8).

Boundary (NO_DUPLICATE_SYSTEMS): the orchestration lives in
agent_quorum (#177), vote collection in provider_vote_adapter (#280),
adapter contract/budget/injection screening in quorum_provider, signature
and replay validation in agent_consensus. This module adds ONLY the
health/availability dimension: it records provider outcomes, exposes a
call advisory, and propagates cooperative cancellation. HEALTH != CONSENSUS,
HEALTH != EXECUTION.

Fail-closed core rules, by construction:
1. UNAVAILABLE is NEVER implicit approval. A provider that cannot be called
   contributes NO vote; missing votes can only produce NO_QUORUM in
   agent_consensus, never ACCEPT.
2. CANCELLED is never success. A cancelled round is recorded and must be
   treated as a failed review round by the caller.
3. No wall clock, no network, no persistence: time is injected, state is
   in-memory and owned by the caller.
4. Health labels are ADVISORIES, not evidence of provider independence and
   not proof that a provider worked correctly in the past.
5. HEALTHY requires at least ONE recorded OK outcome (EVIDENCE-BASED
   HEALTH). A history of only CANCELLED events, or a cleared failure
   history without a single success, stays UNKNOWN: unproven, not healthy
   (UNKNOWN != HEALTHY, CLEAR != HEALTH-PROOF).

Honest limits:
- HEALTHY is a claim from past call outcomes, not a guarantee for the next
  call (CLAIM != EVIDENCE).
- COOLDOWN reduces retry pressure; it cannot repair a broken provider.
- A provider that answers fine while returning wrong verdicts stays HEALTHY
  here; verdict quality is screened elsewhere (quorum_evaluator).
- SCRIPTED != INSTALLED: nothing here performs or blocks I/O by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class HealthEventKind(str, Enum):
    """Outcome of one provider interaction. Soft failures are transient
    signals (timeout, rate limit); hard failures are provider errors.
    CANCELLED is never a soft or hard failure record against the provider
    itself: the caller, not the provider, stopped the round."""

    OK = "OK"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    CANCELLED = "CANCELLED"


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    # UNKNOWN is a first-class status: a provider without call history is
    # not healthy, it is unproven (UNKNOWN != PASS, UNKNOWN != HEALTHY).
    UNKNOWN = "UNKNOWN"
    COOLDOWN = "COOLDOWN"
    UNAVAILABLE = "UNAVAILABLE"


_FAILURE_KINDS = frozenset({
    HealthEventKind.TIMEOUT,
    HealthEventKind.RATE_LIMITED,
    HealthEventKind.PROVIDER_ERROR,
})


class ProviderHealthError(Exception):
    """Invalid use of the health policy (fail-closed)."""


@dataclass(frozen=True)
class HealthEvent:
    kind: HealthEventKind
    now: int
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.now, int) or self.now < 0:
            raise ProviderHealthError("now must be a non-negative integer")
        if not isinstance(self.kind, HealthEventKind):
            raise ProviderHealthError("kind must be a HealthEventKind")


@dataclass
class _ProviderRecord:
    consecutive_failures: int = 0
    consecutive_rate_limits: int = 0
    total_failures: int = 0
    total_ok: int = 0
    total_cancelled: int = 0
    last_event: HealthEventKind | None = None
    last_event_at: int | None = None
    cooldown_until: int | None = None
    events: tuple[HealthEvent, ...] = ()


@dataclass(frozen=True)
class CallAdvisory:
    """Advisory for one provider at a point in time. allow=False always
    carries a provider-side reason; it NEVER carries a verdict."""

    provider_id: str
    allow: bool
    status: HealthStatus
    reason: str


@dataclass(frozen=True)
class RoundCancellation:
    """Immutable marker for one cancelled review round."""

    proposal_digest: str
    reason: str


class CancelScope:
    """Cooperative cancellation for a review round.

    The caller checks `cancelled` before each provider request and records
    a CANCELLED event if a request was in flight or skipped. Cancellation
    is caller-owned: this class never runs threads, signals or I/O.
    """

    def __init__(self) -> None:
        self.__cancelled: RoundCancellation | None = None

    @property
    def cancelled(self) -> bool:
        return self.__cancelled is not None

    @property
    def cancellation(self) -> RoundCancellation | None:
        return self.__cancelled

    def cancel(self, proposal_digest: str, reason: str) -> None:
        if not isinstance(proposal_digest, str) or not proposal_digest.strip():
            raise ProviderHealthError("proposal_digest required for cancellation")
        if not isinstance(reason, str) or not reason.strip():
            raise ProviderHealthError("reason required for cancellation")
        if self.__cancelled is None:
            self.__cancelled = RoundCancellation(
                proposal_digest=proposal_digest, reason=reason,
            )


class ProviderHealthPolicy:
    """Fail-closed health tracker for configured review providers.

    Thresholds are fixed at construction; they are advisory machinery, not
    consensus parameters. A provider marked UNAVAILABLE stays excluded
    until an explicit `clear` by the owner (no silent self-healing, because
    availability is a claim).
    """

    def __init__(
        self,
        *,
        degraded_after: int = 2,
        cooldown_seconds: int = 60,
        unavailable_after: int = 4,
        max_events_kept: int = 64,
    ) -> None:
        if degraded_after < 1 or unavailable_after < 1:
            raise ProviderHealthError("thresholds must be >= 1")
        if cooldown_seconds < 0 or max_events_kept < 1:
            raise ProviderHealthError("cooldown and max_events_kept must be >= 0/>= 1")
        if unavailable_after < degraded_after:
            raise ProviderHealthError(
                "unavailable_after must not be lower than degraded_after"
            )
        self.__degraded_after = degraded_after
        self.__cooldown_seconds = cooldown_seconds
        self.__unavailable_after = unavailable_after
        self.__max_events_kept = max_events_kept
        self.__records: dict[str, _ProviderRecord] = {}
        self.__manually_excluded: set[str] = set()

    # -- state transitions ------------------------------------------------

    def record(self, provider_id: str, event: HealthEvent, *, now: int) -> None:
        """Record one outcome. CANCELLED never counts against provider
        health: the caller stopped the round, so blaming the provider
        would be dishonest attribution."""
        self.__require_id(provider_id)
        if not isinstance(event, HealthEvent):
            raise ProviderHealthError("event must be a HealthEvent")
        rec = self.__records.setdefault(provider_id, _ProviderRecord())
        rec.last_event = event.kind
        rec.last_event_at = event.now
        kept = rec.events + (event,)
        rec.events = kept[-self.__max_events_kept:]
        if event.kind is HealthEventKind.OK:
            rec.consecutive_failures = 0
            rec.consecutive_rate_limits = 0
            rec.cooldown_until = None
            rec.total_ok += 1
            return
        if event.kind is HealthEventKind.CANCELLED:
            rec.total_cancelled += 1
            return
        # Soft and hard failures.
        rec.consecutive_failures += 1
        rec.total_failures += 1
        if event.kind is HealthEventKind.RATE_LIMITED:
            rec.consecutive_rate_limits += 1
        else:
            rec.consecutive_rate_limits = 0
        if rec.consecutive_failures >= self.__unavailable_after:
            self.__manually_excluded.discard(provider_id)  # superseded by hard state
            rec.cooldown_until = None
        elif rec.consecutive_failures >= self.__degraded_after:
            rec.cooldown_until = event.now + self.__cooldown_seconds

    def exclude(self, provider_id: str, *, reason: str) -> None:
        """Owner-decided pause (e.g. operator knows about an outage).
        Fail-closed: exclusion needs a reason and is always revocable."""
        self.__require_id(provider_id)
        if not isinstance(reason, str) or not reason.strip():
            raise ProviderHealthError("reason required for exclusion")
        self.__manually_excluded.add(provider_id)

    def clear(self, provider_id: str) -> None:
        """Revoke manual exclusion and reset failure counters. Owner-fired
        only: health state must not self-heal silently. clear() NEVER
        creates health evidence: without at least one recorded OK the
        status afterwards is UNKNOWN, not HEALTHY (CLEAR != HEALTH-PROOF)."""
        self.__require_id(provider_id)
        self.__manually_excluded.discard(provider_id)
        rec = self.__records.get(provider_id)
        if rec is not None:
            rec.consecutive_failures = 0
            rec.consecutive_rate_limits = 0
            rec.cooldown_until = None

    # -- queries ----------------------------------------------------------

    def status(self, provider_id: str, *, now: int) -> HealthStatus:
        self.__require_id(provider_id)
        if provider_id in self.__manually_excluded:
            return HealthStatus.UNAVAILABLE
        rec = self.__records.get(provider_id)
        if rec is None:
            # No call history is no evidence of health. The provider status
            # is UNKNOWN (not HEALTHY); the advisory still allows a cold
            # start call, but the status never claims unearned health.
            return HealthStatus.UNKNOWN
        if rec.consecutive_failures >= self.__unavailable_after:
            return HealthStatus.UNAVAILABLE
        if (
            rec.cooldown_until is not None
            and now < rec.cooldown_until
        ):
            return HealthStatus.COOLDOWN
        if rec.consecutive_failures >= self.__degraded_after:
            return HealthStatus.DEGRADED
        if rec.total_ok == 0:
            # History exists, but not a single OK outcome: failures below
            # the degraded threshold or only CANCELLED events. Availability
            # is a claim; unproven is UNKNOWN, never HEALTHY.
            return HealthStatus.UNKNOWN
        return HealthStatus.HEALTHY

    def advisory(self, provider_id: str, *, now: int) -> CallAdvisory:
        self.__require_id(provider_id)
        st = self.status(provider_id, now=now)
        rec = self.__records.get(provider_id)
        if st is HealthStatus.UNAVAILABLE:
            reason = "manually excluded" if provider_id in self.__manually_excluded else (
                "consecutive failures reached unavailable threshold"
            )
            return CallAdvisory(
                provider_id=provider_id, allow=False, status=st, reason=reason,
            )
        if st is HealthStatus.COOLDOWN:
            assert rec is not None and rec.cooldown_until is not None
            return CallAdvisory(
                provider_id=provider_id, allow=False, status=st,
                reason=f"cooldown until {rec.cooldown_until}",
            )
        if st is HealthStatus.DEGRADED:
            return CallAdvisory(
                provider_id=provider_id, allow=True, status=st,
                reason="recent failures; call allowed, watch closely",
            )
        if st is HealthStatus.UNKNOWN:
            reason = (
                "no call history (UNKNOWN != HEALTHY, assertion, not evidence)"
                if rec is None
                else "call history without a single success (UNKNOWN != HEALTHY)"
            )
            return CallAdvisory(
                provider_id=provider_id, allow=True, status=st, reason=reason,
            )
        if rec is None:
            return CallAdvisory(
                provider_id=provider_id, allow=True, status=st,
                reason="no call history (assertion, not evidence)",
            )
        return CallAdvisory(
            provider_id=provider_id, allow=True, status=st, reason="ok",
        )

    def callable_order(
        self, provider_ids, *, now: int
    ):
        """Order providers by health for the next round: healthy first,
        then degraded, then others. Excluded/cooldown providers keep their
        position but their advisory stays allow=False. The list is a call
        ORDER, never a vote, never a verdict."""
        ids = tuple(provider_ids)
        if len(set(ids)) != len(ids):
            raise ProviderHealthError("provider ids must be distinct")
        # UNKNOWN ranks after DEGRADED: a failing-but-allowed provider has
        # at least real call evidence; an unproven provider has none. This
        # is an ordering, never a verdict (ORDER != VOTE).
        rank = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNKNOWN: 2,
            HealthStatus.COOLDOWN: 3,
            HealthStatus.UNAVAILABLE: 4,
        }
        keyed = sorted(
            ((rank[self.status(i, now=now)], idx, i) for idx, i in enumerate(ids)),
        )
        return [i for _, _, i in keyed]

    def quorum_capacity(self, provider_ids, *, now: int) -> tuple[str, ...]:
        """Ids whose advisory currently allows a call. If fewer than the
        required quorum remain callable the round must end NO_QUORUM;
        the caller enforces that via agent_consensus (REUSE)."""
        ids = tuple(provider_ids)
        return tuple(
            i for i in ids if self.advisory(i, now=now).allow
        )

    def snapshot(self, provider_id: str) -> Mapping[str, int | str | None]:
        """Read-only disclosure for reports (CLAIM != EVIDENCE)."""
        rec = self.__records.get(provider_id)
        if rec is None:
            return {
                "known": False,
                "excluded": provider_id in self.__manually_excluded,
            }
        return {
            "known": True,
            "excluded": provider_id in self.__manually_excluded,
            "consecutive_failures": rec.consecutive_failures,
            "consecutive_rate_limits": rec.consecutive_rate_limits,
            "total_failures": rec.total_failures,
            "total_ok": rec.total_ok,
            "total_cancelled": rec.total_cancelled,
            "last_event": rec.last_event.value if rec.last_event else None,
            "last_event_at": rec.last_event_at,
            "cooldown_until": rec.cooldown_until,
        }

    @staticmethod
    def __require_id(provider_id: str) -> None:
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ProviderHealthError("provider_id must be a non-empty string")
