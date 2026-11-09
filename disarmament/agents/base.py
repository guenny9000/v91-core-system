"""Common contracts for independent, read-only disarmament specialist agents."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AgentFinding:
    agent_id: str
    subject_id: str
    domain: str
    status: str
    summary: str
    evidence_refs: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    recommended_next_step: str = "HUMAN_REVIEW"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence_refs"] = list(self.evidence_refs)
        result["limitations"] = list(self.limitations)
        return result


class SpecialistAgent:
    """A deterministic specialist over supplied records; no network or tools."""

    agent_id = "abstract"
    domain = "abstract"
    accepted_categories: frozenset[str] = frozenset()

    def analyze(self, records: list[dict[str, Any]]) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            if record.get("category") not in self.accepted_categories:
                continue
            record_id = record.get("record_id")
            if not isinstance(record_id, str) or not record_id.strip():
                findings.append(AgentFinding(
                    self.agent_id, "UNKNOWN", self.domain, "UNKNOWN",
                    "Record has no usable identifier.",
                    limitations=("Input schema incomplete; no conclusion drawn.",),
                ))
                continue
            grade = record.get("evidence_grade", "UNKNOWN")
            if grade not in {"VERIFIED", "CORROBORATED", "DOCUMENTED", "UNKNOWN"}:
                grade = "UNKNOWN"
            findings.append(AgentFinding(
                self.agent_id, record_id, self.domain, grade,
                "Record routed to domain specialist; no claim beyond supplied evidence.",
                evidence_refs=(record_id,) if grade != "UNKNOWN" else (),
                limitations=(
                    "Agent evaluates supplied normalized records only.",
                    "Evidence grade is inherited, not independently re-verified by this agent.",
                    "No global compliance or disarmament conclusion is made.",
                ),
            ))
        return findings
