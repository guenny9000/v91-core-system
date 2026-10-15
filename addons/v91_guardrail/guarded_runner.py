"""Fail-closed gateway for explicitly registered local read-only tools.

Only tools explicitly registered by the host are callable. This gateway rejects
unknown tools, tools not declared read-only, network-capable/destructive tools,
and any proposal whose policy decision is not ALLOW_LOCAL_REVIEW. It is not an
OS sandbox; the host must register only trusted local callables.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .core import evaluate


@dataclass(frozen=True)
class ToolSpec:
    function: Callable[..., Any]
    read_only: bool = True
    network_access: bool = False
    destructive: bool = False


@dataclass(frozen=True)
class ToolResult:
    status: str
    result: Any = None
    audit: Mapping[str, Any] | None = None


class GuardedToolRunner:
    """Run allowlisted local read-only tools after policy evaluation.

    The registry is supplied by trusted host code. Do not register arbitrary
    model-generated functions or tools that can access the network or mutate
    state. Arguments and returned values are intentionally omitted from audit.
    """

    def __init__(self, tools: Mapping[str, ToolSpec]):
        if not isinstance(tools, Mapping):
            raise TypeError("tools muss eine explizite Zuordnung sein")
        self._tools = dict(tools)
        self.audit_log: list[dict[str, Any]] = []

    def run(self, tool_name: str, proposal: str, *args: Any, **kwargs: Any) -> ToolResult:
        base = {"tool_name": str(tool_name), "proposal_checked": isinstance(proposal, str)}
        spec = self._tools.get(tool_name)
        if spec is None:
            return self._record(ToolResult("BLOCK_UNKNOWN_TOOL", audit={
                **base, "decision": "BLOCK", "reason": "TOOL_NOT_ALLOWLISTED",
                "execution_attempted": False,
            }))
        if not spec.read_only or spec.network_access or spec.destructive:
            return self._record(ToolResult("BLOCK_UNSAFE_TOOL_SPEC", audit={
                **base, "decision": "BLOCK", "reason": "TOOL_NOT_LOCAL_READ_ONLY",
                "execution_attempted": False,
            }))

        decision = evaluate(proposal)
        if decision.status != "ALLOW_LOCAL_REVIEW":
            return self._record(ToolResult("BLOCK_POLICY", audit={
                **base, "decision": "BLOCK", "policy_status": decision.status,
                "reason_codes": list(decision.reasons), "topic_flags": list(decision.topic_flags),
                "evidence_state": decision.evidence_state, "execution_attempted": False,
            }))

        try:
            value = spec.function(*args, **kwargs)
        except Exception as exc:
            # Do not expose exception text; it may contain paths or private data.
            return self._record(ToolResult("TOOL_ERROR", audit={
                **base, "decision": "ALLOW_LOCAL_READ_ONLY_TOOL", "policy_status": decision.status,
                "execution_attempted": True, "result_state": "ERROR",
                "error_type": type(exc).__name__,
            }))
        return self._record(ToolResult("EXECUTED_LOCAL_READ_ONLY", result=value, audit={
            **base, "decision": "ALLOW_LOCAL_READ_ONLY_TOOL", "policy_status": decision.status,
            "execution_attempted": True, "result_state": "RETURNED",
            "evidence_state": decision.evidence_state,
        }))

    def _record(self, result: ToolResult) -> ToolResult:
        self.audit_log.append(dict(result.audit or {}))
        return result
