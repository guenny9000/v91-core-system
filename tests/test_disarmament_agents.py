import unittest

from disarmament.agents import DisarmamentAgentCouncil


class DisarmamentAgentCouncilTests(unittest.TestCase):
    def test_eight_specialists_are_registered(self):
        council = DisarmamentAgentCouncil()
        self.assertEqual(len(council.agents), 8)
        self.assertEqual(len({agent.agent_id for agent in council.agents}), 8)

    def test_record_is_routed_to_multiple_relevant_agents(self):
        report = DisarmamentAgentCouncil().run({"records": [{
            "record_id": "space-001",
            "category": "space_security",
            "evidence_grade": "DOCUMENTED",
        }]})
        ids = {item["agent_id"] for item in report["findings"]}
        self.assertIn("space_security", ids)
        self.assertIn("humanitarian_impact", ids)
        self.assertIn("evidence_audit", ids)

    def test_agents_do_not_upgrade_evidence_or_claim_global_status(self):
        report = DisarmamentAgentCouncil().run({"records": [{
            "record_id": "nuclear-001",
            "category": "nuclear",
            "evidence_grade": "DOCUMENTED",
        }]})
        self.assertTrue(all(x["status"] == "DOCUMENTED" for x in report["findings"]))
        self.assertEqual(report["global_disarmament_status"], "UNKNOWN")
        self.assertFalse(report["autonomous_actions"])
        self.assertTrue(report["human_review_required"])

    def test_invalid_grade_is_unknown(self):
        report = DisarmamentAgentCouncil().run({"records": [{
            "record_id": "arms-001",
            "category": "conventional",
            "evidence_grade": "PASS",
        }]})
        self.assertTrue(all(x["status"] == "UNKNOWN" for x in report["findings"]))

    def test_conflicting_agent_assessments_are_escalated(self):
        from disarmament.agents.base import SpecialistAgent, AgentFinding

        class A(SpecialistAgent):
            agent_id = "a"
            domain = "a"
            accepted_categories = frozenset({"nuclear"})

            def analyze(self, records):
                return [AgentFinding("a", "same", "a", "DOCUMENTED", "a")]

        class B(SpecialistAgent):
            agent_id = "b"
            domain = "b"
            accepted_categories = frozenset({"nuclear"})

            def analyze(self, records):
                return [AgentFinding("b", "same", "b", "CORROBORATED", "b")]

        report = DisarmamentAgentCouncil((A, B)).run({"records": [{"category": "nuclear"}]})
        self.assertEqual(report["conflicts"][0]["status"], "CONFLICT_REQUIRES_HUMAN_REVIEW")

    def test_no_records_means_unknown(self):
        report = DisarmamentAgentCouncil().run({"records": []})
        self.assertEqual(report["council_status"], "UNKNOWN")
        self.assertEqual(report["finding_count"], 0)


if __name__ == "__main__":
    unittest.main()
