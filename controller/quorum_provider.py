"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Provider adapter contract for Issue #167 (API-backed review quorum).

This module defines the opt-in adapter layer between external API
reviewers and the existing signed-vote consensus core
(controller/agent_consensus.py, controller/agent_quorum.py). It:

1. requires providers to be explicitly enabled and independently
   provisioned (same provider+model twice is never "independent"),
2. only accepts credentials from approved environment variables
   (>=32 bytes); never from repository files, arguments or logs,
3. validates every provider response against the immutable proposal
   digest, epoch, per-agent replay floor, deadline and clock window,
4. converts APPROVE/REJECT into signed votes and records
   ABSTAIN/UNKNOWN as valid-but-absent opinions (never approval),
5. enforces a per-session token budget across all provider calls
   (exceeding it stops further requests, fail closed),
6. screens free-text provider output for embedded-instruction
   patterns ("prompt injection"); any suspect output is discarded,
   a suspect APPROVE can never become a valid approval.

Honest limits, by construction:
- ADAPTER != PROVIDER: no HTTP client, no model call, no network I/O;
  the caller supplies the transport. SCRIPTED != INSTALLED.
- BUDGET_MODEL != COST: token counts are provider-reported claims.
- The injection screen is a heuristic tripwire, NOT a guarantee;
  a signed vote is authentic, not necessarily correct.
- Votes decide nothing: decision != execution; no side effects here.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Mapping

if __package__ in (None, ""):  # direct script execution: python3 controller/quorum_provider.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from controller.agent_consensus import sign_vote, Vote

VOTE_CHOICES = frozenset({"APPROVE", "REJECT", "ABSTAIN", "UNKNOWN"})
DECIDING_CHOICES = frozenset({"APPROVE", "REJECT"})
MIN_KEY_BYTES = 32

# Heuristic tripwire, not a guarantee: provider free text that embeds
# instruction-like patterns is discarded, never trusted, never executed.
INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?)", re.IGNORECASE),
    re.compile(r"disregard\s+(?:your\s+)?(?:system|safety)\s+(?:prompt|instructions?)", re.IGNORECASE),
    re.compile(r"you\s+(?:are\s+now|must\s+now)\s+(?:an?\s+)?(?:unrestricted|different|new)\s+(?:agent|persona|mode)", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:", re.IGNORECASE),
    re.compile(r"<\|.*\|>", re.DOTALL),
    re.compile(r"```(?:tool|system)", re.IGNORECASE),
)


class QuorumProviderError(ValueError):
    """Invalid provider configuration or response; fail closed."""


