"""Expiring lease locks with monotonically increasing fencing tokens.

Issue #47, stage 6 groundwork. This is the single-process protocol
implementation with an injectable clock. A networked state store (real
distributed locks across nodes) is a later stage - NO distributed claim
is made here.

Fencing guarantee: every lease carries a token that strictly increases per
lock, even across expiry and re-acquisition. If a paused holder wakes up
after its lease expired and someone else took over, the old token is lower
than the last issued token and every guarded action is rejected
(is_fenced -> True). Late writes from stale holders cannot win.

Honest limits:
- In-memory state: restarting the process forgets leases (durable store is
  a later stage).
- A monotonic clock source must be injectable for deterministic tests;
  wall-clock drift between real nodes is not solved by this module.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional


class LeaseLockError(ValueError):
    """Raised when the lease contract is violated."""


@dataclass(frozen=True)
class Lease:
    lock_id: str
    holder_id: str
    fencing_token: int
    expires_at: float

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at


class LeaseLockManager:
    """Expiring leases with per-lock, strictly monotonic fencing tokens."""

    def __init__(self, clock: Optional[Callable[[], float]] = None) -> None:
        self._clock: Callable[[], float] = clock if clock is not None else time.monotonic
        self._leases: dict[str, Lease] = {}
        self._last_token: dict[str, int] = {}

    def _now(self) -> float:
        return self._clock()

    @staticmethod
    def _require_id(name: str, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise LeaseLockError(f"{name} must be a non-empty string")
        return value

    def acquire(self, lock_id: str, holder_id: str, duration: float) -> Optional[Lease]:
        """Acquire a free or expired lock; returns None if actively held."""
        self._require_id("lock_id", lock_id)
        self._require_id("holder_id", holder_id)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
            raise LeaseLockError("duration must be a positive number of seconds")
        now = self._now()
        current = self._leases.get(lock_id)
        if current is not None and not current.is_expired(now):
            return None
        token = self._last_token.get(lock_id, 0) + 1
        self._last_token[lock_id] = token
        lease = Lease(lock_id=lock_id, holder_id=holder_id,
                      fencing_token=token, expires_at=now + duration)
        self._leases[lock_id] = lease
        return lease

    def current(self, lock_id: str) -> Optional[Lease]:
        return self._leases.get(lock_id)

    def renew(self, lock_id: str, holder_id: str, fencing_token: int, duration: float) -> Lease:
        """Extend a live lease; only the current holder with the matching token may renew."""
        self._require_id("lock_id", lock_id)
        self._require_id("holder_id", holder_id)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
            raise LeaseLockError("duration must be a positive number of seconds")
        now = self._now()
        lease = self._leases.get(lock_id)
        if lease is None or lease.holder_id != holder_id or lease.fencing_token != fencing_token:
            raise LeaseLockError("only the current lease holder with the matching fencing token can renew")
        if lease.is_expired(now):
            raise LeaseLockError("lease already expired; renew refused (fail-closed)")
        renewed = Lease(lock_id=lock_id, holder_id=holder_id,
                        fencing_token=fencing_token, expires_at=now + duration)
        self._leases[lock_id] = renewed
        return renewed

    def release(self, lock_id: str, holder_id: str, fencing_token: int) -> None:
        """Release a held lease; only the current holder with the matching token may release."""
        self._require_id("lock_id", lock_id)
        self._require_id("holder_id", holder_id)
        lease = self._leases.get(lock_id)
        if lease is None:
            raise LeaseLockError("no lease held for this lock")
        if lease.holder_id != holder_id or lease.fencing_token != fencing_token:
            raise LeaseLockError("only the current lease holder with the matching fencing token can release")
        del self._leases[lock_id]

    def validate_action(self, lock_id: str, holder_id: str, fencing_token: int) -> bool:
        """Guard for every guarded action: current holder, matching token, not expired."""
        now = self._now()
        lease = self._leases.get(lock_id)
        if lease is None:
            return False
        if lease.holder_id != holder_id or lease.fencing_token != fencing_token:
            return False
        return not lease.is_expired(now)

    def is_fenced(self, lock_id: str, fencing_token: int) -> bool:
        """True if the token is stale (lower than the last issued token) - reject the action."""
        return fencing_token < self._last_token.get(lock_id, 0)
