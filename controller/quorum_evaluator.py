"""V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Independence-aware API quorum evaluation layer (Issue #167, slice 1).

Transport-neutral, fail-closed, no network, no persistence, no
execution bridge. This module sits ON TOP of agent_consensus (REUSE,
NO_DUPLICATE_SYSTEMS): signature, epoch, replay-floor and timestamp
validation stay in agent_consensus.evaluate_consensus; this layer
adds the independence dimension required by issue #167 and the
evidence duty for each stance (CLAIM != EVIDENCE).

Independence rule: two votes from the SAME provider AND model are one
independent source, never two. Valid votes from one source collapse;
conflicting stances within one source void that source's
contribution entirely.

Honest limits:
- INDEPENDENCE != PROVEN: provider/model labels are disclosed claims.
  Code cannot prove two agents run on physically distinct systems.
- agent_consensus signs the approve bit; the stance label and
  provider/model identity are unsigned disclosures on top. A signed
  approve=True can never be turned into ABSTAIN here (mismatch
  invalidates the review), and ABSTAIN always counts as NO
  contribution, never as approval or rejection.
- Evaluations authorise nothing: APPROVED_FOR_DOCUMENTATION is a
  documentation verdict, not an execution permit (DETECTION !=
  AUTHORIZATION). UNKNOWN never passes (UNKNOWN != PASS).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from controller import agent_consensus

ALLOWED_STANCES = ("APPROVE", "REJECT", "ABSTAIN")


class QuorumEvaluatorError(RuntimeError):
    """Fail-closed configuration or envelope error; never swallowed."""


class ReviewDecision(str, Enum):
    APPROVED_FOR_DOCUMENTATION = "APPROVED_FOR_DOCUMENTATION"
    REJECTED = "REJECTED"
    THIRD_REVIEW_REQUIRED = "THIRD_REVIEW_REQUIRED"
    NO_QUORUM = "NO_QUORUM"


@dataclass(frozen=True)
class ReviewVote:
    vote: agent_consensus.Vote
    provider: str
    model: str
    stance: str
    rationale: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class IndependentQuorumResult:
    decision: ReviewDecision
    independent_sources_required: int
    approved_sources: tuple[str, ...]
    rejected_sources: tuple[str, ...]
    abstained_sources: tuple[str, ...]
    voided_sources: tuple[str, ...]
    invalid_reasons: tuple[str, ...]
    independence_note: str

    def as_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "independent_sources_required": self.independent_sources_required,
            "approved_sources": list(self.approved_sources),
            "rejected_sources": list(self.rejected_sources),
            "abstained_sources": list(self.abstained_sources),
            "voided_sources": list(self.voided_sources),
            "invalid_reasons": list(self.invalid_reasons),
            "independence_note": self.independence_note,
            "authorization": "NONE (EVALUATION != AUTHORIZATION)",
        }


def _source_key(provider: str, model: str) -> str:
    return provider.strip().lower() + "|" + model.strip().lower()


def evaluate_independent_quorum(
        reviews: Sequence[ReviewVote], *,
        member_keys: Mapping[str, bytes],
        proposal_digest: str, epoch: int, now: int,
        min_sequence_by_agent: Mapping[str, int],
        independent_sources_required: int = 2,
        allowed_clock_skew_seconds: int = 60,
        quorum_evaluator=None) -> IndependentQuorumResult:
    """Evaluate independent agreement among structured API reviews.

    Signature/replay/timestamp validation is delegated entirely to
    agent_consensus.evaluate_consensus (quorum=1 is used ONLY to obtain
    per-agent validity; the resulting headline decision there is
    ignored). Everything else fails closed here.
    """
    if not isinstance(reviews, (list, tuple)) or not reviews:
        raise QuorumEvaluatorError("reviews must be a non-empty list or tuple")
    if type(independent_sources_required) is not int or independent_sources_required < 2:
        raise QuorumEvaluatorError("independent_sources_required must be an int >= 2")
    evaluate = quorum_evaluator or agent_consensus.evaluate_consensus
    invalid: list[str] = []
    envelope_ok: dict[str, ReviewVote] = {}
    for review in reviews:
        if not isinstance(review, ReviewVote):
            invalid.append("malformed review envelope")
            continue
        vote = review.vote
        if (not isinstance(review.provider, str) or not review.provider.strip()
                or not isinstance(review.model, str) or not review.model.strip()):
            invalid.append("%s: provider/model missing" % vote.agent_id)
            continue
        if review.stance not in ALLOWED_STANCES:
            invalid.append("%s: stance not in %s" % (vote.agent_id, ALLOWED_STANCES))
            continue
        if not isinstance(review.rationale, str) or not review.rationale.strip():
            invalid.append("%s: rationale missing (CLAIM != EVIDENCE)" % vote.agent_id)
            continue
        if review.stance in ("APPROVE", "REJECT"):
            expected_approve = review.stance == "APPROVE"
            if vote.approve is not expected_approve:
                invalid.append("%s: stance/approve mismatch" % vote.agent_id)
                continue
            if (not isinstance(review.evidence, tuple)
                    or any(not isinstance(e, str) or not e.strip() for e in review.evidence)):
                invalid.append("%s: evidence missing (CLAIM != EVIDENCE)" % vote.agent_id)
                continue
        else:  # ABSTAIN: never a signed approve=True
            if vote.approve is not False:
                invalid.append("%s: ABSTAIN must carry approve=False" % vote.agent_id)
                continue
        envelope_ok[vote.agent_id] = review

    base = evaluate(
        [r.vote for r in reviews],
        member_keys=member_keys, proposal_digest=proposal_digest,
        epoch=epoch, now=now, min_sequence_by_agent=min_sequence_by_agent,
        quorum=1, allowed_clock_skew_seconds=allowed_clock_skew_seconds)
    invalid.extend("crypto layer: " + reason for reason in base.invalid_votes)

    valid_agents = set(base.accepted_agents) | set(base.rejected_agents)
    per_source: dict[str, list[ReviewVote]] = {}
    for review in reviews:
        if isinstance(review, ReviewVote) and review.vote.agent_id in valid_agents \
                and review.vote.agent_id in envelope_ok:
            per_source.setdefault(_source_key(review.provider, review.model), []).append(review)

    approved: list[str] = []
    rejected: list[str] = []
    abstained: list[str] = []
    voided: list[str] = []
    for source_key, source_reviews in sorted(per_source.items()):
        stances = {r.stance for r in source_reviews}
        if len(source_reviews) > 1 and len(stances) > 1:
            voided.append(source_key)
            continue
        review = source_reviews[0]
        label = "%s|%s" % (source_key, review.vote.agent_id)
        if review.stance == "APPROVE":
            approved.append(label)
        elif review.stance == "REJECT":
            rejected.append(label)
        else:
            abstained.append(label)

    required = independent_sources_required
    if len(approved) >= required:
        decision = ReviewDecision.APPROVED_FOR_DOCUMENTATION
    elif len(rejected) >= required:
        decision = ReviewDecision.REJECTED
    elif approved and rejected:
        decision = ReviewDecision.THIRD_REVIEW_REQUIRED
    else:
        decision = ReviewDecision.NO_QUORUM

    note = ("INDEPENDENCE != PROVEN: provider/model are disclosed claims; "
            "same provider+model collapses to one source. Evaluation "
            "authorises nothing (DETECTION != AUTHORIZATION).")
    return IndependentQuorumResult(
        decision, required, tuple(approved), tuple(rejected),
        tuple(abstained), tuple(voided), tuple(invalid), note)