@dataclass(frozen=True)
class ProviderConfig:
    """Opt-in description of ONE independently provisioned API reviewer."""
    agent_id: str
    provider: str
    model: str
    key_env_var: str
    token_budget: int
    enabled: bool = False

    def __post_init__(self) -> None:
        for field in ("agent_id", "provider", "model", "key_env_var"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise QuorumProviderError(f"ProviderConfig.{field} must be non-empty")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", self.key_env_var):
            raise QuorumProviderError(
                "key_env_var must be an environment VARIABLE NAME (A-Z, 0-9, _), "
                "never key material")
        if type(self.token_budget) is not int or self.token_budget < 0:
            raise QuorumProviderError("token_budget must be a non-negative integer")
        if not isinstance(self.enabled, bool):
            raise QuorumProviderError("enabled must be boolean (opt-in)")


def prepare_reviewers(configs: list[ProviderConfig]) -> tuple[ProviderConfig, ...]:
    """Validate the reviewer set: opt-in, distinct, independently provisioned.

    Two reviewers on the same provider+model are NOT independent; two reviewer
    identities sharing one environment key variable are NOT independently
    provisioned. Both are refused (Issue #167 rules 1-2).
    """
    if not isinstance(configs, list) or not configs:
        raise QuorumProviderError("configs must be a non-empty list of ProviderConfig")
    enabled = [c for c in configs if isinstance(c, ProviderConfig) and c.enabled]
    if len(enabled) != 3:
        raise QuorumProviderError(
            "exactly three API reviewers must be explicitly enabled (opt-in)")
    if len({c.agent_id for c in enabled}) != 3:
        raise QuorumProviderError("reviewer agent_ids must be distinct")
    pairs = [(c.provider, c.model) for c in enabled]
    if len(set(pairs)) != 3:
        raise QuorumProviderError(
            "same provider+model twice is not an independent reviewer")
    if len({c.key_env_var for c in enabled}) != 3:
        raise QuorumProviderError(
            "independent provisioning required: each reviewer needs its own key variable")
    return tuple(enabled)


def resolve_provider_key(config: ProviderConfig) -> bytes:
    """Fetch the reviewer's independent key from the approved environment only."""
    raw = os.environ.get(config.key_env_var, "")
    if not raw or len(raw.encode("utf-8")) < MIN_KEY_BYTES:
        raise QuorumProviderError(
            f"{config.key_env_var} missing or shorter than {MIN_KEY_BYTES} bytes "
            f"for {config.agent_id} (fail closed; keys never come from repo or args)")
    return raw.encode("utf-8")


def _screen_for_injection(text: str, where: str) -> None:
    if not isinstance(text, str):
        raise QuorumProviderError(f"{where} must be a string")
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            raise QuorumProviderError(
                f"prompt-injection tripwire hit in {where}: provider output "
                "discarded (heuristic screen, not a guarantee)")


def review_provider_response(
    config: ProviderConfig,
    payload: Mapping[str, Any],
    *,
    proposal_digest: str,
    epoch: int,
    deadline: int,
    now: int,
    min_sequence: int,
    agent_key: bytes,
) -> dict[str, Any]:
    """Validate one raw provider response and render it into a signed vote.

    Returns a machine-readable report. APPROVE/REJECT become a signed Vote;
    ABSTAIN/UNKNOWN stay an honest absent opinion (rendered_vote is None);
    anything invalid raises QuorumProviderError (fail closed).
    Only a signed APPROVE can later count toward a quorum; the report reminds:
    SIGNATURE_AUTHENTIC != STATEMENT_CORRECT.
    """
    if not isinstance(config, ProviderConfig):
        raise QuorumProviderError("config must be a ProviderConfig")
    if not isinstance(payload, Mapping):
        raise QuorumProviderError("provider payload must be an object")
    if type(epoch) is not int or type(now) is not int or type(deadline) is not int:
        raise QuorumProviderError("epoch, deadline and now must be integer timestamps")
    if deadline <= now or min(epoch, now, min_sequence) < 0:
        raise QuorumProviderError("deadline must be in the future; times and floor non-negative")
    if not isinstance(agent_key, bytes) or len(agent_key) < MIN_KEY_BYTES:
        raise QuorumProviderError("agent_key must contain at least 32 bytes")

    identity_provider = payload.get("provider")
    identity_model = payload.get("model")
    if identity_provider != config.provider or identity_model != config.model:
        raise QuorumProviderError(
            f"{config.agent_id}: payload identity {identity_provider}/{identity_model} "
            f"does not match configured {config.provider}/{config.model}")

    vote_choice = payload.get("vote")
    if vote_choice not in VOTE_CHOICES:
        raise QuorumProviderError(
            f"{config.agent_id}: vote must be one of {sorted(VOTE_CHOICES)}")

    rationale = payload.get("rationale")
    _screen_for_injection(rationale, f"{config.agent_id}.rationale")
    if not rationale.strip():
        raise QuorumProviderError(f"{config.agent_id}: rationale must be non-empty")

    evidence_refs = payload.get("evidence_refs", [])
    if (not isinstance(evidence_refs, list)
            or any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs)):
        raise QuorumProviderError(f"{config.agent_id}: evidence_refs must be a list of strings")
    for ref in evidence_refs:
        _screen_for_injection(ref, f"{config.agent_id}.evidence_refs")

    digest = payload.get("proposal_digest")
    if not isinstance(digest, str) or digest != proposal_digest:
        raise QuorumProviderError(f"{config.agent_id}: proposal digest mismatch (stale bundle)")

    response_epoch = payload.get("epoch")
    if type(response_epoch) is not int or response_epoch != epoch:
        raise QuorumProviderError(f"{config.agent_id}: epoch mismatch (stale policy/proposal)")

    sequence = payload.get("sequence")
    if type(sequence) is not int or sequence <= min_sequence:
        raise QuorumProviderError(f"{config.agent_id}: replay floor not exceeded")

    issued_at = payload.get("issued_at")
    if type(issued_at) is not int or issued_at > deadline or abs(now - issued_at) > 60:
        raise QuorumProviderError(f"{config.agent_id}: issued_at outside deadline/clock window")

    token_usage = payload.get("token_usage")
    if type(token_usage) is not int or token_usage < 0:
        raise QuorumProviderError(f"{config.agent_id}: token_usage must be non-negative (claim)")

    rendered: Vote | None = None
    if vote_choice in DECIDING_CHOICES:
        rendered = sign_vote(
            agent_id=config.agent_id,
            proposal_digest=proposal_digest,
            epoch=epoch,
            sequence=sequence,
            issued_at=issued_at,
            approve=vote_choice == "APPROVE",
            agent_key=agent_key,
        )

    return {
        "agent_id": config.agent_id,
        "provider": config.provider,
        "model": config.model,
        "vote": vote_choice,
        "rendered_vote": rendered,
        "token_usage_claim": token_usage,
        "evidence_ref_count": len(evidence_refs),
        "honest_limits": [
            "SIGNATURE_AUTHENTIC != STATEMENT_CORRECT.",
            "BUDGET_MODEL != COST; token_usage is a provider-reported claim.",
            "Injection screen is a heuristic tripwire, not a guarantee.",
        ],
    }


