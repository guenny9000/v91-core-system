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
    if request.deadline <= request.now:
        raise QuorumOrchestrationError("review deadline must be in the future")
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
) -> ReviewOutcome:
    """
    Ask two independent reviewers first; ask the third unless they agree.

    Reviewer adapters must be independently configured and must return a
    signed Vote for the exact digest/epoch. Exceptions and malformed replies
    are recorded as absent/invalid votes; they never count as approval.
    No command or external side effect is performed here.
    """
    ids = tuple(reviewer_ids)
    if len(ids) != 3 or len(set(ids)) != 3 or any(not isinstance(x, str) or not x.strip() for x in ids):
        raise QuorumOrchestrationError("exactly three distinct reviewer identities are required")
    if set(reviewers) != set(ids) or set(member_keys) != set(ids):
        raise QuorumOrchestrationError("reviewers and member_keys must match the three identities")
    digest = proposal_digest(request)
    collected: list[Vote] = []
    asked: list[str] = []

    def ask(agent_id: str) -> None:
        asked.append(agent_id)
        try:
            vote = reviewers[agent_id](
                digest, request.epoch, request.policy_version,
                request.evidence, request.deadline,
            )
        except Exception:
            return
        if isinstance(vote, Vote):
            collected.append(vote)

    # First two independent reviewers.
    ask(ids[0])
    ask(ids[1])
    result = evaluate_consensus(
        collected, member_keys=member_keys, proposal_digest=digest,
        epoch=request.epoch, now=request.now,
        min_sequence_by_agent=min_sequence_by_agent, quorum=2,
    )

    # A third opinion is required for disagreement, absence, timeout,
    # malformed signatures, stale votes or any other NO_QUORUM outcome.
    if result.decision is Decision.NO_QUORUM:
        ask(ids[2])
        result = evaluate_consensus(
            collected, member_keys=member_keys, proposal_digest=digest,
            epoch=request.epoch, now=request.now,
            min_sequence_by_agent=min_sequence_by_agent, quorum=2,
        )

    return ReviewOutcome(
        proposal_digest=digest,
        decision=result.decision,
        votes_requested=tuple(asked),
        votes_received=len(collected),
        consensus=result,
        execution_permitted=False,
    )
