import importlib.util
import sys
import unittest
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parents[1] / "global_guard" / "policy.py"
SPEC = importlib.util.spec_from_file_location("v91_global_guard_policy_disarmament", POLICY_PATH)
POLICY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = POLICY
SPEC.loader.exec_module(POLICY)


class DisarmamentGuardTests(unittest.TestCase):
    def test_weapon_and_military_control_actions_are_explicitly_denied(self):
        request = {
            "action_id": "disarmament-guard-001",
            "action_class": "weapon_control",
            "purpose": "Attempt to control an external weapon system.",
            "expected_effect": "No operation is executed.",
        }
        for action_class in (
            "weapon_control", "weapons_development", "military_network_access",
            "remote_satellite_control", "remote_deorbit", "anti_satellite_action",
            "autonomous_attack",
        ):
            with self.subTest(action_class=action_class):
                request["action_class"] = action_class
                decision = POLICY.authorize_action(request)
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.code, "PROHIBITED_ACTION_CLASS")


if __name__ == "__main__":
    unittest.main()
