"""Deterministic availability/safety gate for external server models.

Policy (V91 charter):
- Performance metrics UNKNOWN is not FAIL: a model may work without
  publishable speed/energy/load numbers, and the result says so honestly.
- Safety status UNKNOWN is not PASS: an unverified safety check blocks
  the gate. Fail-closed applies to safety, honesty applies to metrics.

Evaluation is pure: it returns a result object and never mutates the input.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

SAFETY_STATUSES = {"VERIFIED", "FAILED", "UNKNOWN"}


class ModelGateError(ValueError):
    """Raised when a model description cannot be evaluated safely."""


@dataclass(frozen=True)
class ModelGateResult:
    decision: str
    reason: str
    safety_status: str
    metrics_status: str  # "PRESENT" | "UNKNOWN"
    performance_status: str  # "VERIFIED" | "UNVERIFIED"


def _is_true(value: Any) -> bool:
    # Strict: only boolean True counts. Strings like "yes" do not.
    return value is True


def evaluate_server_model(model: Mapping[str, Any]) -> ModelGateResult:
    """Evaluate one model description as untrusted input; never mutate it."""
    if not isinstance(model, Mapping):
        raise ModelGateError("model must be a mapping")

    if not _is_true(model.get("available")):
        return ModelGateResult(
            "BLOCKED_UNAVAILABLE", "model not available",
            "UNKNOWN", "UNKNOWN", "UNVERIFIED",
        )

    if not _is_true(model.get("authorization_valid")):
        return ModelGateResult(
            "BLOCKED_UNAUTHORIZED", "authorization missing or invalid",
            "UNKNOWN", "UNKNOWN", "UNVERIFIED",
        )

    safety = model.get("safety_check")
    if safety not in SAFETY_STATUSES:
        raise ModelGateError(
            f"safety_check must be one of {sorted(SAFETY_STATUSES)}, got {safety!r}"
        )

    if safety == "FAILED":
        return ModelGateResult(
            "BLOCKED_SAFETY_FAILED", "safety check failed",
            "FAILED", "UNKNOWN", "UNVERIFIED",
        )

    if safety == "UNKNOWN":
        # Fail-closed on safety: unverified safety is not a pass.
        return ModelGateResult(
            "BLOCKED_SAFETY_UNKNOWN", "safety check has not been performed",
            "UNKNOWN", "UNKNOWN", "UNVERIFIED",
        )

    metrics = model.get("metrics")
    if metrics is None:
        # Honest allow: performance UNKNOWN is not FAIL.
        return ModelGateResult(
            "ALLOW_WITHOUT_METRICS", "safety verified, metrics not provided",
            "VERIFIED", "UNKNOWN", "UNVERIFIED",
        )
    if not isinstance(metrics, Mapping):
        raise ModelGateError("metrics must be a mapping or None")

    return ModelGateResult(
        "ALLOW_WITH_METRICS", "safety verified, metrics provided",
        "VERIFIED", "PRESENT", "VERIFIED",
    )
