"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Provider-neutral orchestration for an independent 2-of-3 review.

This module calls configured reviewer adapters; it does not implement an
HTTP/API provider, persist replay floors, store credentials, or execute
approved actions. The caller owns durable sequence-floor storage and must
apply its own authorization/capability checks after this module returns.
Provider calls are synchronous; adapters must enforce their own deadlines.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from controller.agent_consensus import (
    ConsensusResult,
    Decision,
    Vote,
    evaluate_consensus,
)


@dataclass(frozen=True)
class ReviewRequest:
    proposal: dict
    policy_version: str
    evidence: tuple[dict, ...]
    deadline: int
    epoch: int
    now: int


@dataclass(frozen=True)
class ReviewOutcome:
    proposal_digest: str
    decision: Decision
    votes_requested: tuple[str, ...]
    votes_received: int
    consensus: ConsensusResult
    execution_permitted: bool = False
    deadline_expired: bool = False


Reviewer = Callable[[str, int, str, tuple[dict, ...], int], Vote]


class QuorumOrchestrationError(ValueError):
    """Invalid orchestration configuration; fail closed."""


def proposal_digest(request: ReviewRequest) -> str:
    """Hash the immutable proposal, policy version and evidence bundle."""
    if not isinstance(request, ReviewRequest):
        raise QuorumOrchestrationError("request must be a ReviewRequest")
    if not isinstance(request.proposal, dict) or not request.proposal:
        raise QuorumOrchestrationError("proposal must be a non-empty object")
    if not isinstance(request.policy_version, str) or not request.policy_version.strip():
        raise QuorumOrchestrationError("policy_version must be non-empty")
    if not isinstance(request.evidence, tuple) or any(not isinstance(x, dict) for x in request.evidence):
        raise QuorumOrchestrationError("evidence must be a tuple of objects")
    if type(request.deadline) is not int or type(request.now) is not int:
        raise QuorumOrchestrationError("deadline and now must be integer timestamps")
    if request.now < 0 or request.deadline < 0 or request.deadline <= request.now:
        raise QuorumOrchestrationError("review deadline and creation time must be non-negative and deadline must be in the future")
    if type(request.epoch) is not int or request.epoch < 0:
        raise QuorumOrchestrationError("epoch must be a non-negative integer")
    payload = {
        "proposal": request.proposal,
        "policy_version": request.policy_version,
        "evidence": list(request.evidence),
        "deadline": request.deadline,
        "epoch": request.epoch,
    }
    try:
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise QuorumOrchestrationError("proposal bundle is not canonical JSON data") from exc
    return hashlib.sha256(canonical).hexdigest()


def review_with_quorum(
    request: ReviewRequest,
    *,
    reviewer_ids: Sequence[str],
    reviewers: Mapping[str, Reviewer],
    member_keys: Mapping[str, bytes],
    min_sequence_by_agent: Mapping[str, int],
    now_provider: Callable[[], int],
) -> ReviewOutcome:
    """
    Ask two independent reviewers first; ask the third unless they agree.

    A fresh, injected clock is mandatory. The request's creation-time clock
    is not reused as a deadline check. Each provider call is checked before
    and after it; responses arriving at/after the deadline are discarded.
    Provider adapters must still enforce their own timeout because calls are
    synchronous and this orchestrator cannot interrupt a blocked call.
    """
    ids = tuple(reviewer_ids)
    if len(ids) != 3 or len(set(ids)) != 3 or any(not isinstance(x, str) or not x.strip() for x in ids):
        raise QuorumOrchestrationError("exactly three distinct reviewer identities are required")
    if set(reviewers) != set(ids) or set(member_keys) != set(ids):
        raise QuorumOrchestrationError("reviewers and member_keys must match the three identities")
    if not callable(now_provider):
        raise QuorumOrchestrationError("a fresh now_provider is required")
    digest = proposal_digest(request)
    collected: list[Vote] = []
    asked: list[str] = []
    last_now = request.now
    deadline_expired = False

    def fresh_now() -> int:
        nonlocal last_now
        try:
            value = now_provider()
        except Exception as exc:
            raise QuorumOrchestrationError("fresh clock provider failed") from exc
        if type(value) is not int or value < 0:
            raise QuorumOrchestrationError("fresh clock must return a non-negative integer timestamp")
        if value < last_now:
            raise QuorumOrchestrationError("fresh clock moved backwards")
        last_now = value
        return value

    def evaluation_time() -> int:
        nonlocal deadline_expired
        value = fresh_now()
        if value >= request.deadline:
            deadline_expired = True
        # A vote received before the deadline remains evaluable after the
        # deadline; cap the consensus clock at the final in-window second.
        return min(value, request.deadline - 1)

    def ask(agent_id: str) -> None:
        nonlocal deadline_expired
        before = fresh_now()
        if before >= request.deadline:
            deadline_expired = True
            return
        asked.append(agent_id)
        try:
            vote = reviewers[agent_id](
                digest, request.epoch, request.policy_version,
                request.evidence, request.deadline,
            )
        except Exception:
            vote = None
        after = fresh_now()
        if after >= request.deadline:
            deadline_expired = True
            return
        if isinstance(vote, Vote):
            if type(vote.issued_at) is int and vote.issued_at >= request.deadline:
                return
            collected.append(vote)

    # First two independent reviewers.
    ask(ids[0])
    ask(ids[1])
    result = evaluate_consensus(
        collected, member_keys=member_keys, proposal_digest=digest,
        epoch=request.epoch, now=evaluation_time(),
        min_sequence_by_agent=min_sequence_by_agent, quorum=2,
    )

    # A third opinion is required for disagreement, absence, timeout,
    # malformed signatures, stale votes or any other NO_QUORUM outcome.
    # ask() checks the fresh deadline again and will not contact provider 3
    # once the review window has expired.
    if result.decision is Decision.NO_QUORUM:
        ask(ids[2])
        result = evaluate_consensus(
            collected, member_keys=member_keys, proposal_digest=digest,
            epoch=request.epoch, now=evaluation_time(),
            min_sequence_by_agent=min_sequence_by_agent, quorum=2,
        )

    return ReviewOutcome(
        proposal_digest=digest,
        decision=result.decision,
        votes_requested=tuple(asked),
        votes_received=len(collected),
        consensus=result,
        execution_permitted=False,
        deadline_expired=deadline_expired,
    )