def enforce_token_budget(
    configs: Mapping[str, ProviderConfig],
    used_by_agent: Mapping[str, int],
) -> None:
    """Fail closed when a reviewer exceeds its configured token budget."""
    for agent_id, config in configs.items():
        used = used_by_agent.get(agent_id, 0)
        if type(used) is not int or used < 0:
            raise QuorumProviderError(f"{agent_id}: token usage must be a non-negative int")
        if used > config.token_budget:
            raise QuorumProviderError(
                f"{agent_id}: token budget exceeded ({used} > {config.token_budget}); "
                "stopping further provider requests (fail closed)")


def _cli() -> int:
    """Offline validator; invoke as: python3 -m controller.quorum_provider ..."""
    parser = argparse.ArgumentParser(
        description="Validate one raw provider response offline (no network).")
    parser.add_argument("--payload", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--deadline", type=int, required=True)
    parser.add_argument("--now", type=int, required=True)
    parser.add_argument("--min-sequence", type=int, required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--key-env", required=True)
    parser.add_argument("--token-budget", type=int, default=0)
    args = parser.parse_args()
    try:
        with open(args.payload, "r", encoding="utf-8") as stream:
            payload = json.load(stream)
        config = ProviderConfig(
            agent_id=args.agent_id, provider=args.provider, model=args.model,
            key_env_var=args.key_env, token_budget=args.token_budget, enabled=True,
        )
        key = resolve_provider_key(config)
        report = review_provider_response(
            config, payload, proposal_digest=args.digest, epoch=args.epoch,
            deadline=args.deadline, now=args.now, min_sequence=args.min_sequence,
            agent_key=key,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=True))
        return 2
    report["rendered_vote"] = (
        {"agent_id": report["rendered_vote"].agent_id,
         "approve": report["rendered_vote"].approve,
         "signature": report["rendered_vote"].signature}
        if report["rendered_vote"] is not None else None
    )
    report["status"] = "VALID"
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
