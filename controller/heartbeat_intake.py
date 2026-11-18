#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Heartbeat intake bridge for V91 (Issue #37, stage 3 evidence path).

This is the ONE place that translates a verified signed heartbeat
into cooperation-register evidence (NO_DUPLICATE_SYSTEMS):

  signed_heartbeat.SignedHeartbeatVerifier  (origin proof)
      -> HeartbeatIntake.receive()          (this module)
      -> cooperation_register.CooperationRegister  (evidence view)

Design rules honored explicitly:

- RECEIVER-ASSIGNED SEQUENCE: the register observation sequence is a
  local, monotonic, receiver-side counter. A sender-claimed sequence
  would be a claim, not evidence. Two different integrators feeding
  the same register through this bridge stay conflict-free.
- UNKNOWN != PASS: every rejected heartbeat with an identifiable peer
  is filed into the register as an INVALID observation, which counts
  as a failed attempt only; a rejected heartbeat NEVER upgrades a
  view. Envelopes too malformed to identify a peer are rejected
  before the register is touched (REJECTED_PRE_REGISTER).
- ISOLATE_NOT_DESTROY: a rejection (revoked peer, stale timestamp)
  leaves the last verified view untouched.
- Signed metadata: software_version/capabilities are taken ONLY from
  the signature-verified envelope metrics (keys "software_version",
  "capabilities", comma-separated). They are recorded as observed
  metadata, never as health or authorization.
- DETECTION != AUTHORIZATION: receiving verifies nothing about the
  remote node's health or honesty; a verified heartbeat only proves
  origin at this point in time.

Honest limits: the sequence counter is in-memory and per process
(a restart restarts it at 1; conflicts this could raise against a
long-lived register are filed as conflicts, never auto-resolved).
No network code, no daemon; callers deliver envelopes themselves.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from controller.cooperation_register import (
    CooperationRegister,
    Observation,
)
from controller.peer_directory import PeerDirectory
from controller.signed_heartbeat import (
    DEFAULT_MAX_FUTURE_SECONDS,
    DEFAULT_MAX_SEEN_NONCES,
    DEFAULT_TTL_SECONDS,
    HeartbeatVerification,
    ORIGIN_VERIFIED,
    SignedHeartbeatVerifier,
)

METRIC_SOFTWARE_VERSION = "software_version"
METRIC_CAPABILITIES = "capabilities"
FALLBACK_SOFTWARE_VERSION = "UNKNOWN"
STATUS_PRE_REGISTER = "REJECTED_PRE_REGISTER"


class HeartbeatIntakeError(Exception):
    """Raised for caller errors (bad parameters), never for rejects."""


@dataclass(frozen=True)
class IntakeOutcome:
    """What one received envelope led to (composite evidence)."""

    verification: HeartbeatVerification
    status: str
    view_updated: bool
    sequence: Optional[int] = None


class HeartbeatIntake:
    """Feed signed heartbeats into one cooperation register, fail-closed."""

    def __init__(
        self,
        *,
        peer_directory: PeerDirectory,
        register: CooperationRegister,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_future_seconds: float = DEFAULT_MAX_FUTURE_SECONDS,
        now_provider: Optional[Callable[[], float]] = None,
        max_seen_nonces: int = DEFAULT_MAX_SEEN_NONCES,
    ) -> None:
        for name, obj in (("peer_directory", peer_directory),
                          ("register", register)):
            if obj is None:
                raise HeartbeatIntakeError(f"{name} is required")
        self._verifier = SignedHeartbeatVerifier(
            peer_directory=peer_directory,
            ttl_seconds=ttl_seconds,
            max_future_seconds=max_future_seconds,
            now_provider=now_provider,
            max_seen_nonces=max_seen_nonces,
        )
        self._register = register
        self._now = now_provider or time.time
        self._sequences: dict[str, int] = {}

    def _next_sequence(self, peer_id: str) -> int:
        current = self._sequences.get(peer_id, 0) + 1
        self._sequences[peer_id] = current
        return current

    @staticmethod
    def _metadata_from(envelope: Mapping[str, Any]) -> tuple[str, tuple[str, ...]]:
        metrics = envelope.get("metrics")
        if not isinstance(metrics, Mapping):
            return FALLBACK_SOFTWARE_VERSION, ()
        software_version = metrics.get(METRIC_SOFTWARE_VERSION)
        if not isinstance(software_version, str) or not software_version:
            software_version = FALLBACK_SOFTWARE_VERSION
        capabilities: tuple[str, ...] = ()
        raw = metrics.get(METRIC_CAPABILITIES)
        if isinstance(raw, str) and raw.strip():
            capabilities = tuple(
                part.strip() for part in raw.split(",") if part.strip())
        return software_version, capabilities

    def receive(self, envelope: Any) -> IntakeOutcome:
        """Verify one envelope and file the result as register evidence.

        Never raises on a bad envelope; returns composite evidence.
        """
        verification = self._verifier.verify(envelope)
        if not isinstance(envelope, Mapping):
            return IntakeOutcome(verification, STATUS_PRE_REGISTER,
                                 view_updated=False)
        peer_id = envelope.get("peer_id")
        if not isinstance(peer_id, str) or not peer_id.strip():
            return IntakeOutcome(verification, STATUS_PRE_REGISTER,
                                 view_updated=False)
        key_id = envelope.get("key_id")
        if not isinstance(key_id, str) or not key_id.strip():
            return IntakeOutcome(verification, STATUS_PRE_REGISTER,
                                 view_updated=False)

        software_version, capabilities = self._metadata_from(envelope)
        sequence = self._next_sequence(peer_id)
        observation = Observation(
            peer_id=peer_id,
            key_id=key_id,
            sequence=sequence,
            received_at=float(self._now()),  # receiver-local read time
            software_version=software_version,
            capabilities=capabilities,
            state=verification.state,
            verification=verification.as_register_verification(),
        )
        outcome = self._register.record(observation)
        return IntakeOutcome(
            verification=verification,
            status=outcome.status,
            view_updated=outcome.view_updated,
            sequence=sequence,
        )
