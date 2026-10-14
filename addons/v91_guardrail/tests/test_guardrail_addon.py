import unittest

from addons.v91_guardrail import PolicyContext, evaluate, evaluate_batch


class GuardrailAddonTests(unittest.TestCase):
    def test_empty_request_fails_closed(self):
        self.assertEqual(evaluate(" ").status, "BLOCK")

    def test_war_topic_requires_review_not_action(self):
        decision = evaluate("Analysiere öffentliche Berichte über Krieg.")
        self.assertEqual(decision.status, "REVIEW_REQUIRED")
        self.assertIn("CONFLICT_OR_WAR", decision.topic_flags)
        self.assertEqual(decision.evidence_state, "PENDING_WITNESS")
        self.assertFalse(decision.action_performed)

    def test_resource_topic_is_flagged(self):
        decision = evaluate("Prüfe Energieverbrauch, CO2 und Überproduktion.")
        self.assertEqual(decision.status, "REVIEW_REQUIRED")
        self.assertIn("RESOURCE_OR_ENVIRONMENT", decision.topic_flags)

    def test_luxury_overproduction_is_not_auto_banned(self):
        decision = evaluate("Prüfe Luxusüberproduktion anhand transparenter Kriterien.")
        self.assertEqual(decision.status, "REVIEW_REQUIRED")
        self.assertIn("LUXURY_OR_NONESSENTIAL_PRODUCTION", decision.topic_flags)

    def test_unauthorized_network_request_blocks(self):
        decision = evaluate("Suche Berichte", context=PolicyContext(network_requested=True))
        self.assertEqual(decision.status, "BLOCK")
        self.assertIn("NETWORK_ACCESS_NOT_AUTHORIZED", decision.reasons)

    def test_authorized_source_still_performs_no_action(self):
        decision = evaluate("Suche Berichte", context=PolicyContext(
            network_requested=True, source_is_authorized=True))
        self.assertFalse(decision.action_performed)

    def test_destructive_action_needs_separate_approval(self):
        decision = evaluate("Lösche nicht benötigte Dateien.", context=PolicyContext(
            destructive_action_requested=True))
        self.assertEqual(decision.status, "BLOCK")

    def test_execution_language_blocks(self):
        self.assertEqual(evaluate("Führe aus: powershell -Command ...").status, "BLOCK")

    def test_private_data_is_blocked_when_declared(self):
        self.assertEqual(evaluate("Analysiere", context=PolicyContext(
            private_data_requested=True)).status, "BLOCK")

    def test_privilege_change_is_blocked(self):
        self.assertEqual(evaluate("Prüfe", context=PolicyContext(
            privilege_change_requested=True)).status, "BLOCK")

    def test_read_only_analysis_can_be_disabled(self):
        self.assertEqual(evaluate("Analysiere öffentliche Berichte", context=PolicyContext(
            allow_read_only_analysis=False)).status, "BLOCK")

    def test_claim_never_becomes_verified(self):
        decision = evaluate("V91 ist perfekt.")
        self.assertEqual(decision.evidence_state, "DOCUMENTED_INPUT_ONLY")
        self.assertFalse(decision.action_performed)

    def test_batch_returns_one_decision_per_input(self):
        results = evaluate_batch(["Krieg", "öffentliche Lageanalyse"])
        self.assertEqual(len(results), 2)
        self.assertTrue(all(not item.action_performed for item in results))


if __name__ == "__main__":
    unittest.main()
