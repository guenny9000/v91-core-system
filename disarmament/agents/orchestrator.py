"""Coordinator for independent specialist findings.

The coordinator routes supplied records and summarizes disagreements.
It never votes a claim into truth, fetches sources, or performs operations.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .base import SpecialistAgent
from .domain_agents import (
    AutonomousWeaponsAgent,
    ConventionalArmsAgent,
    EvidenceAuditAgent,
    HumanitarianImpactAgent,
    MilitaryProductionAgent,
    NuclearArmsAgent,
    SpaceSecurityAgent,
    TreatyAgent,
)


DEFAULT_AGENTS = (
    TreatyAgent,
    NuclearArmsAgent,
    ConventionalArmsAgent,
    AutonomousWeaponsAgent,
    SpaceSecurityAgent,
    MilitaryProductionAgent,
    HumanitarianImpactAgent,
    EvidenceAuditAgent,
)


class DisarmamentAgentCouncil:
    """Runs isolated deterministic specialists on the same immutable input set."""

    def __init__(self, agents: tuple[type[SpecialistAgent], ...] = DEFAULT_AGENTS):
        if not agents or len({agent.agent_id for agent in agents}) != len(agents):
            raise ValueError("Agent set must be non-empty and agent IDs unique")
        self.agents = tuple(agent() for agent in agents)

    def run(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
            raise ValueError("payload must contain a records list")
        records = payload["records"]
        if any(not isinstance(item, dict) for item in records):
            raise ValueError("every record must be an object")

        findings = []
        for agent in self.agents:
            findings.extend(agent.analyze(records))

        counts = Counter(item.status for item in findings)
        subjects: dict[str, list[dict[str, Any]]] = {}
        for finding in findings:
            subjects.setdefault(finding.subject_id, []).append(finding.to_dict())

        conflicts = []
        for subject_id, items in subjects.items():
            grades = {item["status"] for item in items if item["status"] != "UNKNOWN"}
            if len(grades) > 1:
                conflicts.append({
                    "subject_id": subject_id,
                    "status": "CONFLICT_REQUIRES_HUMAN_REVIEW",
                    "agent_positions": [
                        {"agent_id": item["agent_id"], "status": item["status"]}
                        for item in items
                    ],
                })

        return {
            "council_status": "OBSERVED" if findings else "UNKNOWN",
            "scope": "supplied_records_only",
            "agents_configured": [agent.agent_id for agent in self.agents],
            "agents_executed": len(self.agents),
            "finding_count": len(findings),
            "status_counts": {
                key: counts.get(key, 0)
                for key in ("VERIFIED", "CORROBORATED", "DOCUMENTED", "UNKNOWN")
            },
            "findings": [item.to_dict() for item in findings],
            "conflicts": conflicts,
            "global_disarmament_status": "UNKNOWN",
            "global_inventory_total": None,
            "autonomous_actions": False,
            "network_access": False,
            "operational_controls": False,
            "human_review_required": True,
        }
