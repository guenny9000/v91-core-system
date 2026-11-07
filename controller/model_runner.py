"""Pinned deterministic model runner producing replay-comparable run records.

This module still does not ship a model. It wraps an injected inference
callable with the pinning contract from Issue #47 stage 2: digests for the
model, tokenizer and runtime are required up front, inputs and outputs are
bytes, and every finished run is recorded as COMPLETED_UNVERIFIED. The runner
also refuses to verify two records that both originated from itself, because
a runner cannot verify itself - independent replay must come from elsewhere.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from controller.model_run_manifest import build_run_manifest, verify_exact_replay


class ModelRunnerError(ValueError):
    """Raised when the pinned runner contract is violated."""


def _require_digest(name: str, value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ModelRunnerError(f"{name} must be a 64-character lowercase SHA-256 hex digest")
    return value


class PinnedModelRunner:
    """Wraps an injected inference callable with a strict pinning contract."""

    def __init__(
        self,
        *,
        inference: Callable[[bytes], bytes],
        model_digest: str,
        tokenizer_digest: str,
        runtime_digest: str,
        seed: int,
        parameters: Mapping[str, Any],
        precision: str,
        backend: str,
        allow_nondeterministic: bool = False,
    ) -> None:
        if not callable(inference):
            raise ModelRunnerError("inference must be a callable accepting bytes and returning bytes")
        _require_digest("model_digest", model_digest)
        _require_digest("tokenizer_digest", tokenizer_digest)
        _require_digest("runtime_digest", runtime_digest)
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ModelRunnerError("seed must be a non-negative integer")
        if not isinstance(parameters, Mapping):
            raise ModelRunnerError("parameters must be a mapping")
        if not isinstance(precision, str) or not precision.strip():
            raise ModelRunnerError("precision is required")
        if not isinstance(backend, str) or not backend.strip():
            raise ModelRunnerError("backend is required")
        params = dict(parameters)
        if not allow_nondeterministic:
            temperature = params.get("temperature")
            if isinstance(temperature, bool) or (isinstance(temperature, (int, float)) and temperature != 0):
                raise ModelRunnerError(
                    "temperature != 0 makes exact replay unlikely; pass allow_nondeterministic=True to record such runs honestly"
                )
            if params.get("do_sample") is True:
                raise ModelRunnerError(
                    "do_sample=True makes exact replay unlikely; pass allow_nondeterministic=True to record such runs honestly"
                )
        self._inference = inference
        self._model_digest = model_digest
        self._tokenizer_digest = tokenizer_digest
        self._runtime_digest = runtime_digest
        self._seed = seed
        self._parameters = params
        self._precision = precision
        self._backend = backend
        self._emitted: set[tuple[str, str]] = set()

    def run(self, input_bytes: bytes) -> dict[str, Any]:
        """Execute the pinned inference once and return a COMPLETED_UNVERIFIED run record."""
        if not isinstance(input_bytes, bytes):
            raise ModelRunnerError("input must be bytes")
        output = self._inference(input_bytes)
        if not isinstance(output, bytes):
            raise ModelRunnerError("inference output must be bytes")
        manifest = build_run_manifest(
            model_digest=self._model_digest,
            tokenizer_digest=self._tokenizer_digest,
            runtime_digest=self._runtime_digest,
            input_bytes=input_bytes,
            output_bytes=output,
            seed=self._seed,
            parameters=self._parameters,
            precision=self._precision,
            backend=self._backend,
        )
        self._emitted.add((manifest["input_digest"], manifest["output_digest"]))
        return manifest

    def produced_here(self, manifest: Mapping[str, Any]) -> bool:
        """Return True if this exact (input, output) pair was produced by this runner instance."""
        try:
            key = (manifest["input_digest"], manifest["output_digest"])
        except (KeyError, TypeError) as exc:
            raise ModelRunnerError("not a run manifest") from exc
        return key in self._emitted

    def shares_inference_with(self, other: "PinnedModelRunner") -> bool:
        """True if both runners wrap the exact same injected inference callable.

        Honest disclosure for replay sessions: sharing the callable means both
        'nodes' compute identically by construction - it says nothing about
        physical node separation.
        """
        return isinstance(other, PinnedModelRunner) and self._inference is other._inference

    def verify_independent_replay(self, reference: Mapping[str, Any], replay: Mapping[str, Any]) -> dict[str, str]:
        """Compare two run records, refusing comparisons where both sides came from this runner."""
        if self.produced_here(reference) and self.produced_here(replay):
            return {
                "status": "SELF_VERIFICATION_REFUSED",
                "reason": "both records were produced by this runner; a runner cannot verify itself - an independent node must produce the replay",
            }
        return verify_exact_replay(reference, replay)
