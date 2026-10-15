import importlib.util
import sys
import unittest
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parents[1] / "global_guard" / "policy.py"
SPEC = importlib.util.spec_from_file_location("v91_global_guard_policy", POLICY_PATH)
POLICY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = POLICY
SPEC.loader.exec_module(POLICY)
GuardPolicy = POLICY.GuardPolicy
authorize_action = POLICY.authorize_action


def request(**overrides):
    value = {
        "action_id": "test-001",
        "action_class": "read_only",
        "purpose": "Lokale, isolierte Prüfung.",
        "expected_effect": "Eine strukturierte Prüfausgabe.",
        "steps": 1,
        "external_calls": 0,
        "cost_units": 1,
        "output_bytes": 100,
    }
    value.update(overrides)
    return value


class GlobalGuardTests(unittest.TestCase):
    def test_safe_read_only_request_is_allowed(self):
        decision = authorize_action(request())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.code, "ALLOW_WITHIN_POLICY")

    def test_unknown_action_class_fails_closed(self):
        decision = authorize_action(request(action_class="do_anything"))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "UNKNOWN_ACTION_CLASS")

    def test_violence_and_propagation_classes_are_denied(self):
        for action_class in (
            "weapons_development", "target_selection_for_violence",
            "autonomous_attack", "unauthorized_propagation",
            "credential_exfiltration", "destructive_cleanup",
        ):
            with self.subTest(action_class=action_class):
                decision = authorize_action(request(action_class=action_class))
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.code, "PROHIBITED_ACTION_CLASS")

    def test_network_disabled_even_if_class_is_granted(self):
        policy = GuardPolicy(allowed_capabilities=frozenset({"network_read"}))
        decision = authorize_action(request(action_class="network_read"), policy)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "NETWORK_DISABLED")

    def test_resource_limit_enforced(self):
        decision = authorize_action(request(steps=101))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "RESOURCE_LIMIT_EXCEEDED")

    def test_mutation_requires_approval_and_capability(self):
        policy = GuardPolicy(allowed_capabilities=frozenset({"file_write"}))
        req = request(action_class="file_write")
        denied = authorize_action(req, policy)
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, "HUMAN_APPROVAL_REQUIRED")
        allowed = authorize_action(req, policy, human_approved=True)
        self.assertTrue(allowed.allowed)

    def test_missing_purpose_is_denied(self):
        decision = authorize_action(request(purpose=""))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "INVALID_PURPOSE")

    def test_model_and_production_changes_stay_disabled(self):
        policy = GuardPolicy(allowed_capabilities=frozenset({"model_change", "production_change"}))
        model = authorize_action(request(action_class="model_change"), policy,
                                 human_approved=True)
        prod = authorize_action(request(action_class="production_change"), policy,
                                human_approved=True)
        self.assertEqual(model.code, "MODEL_CHANGE_DISABLED")
        self.assertEqual(prod.code, "PRODUCTION_CHANGE_DISABLED")


if __name__ == "__main__":
    unittest.main()
