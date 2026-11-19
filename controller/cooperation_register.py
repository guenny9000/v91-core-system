#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Local cooperation register for V91 peers (Issue #37, item 4+7).

A local, per-peer overview of what THIS node has VERIFIED about its
peers. It records LAST_SEEN, sequence, software_version, capabilities,
health and trust_state per peer, plus open CONFLICTS. It is a view of
evidence, never a claim of global truth.

Rules (fail-closed everywhere):
- Only VERIFIED observations (signature, freshness and replay checks
  already passed in a separately reviewed module such as
  controller/peer_sync.py or controller/federation_receiver.py) update
  a peer's view. Unverified or invalid data is counted as a failed
  attempt and NEVER upgrades health (UNKNOWN != PASS).
- DETECTION != AUTHORIZATION: a recorded heartbeat grants no execution
  rights, no remote access, and merges nothing.
- CONFLICT, no auto-overwrite: an equal sequence with different content,
  or a lower sequence, is recorded as an open conflict; the last already
  VERIFIED view remains in place until Sebastian (operator) resolves it
  explicitly. ISOLATE_NOT_DESTROY: conflict data is kept, never deleted.
- Freshness is evaluated at READ time against the registered max age:
  a peer without a fresh verified heartbeat reads as STALE, never as
  healthy.

