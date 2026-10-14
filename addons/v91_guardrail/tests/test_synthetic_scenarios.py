import unittest

from addons.v91_guardrail.scenario_runner import run_scenarios


class SyntheticScenarioTests(unittest.TestCase):
    def test_all_fictional_scenarios_match_expected_rules(self):
        report = run_scenarios()
        self.assertEqual(report["environment"], "SIMULATED_CLOSED_WORLD")
        self.assertGreaterEqual(report["scenario_count"], 7)
        self.assertEqual(report["fail_count"], 0, report)
        self.assertEqual(report["pass_count"], report["scenario_count"])

    def test_report_has_reproducibility_hash_and_no_real_actions(self):
        report = run_scenarios()
        self.assertEqual(len(report["catalog_sha256"]), 64)
        for result in report["results"]:
            self.assertTrue(result["checks"]["no_action_performed"])
            self.assertTrue(result["fictional_entity"].endswith("(fictional)") or result["entity_type"] == "state")


if __name__ == "__main__":
    unittest.main()
