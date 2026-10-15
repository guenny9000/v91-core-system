"""Deterministic 30-case regression matrix for V91 Global Guard."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from global_guard.policy import GuardPolicy, authorize_action


def request(**overrides):
    value = {
        "action_id": "matrix-case",
        "action_class": "read_only",
        "purpose": "Deterministic isolated regression case",
        "expected_effect": "Return a policy decision only",
        "steps": 1,
        "external_calls": 0,
        "cost_units": 1,
        "output_bytes": 128,
    }
    value.update(overrides)
    return value


class GlobalGuardMatrixTests(unittest.TestCase):
    def test_thirty_cases_match_expected_policy(self):
        cases = []
        for index in range(10):
            capability = "read_only" if index % 2 == 0 else "local_analysis"
            cases.append((f"allow-{index:02d}", request(
                action_id=f"allow-{index:02d}", action_class=capability,
                steps=index + 1, output_bytes=128 + index), True))

        denied_requests = [
            request(action_class="unknown_power"),
            request(action_class="weapons_development"),
            request(action_class="target_selection_for_violence"),
            request(action_class="autonomous_attack"),
            request(action_class="unauthorized_propagation"),
            request(action_class="credential_exfiltration"),
            request(action_class="destructive_cleanup"),
            request(action_class="network_read"),
            request(network_required=True),
            request(model_change=True),
            request(production_change=True),
            request(steps=101),
            request(external_calls=1),
            request(cost_units=101),
            request(output_bytes=1_000_001),
            request(steps=True),
            request(action_id=""),
            request(purpose=""),
            request(expected_effect=""),
            request(action_class="file_write"),
        ]
        cases.extend((f"deny-{index:02d}", item, False)
                     for index, item in enumerate(denied_requests))
        self.assertEqual(len(cases), 30)

        for name, item, expected in cases:
            with self.subTest(case=name):
                decision = authorize_action(item)
                self.assertEqual(decision.allowed, expected, decision.to_dict())

    def test_malformed_approval_flag_fails_closed(self):
        decision = authorize_action(request(), human_approved="false")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "INVALID_APPROVAL_FLAG")

    def test_non_mapping_request_fails_closed(self):
        decision = authorize_action(["not", "a", "mapping"])
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "INVALID_REQUEST")

    def test_invalid_policy_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            GuardPolicy(max_steps=True)
        with self.assertRaises(ValueError):
            GuardPolicy(allow_network="false")
        with self.assertRaises(ValueError):
            GuardPolicy(allowed_capabilities=frozenset({"arbitrary_power"}))


if __name__ == "__main__":
    unittest.main()
