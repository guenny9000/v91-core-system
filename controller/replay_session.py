"""Two-node independent replay verification (Issue #47, stage 4 groundwork).

A reference run and a replay run must come from two DIFFERENT runner
instances. The comparison itself is delegated to the pure function
verify_exact_replay - it is not performed by either runner, so no runner
verifies itself (consistent with controller/model_runner.py).

Honest limits, by design:
- Code cannot prove that two instances ran on physically separate nodes.
  The result therefore never claims node independence; it discloses
  'NODE_INDEPENDENCE_NOT_PROVABLE_BY_CODE' and whether the two runners
  share the same injected inference callable.
- VERIFIED_EXACT means byte-identical outputs under recorded conditions -
  nothing more, nothing about truth, safety, or production readiness.
"""
from __future__ import annotations

from typing import Any

from controller.model_run_manifest import verify_exact_replay
from controller.model_runner import PinnedModelRunner


class ReplaySessionError(ValueError):
    """Raised when the two-node replay contract is violated."""


INDEPENDENCE_CLAIM = "NODE_INDEPENDENCE_NOT_PROVABLE_BY_CODE"

COMBINED_BYTE_MATCH = "VERIFIED_EXACT_BYTE_MATCH_INDEPENDENCE_UNPROVEN"


class TwoNodeReplay:
    """Executes one reference run and one replay run on two distinct runner instances."""

    def __init__(self, *, reference_runner: PinnedModelRunner, replay_runner: PinnedModelRunner) -> None:
        if not isinstance(reference_runner, PinnedModelRunner) or not isinstance(replay_runner, PinnedModelRunner):
            raise ReplaySessionError("both nodes must be PinnedModelRunner instances")
        if reference_runner is replay_runner:
            raise ReplaySessionError(
                "reference and replay must be two different runner instances; a runner cannot replay itself"
            )
        self._reference = reference_runner
        self._replay = replay_runner

    def execute(self, input_bytes: bytes) -> dict[str, Any]:
        """Run reference and replay once, then compare via the independent pure verifier."""
        if not isinstance(input_bytes, bytes):
            raise ReplaySessionError("input must be bytes")
        reference_manifest = self._reference.run(input_bytes)
        replay_manifest = self._replay.run(input_bytes)
        verdict = verify_exact_replay(reference_manifest, replay_manifest)
        status = verdict["status"]
        return {
            "status": status,
            "reason": verdict.get("reason", ""),
            "combined_status": COMBINED_BYTE_MATCH if status == "VERIFIED_EXACT" else status,
            "reference": reference_manifest,
            "replay": replay_manifest,
            "shared_inference_callable": self._reference.shares_inference_with(self._replay),
            "node_independence": INDEPENDENCE_CLAIM,
        }
