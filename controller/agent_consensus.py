"""Transport-neutral fail-closed vote validation. No network, ledger, or execution."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import json
import re
from typing import Mapping

_HEX = re.compile(r"^[0-9a-f]{64}$")


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    NO_QUORUM = "NO_QUORUM"


@dataclass(frozen=True)
class Vote:
    agent_id: str
    proposal_digest: str
    epoch: int
    sequence: int
    issued_at: int
    approve: bool
    signature: str


@dataclass(frozen=True)
class ConsensusResult:
    decision: Decision
    quorum_required: int
    valid_approvals: int
    valid_rejections: int
    accepted_agents: tuple[str, ...]
    rejected_agents: tuple[str, ...]
    invalid_votes: tuple[str, ...]


def _payload(vote: Vote) -> bytes:
    fields = {
        "agent_id": vote.agent_id, "proposal_digest": vote.proposal_digest,
        "epoch": vote.epoch, "sequence": vote.sequence,
        "issued_at": vote.issued_at, "approve": vote.approve,
    }
    return json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("ascii")


def sign_vote(*, agent_id: str, proposal_digest: str, epoch: int,
              sequence: int, issued_at: int, approve: bool,
              agent_key: bytes) -> Vote:
    """Sign one vote with that agent's independent secret (>=32 bytes)."""
    if len(agent_key) < 32:
        raise ValueError("agent_key must contain at least 32 bytes")
    if not agent_id or not agent_id.strip() or not _HEX.fullmatch(proposal_digest):
        raise ValueError("invalid agent_id or proposal_digest")
    if any(type(v) is not int or v < 0 for v in (epoch, sequence, issued_at)):
        raise ValueError("epoch, sequence and issued_at must be non-negative integers")
    if type(approve) is not bool:
        raise ValueError("approve must be boolean")
    unsigned = Vote(agent_id, proposal_digest, epoch, sequence, issued_at, approve, "")
    signature = hmac.new(agent_key, _payload(unsigned), hashlib.sha256).hexdigest()
    return Vote(agent_id, proposal_digest, epoch, sequence, issued_at, approve, signature)


def evaluate_consensus(votes: list[Vote] | tuple[Vote, ...], *,
                       member_keys: Mapping[str, bytes], proposal_digest: str,
                       epoch: int, now: int,
                       min_sequence_by_agent: Mapping[str, int],
                       quorum: int | None = None,
                       allowed_clock_skew_seconds: int = 60) -> ConsensusResult:
    """Validate unique votes. Replay floors must come from durable trusted state."""
    members = dict(member_keys)
    if not members or any(not name.strip() or len(key) < 32 for name, key in members.items()):
        raise ValueError("each configured member needs a name and key of >=32 bytes")
    if not _HEX.fullmatch(proposal_digest):
        raise ValueError("proposal_digest must be a lowercase SHA-256 hex digest")
    if type(epoch) is not int or type(now) is not int or min(epoch, now) < 0:
        raise ValueError("epoch and now must be non-negative integers")
    if type(allowed_clock_skew_seconds) is not int or allowed_clock_skew_seconds < 0:
        raise ValueError("clock skew must be a non-negative integer")
    required = quorum if quorum is not None else len(members) // 2 + 1
    if type(required) is not int or not 1 <= required <= len(members):
        raise ValueError("quorum must be between 1 and the member count")

    seen: set[str] = set()
    yes: list[str] = []
    no: list[str] = []
    invalid: list[str] = []
    for vote in votes:
        agent = vote.agent_id
        if agent in seen:
            invalid.append(f"{agent}: duplicate vote")
            continue
        seen.add(agent)
        key = members.get(agent)
        if key is None:
            invalid.append(f"{agent}: unknown member")
            continue
        if vote.proposal_digest != proposal_digest or vote.epoch != epoch:
            invalid.append(f"{agent}: proposal or epoch mismatch")
            continue
        floor = min_sequence_by_agent.get(agent)
        if type(vote.sequence) is not int or floor is None or vote.sequence <= floor:
            invalid.append(f"{agent}: stale or untracked sequence")
            continue
        if type(vote.issued_at) is not int or abs(now - vote.issued_at) > allowed_clock_skew_seconds:
            invalid.append(f"{agent}: timestamp outside allowed window")
            continue
        if type(vote.approve) is not bool or not _HEX.fullmatch(vote.signature):
            invalid.append(f"{agent}: malformed vote or signature")
            continue
        expected = hmac.new(key, _payload(vote), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, vote.signature):
            invalid.append(f"{agent}: signature verification failed")
            continue
        (yes if vote.approve else no).append(agent)

    decision = (Decision.ACCEPT if len(yes) >= required else
                Decision.REJECT if len(no) >= required else Decision.NO_QUORUM)
    return ConsensusResult(decision, required, len(yes), len(no),
                           tuple(sorted(yes)), tuple(sorted(no)), tuple(invalid))