Honest limits (DOCUMENTED != IMPLEMENTED here):
- NO global status: this register deliberately offers no merged/global
  view, because no complete, time-consistent evidence base exists
  (issue #37 item 4). aggregation is refused, not approximated.
- In-memory MVP: no persistence, no background timers, no network; the
  caller drives the clock via now_provider.
- Replay/freshness/signature verification itself is NOT re-done here;
  the register trusts its caller's verification RESULT only far enough
  to file it as evidence, and requires it as an explicit argument.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable

SCHEMA_VERSION = 1
HEALTHY_STATE = "ALIVE_VERIFIED"
STALE_STATE = "STALE"
UNKNOWN_STATE = "UNKNOWN"
CONFLICT_DIVERGENT = "CONFLICT_DIVERGENT_DUPLICATE"
CONFLICT_OUTDATED = "CONFLICT_OUTDATED_SEQUENCE"
RESOLVED_STATE = "RESOLVED_BY_OPERATOR"
VERIFIED_STATES = frozenset({HEALTHY_STATE})


class RegisterError(ValueError):
    """Raised when the register contract is violated (fail-closed)."""


@dataclass(frozen=True)
class Verification:
    """Evidence object from a separately reviewed verification module.

    state must be an affirmative, verified state string (default
    ALIVE_VERIFIED as produced by controller/peer_sync.PeerRegistry);
    anything else makes the observation non-evidence by construction.
    """

    state: str
    reason: str
    signature_checked: bool = True
    freshness_checked: bool = True
    replay_checked: bool = True


_FAILED_VERIFICATION = Verification(state="INVALID", reason="unset", signature_checked=False,
                                     freshness_checked=False, replay_checked=False)


def verification_from_result(result: Any) -> Verification:
    """Adapt a peer_sync.PeerResult-like object into register evidence.

    Any missing attribute or non-verified state degrades to a failed
    verification; this never fabricates evidence (UNKNOWN != PASS).
    """
    try:
        state = str(result.state)
        reason = str(result.reason)
    except AttributeError:
        return _FAILED_VERIFICATION
    return Verification(
        state=state,
        reason=reason,
        signature_checked=state in VERIFIED_STATES,
        freshness_checked=state in VERIFIED_STATES,
        replay_checked=state in VERIFIED_STATES,
    )


@dataclass(frozen=True)
class Observation:
    """One heartbeat observation offered to the register."""

    peer_id: str
    key_id: str
    sequence: int
    received_at: float
    software_version: str
    capabilities: tuple[str, ...]
    state: str
    verification: Verification

    def content_key(self) -> tuple[Any, ...]:
        # The peer's runtime state (READY/BUSY/...) is volatile by design and
        # is not part of the divergence check; identity-relevant content is.
        return (self.peer_id, self.key_id, self.software_version,
                tuple(sorted(self.capabilities)))


@dataclass
class PeerView:
    """The register's current, evidence-backed view of ONE peer."""

    peer_id: str
    key_id: str = ""
    last_sequence: int = 0
    last_seen: float | None = None
    software_version: str = ""
    capabilities: tuple[str, ...] = ()
    state: str = UNKNOWN_STATE
    verified_observations: int = 0
    failed_attempts: int = 0
    open_conflicts: list[dict[str, Any]] = field(default_factory=list)

    def health(self, *, now: float, max_age_seconds: float) -> str:
        """Freshness is re-evaluated at read time, never assumed."""
        if self.last_seen is None or self.state not in VERIFIED_STATES:
            return UNKNOWN_STATE
        age = float(now) - float(self.last_seen)
        if not math.isfinite(age) or age > max_age_seconds:
            return STALE_STATE
        return HEALTHY_STATE


@dataclass(frozen=True)
class RecordOutcome:
    """What the register did with one offered observation."""

    peer_id: str | None
    status: str
    reason: str
    conflict_recorded: bool = False
    view_updated: bool = False


def _require_observation_shapes(observation: Observation) -> None:
    for name in ("peer_id", "key_id", "software_version"):
        value = getattr(observation, name)
        if not isinstance(value, str) or not value.strip():
            raise RegisterError(f"{name} must be a non-empty string")
    sequence = observation.sequence
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise RegisterError("sequence must be a positive integer")
    received_at = observation.received_at
    if isinstance(received_at, bool) or not isinstance(received_at, (int, float)):
        raise RegisterError("received_at must be numeric")
    if not math.isfinite(float(received_at)):
        raise RegisterError("received_at must be finite")
    capabilities = observation.capabilities
    if not isinstance(capabilities, (tuple, list)) or any(
        not isinstance(item, str) or not item for item in capabilities
    ):
        raise RegisterError("capabilities must be non-empty strings")
    if len(set(capabilities)) != len(capabilities):
        raise RegisterError("capabilities must be unique")
    if not isinstance(observation.state, str) or not observation.state:
        raise RegisterError("state must be a non-empty string")
    if not isinstance(observation.verification, Verification):
        raise RegisterError("a Verification evidence object is required")


class CooperationRegister:
    """Local per-peer evidence register. No global view, no authority."""

    def __init__(
        self,
        *,
        max_age_seconds: float = 90.0,
        now_provider: Callable[[], float] | None = None,
    ) -> None:
        if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, (int, float)):
            raise RegisterError("max_age_seconds must be numeric")
        if not math.isfinite(float(max_age_seconds)) or max_age_seconds <= 0:
            raise RegisterError("max_age_seconds must be a positive finite number")
        self._max_age_seconds = float(max_age_seconds)
        self._now = now_provider or time.time
        self._views: dict[str, PeerView] = {}
        self._history: list[dict[str, Any]] = []

    @property
    def max_age_seconds(self) -> float:
        return self._max_age_seconds

    def _now_value(self) -> float:
        now = self._now()
        if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(float(now)):
            raise RegisterError("now_provider returned a non-finite value")
        return float(now)

    def record(self, observation: Observation) -> RecordOutcome:
        """File one observation. Only verified evidence updates a view."""
        if not isinstance(observation, Observation):
            raise RegisterError("record expects an Observation")
        _require_observation_shapes(observation)

        verification = observation.verification
        is_verified = (
            verification.signature_checked
            and verification.freshness_checked
            and verification.replay_checked
            and verification.state in VERIFIED_STATES
        )

        view = self._views.get(observation.peer_id)
        if view is None:
            view = PeerView(peer_id=observation.peer_id)
            self._views[observation.peer_id] = view

        if not is_verified:
            view.failed_attempts += 1
            self._history.append({
                "event": "FAILED_ATTEMPT", "peer_id": observation.peer_id,
                "reason": verification.reason, "claimed_state": verification.state,
            })
            return RecordOutcome(
                observation.peer_id, "NOT_VERIFIED",
                f"verification state {verification.state!r} is not evidence; "
                "counted as failed attempt only",
            )

        if view.state in VERIFIED_STATES:
            if observation.sequence == view.last_sequence:
                if observation.content_key() == self._content_key_of(view):
                    return RecordOutcome(
                        observation.peer_id, "IDEMPOTENT_REPLAY_KNOWN",
                        "identical verified duplicate; view unchanged",
                    )
                conflict = self._conflict(
                    view, CONFLICT_DIVERGENT,
                    f"sequence {observation.sequence} already verified with different "
                    "content; divergence filed as conflict",
                    observation,
                )
                return RecordOutcome(
                    observation.peer_id, "CONFLICT", conflict["reason"],
                    conflict_recorded=True,
                )
            if observation.sequence < view.last_sequence:
                conflict = self._conflict(
                    view, CONFLICT_OUTDATED,
                    f"verified but outdated sequence {observation.sequence} < "
                    f"{view.last_sequence}; filed as conflict, view kept",
                    observation,
                )
                return RecordOutcome(
                    observation.peer_id, "CONFLICT", conflict["reason"],
                    conflict_recorded=True,
                )

        self._apply_verified(view, observation)
        return RecordOutcome(
            observation.peer_id, "VERIFIED_RECORDED",
            "verified observation recorded; view updated",
            view_updated=True,
        )

    @staticmethod
    def _content_key_of(view: PeerView) -> tuple[Any, ...]:
        return (view.peer_id, view.key_id, view.software_version,
                tuple(sorted(view.capabilities)))

    def _apply_verified(self, view: PeerView, observation: Observation) -> None:
        view.key_id = observation.key_id
        view.last_sequence = observation.sequence
        view.last_seen = float(observation.received_at)
        view.software_version = observation.software_version
        view.capabilities = tuple(observation.capabilities)
        view.state = HEALTHY_STATE
        view.verified_observations += 1
        self._history.append({
            "event": "VERIFIED", "peer_id": observation.peer_id,
            "sequence": observation.sequence,
            "software_version": observation.software_version,
        })

    def _conflict(
        self, view: PeerView, kind: str, reason: str, observation: Observation,
    ) -> dict[str, Any]:
        conflict = {
            "kind": kind,
            "reason": reason,
            "observed_sequence": observation.sequence,
            "observed_version": observation.software_version,
            "observed_key_id": observation.key_id,
            "kept_sequence": view.last_sequence,
            "kept_version": view.software_version,
            "resolved": False,
        }
        view.open_conflicts.append(conflict)
        self._history.append({
            "event": kind, "peer_id": observation.peer_id,
            "sequence": observation.sequence,
        })
        return conflict

    def resolve_conflict(self, peer_id: str, *, resolution: str, reason: str) -> dict[str, Any]:
        """Explicit operator resolution. The register merges nothing itself.

        Clearing a conflict is a bookkeeping act by an explicit, audited
        operator decision; it changes no verified view data here.
        """
        if not isinstance(peer_id, str) or not peer_id.strip():
            raise RegisterError("peer_id must be a non-empty string")
        if not isinstance(resolution, str) or not resolution.strip() or len(resolution) > 64:
            raise RegisterError("a non-empty resolution label (<= 64 chars) is required")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 512:
            raise RegisterError("a non-empty resolution reason (<= 512 chars) is required")
        view = self._views.get(peer_id)
        if view is None:
            raise RegisterError(f"peer {peer_id!r} is not on the register")
        open_conflicts = [c for c in view.open_conflicts if not c["resolved"]]
        if not open_conflicts:
            raise RegisterError(f"peer {peer_id!r} has no open conflict to resolve")
        for conflict in open_conflicts:
            conflict["resolved"] = True
            conflict["resolution"] = resolution
            conflict["resolution_reason"] = reason
        self._history.append({
            "event": RESOLVED_STATE, "peer_id": peer_id,
            "resolution": resolution, "count": len(open_conflicts),
        })
        return {"peer_id": peer_id, "resolved": len(open_conflicts)}

    def view(self, peer_id: str) -> dict[str, Any] | None:
        """Public read: a copy with READ-TIME health; no internal state leaks."""
        if not isinstance(peer_id, str) or not peer_id:
            raise RegisterError("peer_id must be a non-empty string")
        internal = self._views.get(peer_id)
        if internal is None:
            return None
        now = self._now_value()
        return {
            "schema_version": SCHEMA_VERSION,
            "peer_id": internal.peer_id,
            "key_id": internal.key_id,
            "last_sequence": internal.last_sequence,
            "last_seen": internal.last_seen,
            "software_version": internal.software_version,
            "capabilities": list(internal.capabilities),
            "recorded_state": internal.state,
            "health": internal.health(now=now, max_age_seconds=self._max_age_seconds),
            "verified_observations": internal.verified_observations,
            "failed_attempts": internal.failed_attempts,
            "open_conflicts": [dict(c) for c in internal.open_conflicts],
        }

    def overview(self) -> dict[str, Any]:
        """Per-peer overview ONLY. A merged/global status is refused by design."""
        now = self._now_value()
        peers = {}
        for peer_id, internal in sorted(self._views.items()):
            peers[peer_id] = {
                "health": internal.health(now=now, max_age_seconds=self._max_age_seconds),
                "software_version": internal.software_version,
                "last_sequence": internal.last_sequence,
                "open_conflicts": sum(1 for c in internal.open_conflicts if not c["resolved"]),
            }
        return {
            "schema_version": SCHEMA_VERSION,
            "peers": peers,
            "global_status": "REFUSED: no complete, time-consistent evidence base "
            "(issue #37 item 4; a merged status would be a claim, not evidence)",
        }

    def event_log(self) -> list[dict[str, Any]]:
        """Audit trail copy: events are kept, never rewritten or deleted."""
        return [dict(event) for event in self._history]

    def export_report(self, *, include_event_log: bool = True) -> dict[str, Any]:
        """Deterministic machine-readable snapshot of THIS local register.

        The export is a COPY of the register's evidence-backed view:
        read-time health evaluated against the registered max age, peers
        in sorted order, events kept (ISOLATE_NOT_DESTROY). No wall
        clock is consulted; the caller drives time via now_provider, so
        two exports at the same logical time are identical.

        Honest limits, by construction:
        - No global status: an export is a LOCAL view and merges
          nothing; a merged status would be a claim, not evidence
          (issue #37 item 4).
        - EXPORT != BROADCAST: handing this dict to another system is
          an explicit, audited caller decision and grants no rights.
        """
        if not isinstance(include_event_log, bool):
            raise RegisterError("include_event_log must be a boolean")
        now = self._now_value()
        peers: dict[str, Any] = {}
        for peer_id, internal in sorted(self._views.items()):
            peers[peer_id] = {
                "key_id": internal.key_id,
                "last_sequence": internal.last_sequence,
                "last_seen": internal.last_seen,
                "software_version": internal.software_version,
                "capabilities": list(internal.capabilities),
                "recorded_state": internal.state,
                "health": internal.health(
                    now=now, max_age_seconds=self._max_age_seconds),
                "verified_observations": internal.verified_observations,
                "failed_attempts": internal.failed_attempts,
                "open_conflicts": sum(
                    1 for c in internal.open_conflicts if not c["resolved"]),
                "conflicts": [dict(c) for c in internal.open_conflicts],
            }
        report: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "report_kind": "LOCAL_REGISTER_EXPORT",
            "peers": peers,
            "peer_count": len(peers),
            "max_age_seconds": self._max_age_seconds,
            "event_log_included": include_event_log,
            "global_status": "REFUSED: export is a local evidence view, "
                             "not a global truth (issue #37 item 4)",
        }
        if include_event_log:
            report["event_log"] = [dict(event) for event in self._history]
        return report
