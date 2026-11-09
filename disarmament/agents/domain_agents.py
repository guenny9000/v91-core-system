"""Independent deterministic domain agents for disarmament monitoring."""
from .base import SpecialistAgent


class TreatyAgent(SpecialistAgent):
    agent_id = "treaty_obligations"
    domain = "treaty_status_and_obligations"
    accepted_categories = frozenset({"nuclear", "chemical", "biological", "conventional"})


class NuclearArmsAgent(SpecialistAgent):
    agent_id = "nuclear_arsenals"
    domain = "nuclear_arsenals_and_reduction"
    accepted_categories = frozenset({"nuclear"})


class ConventionalArmsAgent(SpecialistAgent):
    agent_id = "conventional_arms"
    domain = "conventional_stockpiles_and_transfers"
    accepted_categories = frozenset({"conventional", "arms_transfers"})


class AutonomousWeaponsAgent(SpecialistAgent):
    agent_id = "autonomous_weapons"
    domain = "autonomous_weapons_governance"
    accepted_categories = frozenset({"autonomous_weapons"})


class SpaceSecurityAgent(SpecialistAgent):
    agent_id = "space_security"
    domain = "space_security_and_civilian_protection"
    accepted_categories = frozenset({"space_security"})


class MilitaryProductionAgent(SpecialistAgent):
    agent_id = "military_production_conversion"
    domain = "military_production_and_civilian_conversion"
    accepted_categories = frozenset({"military_production", "military_expenditure"})


class HumanitarianImpactAgent(SpecialistAgent):
    agent_id = "humanitarian_impact"
    domain = "humanitarian_and_environmental_safeguards"
    accepted_categories = frozenset({
        "nuclear", "chemical", "biological", "conventional",
        "military_production", "demining", "space_security",
    })


class EvidenceAuditAgent(SpecialistAgent):
    agent_id = "evidence_audit"
    domain = "provenance_and_evidence_quality"
    accepted_categories = frozenset({
        "nuclear", "chemical", "biological", "conventional",
        "autonomous_weapons", "space_security", "arms_transfers",
        "military_expenditure", "military_production", "demining",
    })
