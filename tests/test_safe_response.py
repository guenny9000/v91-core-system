'''Tests for controller.safe_response (Issue #276, capability 6).

All test data remains pure ASCII (<= 0x7F) per repo convention.
'''

import unittest

from controller import safe_response as sr


def valid_plan(**overrides):
    base = {
        "plan_id": "PLAN-001",
        "date": "2026-11-21",
        "reviewer": "operator@example",
        "detection": {
            "finding": "dependency with known issue",
            "evidence": {"source": "advisory feed", "checked_on": "2026-11-21"},
        },
        "actions": [
            {"verb": "preserve_evidence"},
            {"verb": "contain", "affects_others": False},
        ],
        "uncertainty_note": "advisory severity unconfirmed locally",
    }
    base.update(overrides)
    return base


class TestRequiredFields(unittest.TestCase):
    def test_valid_plan_approved_for_documentation(self):
        res = sr.validate_response_plan(valid_plan())
        self.assertEqual(res["decision"], "APPROVED_FOR_DOCUMENTATION")
        self.assertEqual(res["violations"], [])

    def test_missing_plan_id_rejected(self):
        res = sr.validate_response_plan(valid_plan(plan_id=""))
        self.assertEqual(res["decision"], "REJECTED")
        self.assertIn("field_missing:plan_id", res["violations"])

    def test_missing_detection_rejected(self):
        res = sr.validate_response_plan(valid_plan(detection={}))
        self.assertIn("detection:missing", res["violations"])

    def test_detection_without_evidence_rejected(self):
        plan = valid_plan()
        plan["detection"] = {"finding": "x"}
        self.assertIn("detection:evidence_missing", sr.validate_response_plan(plan)["violations"])

    def test_detection_evidence_needs_date(self):
        plan = valid_plan()
        plan["detection"] = {
            "finding": "x",
            "evidence": {"source": "feed", "checked_on": ""},
        }
        self.assertIn(
            "detection:evidence_checked_on_missing",
            sr.validate_response_plan(plan)["violations"],
        )

    def test_missing_uncertainty_note_rejected(self):
        res = sr.validate_response_plan(valid_plan(uncertainty_note=" "))
        self.assertIn("record:uncertainty_note_missing", res["violations"])

    def test_non_dict_plan_raises(self):
        with self.assertRaises(sr.SafeResponseError):
            sr.validate_response_plan("not-a-plan")


class TestActions(unittest.TestCase):
    def test_empty_actions_rejected(self):
        res = sr.validate_response_plan(valid_plan(actions=[]))
        self.assertIn("actions:missing_or_empty", res["violations"])

    def test_unknown_verb_rejected(self):
        plan = valid_plan(actions=[{"verb": "reboot_the_world"}])
        self.assertIn("actions:unknown_verb:reboot_the_world", sr.validate_response_plan(plan)["violations"])

    def test_forbidden_unauthorized_access(self):
        plan = valid_plan(actions=[{"verb": "unauthorized_access"}])
        self.assertIn("actions:FORBIDDEN:unauthorized_access", sr.validate_response_plan(plan)["violations"])

    def test_forbidden_retaliation(self):
        plan = valid_plan(actions=[{"verb": "retaliation"}])
        self.assertIn("actions:FORBIDDEN:retaliation", sr.validate_response_plan(plan)["violations"])

    def test_forbidden_censorship(self):
        plan = valid_plan(actions=[{"verb": "censorship"}])
        self.assertIn("actions:FORBIDDEN:censorship", sr.validate_response_plan(plan)["violations"])

    def test_forbidden_records_destruction(self):
        plan = valid_plan(actions=[{"verb": "records_destruction"}])
        self.assertIn("actions:FORBIDDEN:records_destruction", sr.validate_response_plan(plan)["violations"])

    def test_forbidden_denial_of_lawful_service(self):
        plan = valid_plan(actions=[{"verb": "denial_of_lawful_service"}])
        self.assertIn(
            "actions:FORBIDDEN:denial_of_lawful_service",
            sr.validate_response_plan(plan)["violations"],
        )

    def test_malformed_action_entry(self):
        plan = valid_plan(actions=["garbage"])
        self.assertIn("actions:malformed_entry", sr.validate_response_plan(plan)["violations"])


class TestAuthorizationAndNotification(unittest.TestCase):
    def test_impact_affecting_others_needs_authorization(self):
        plan = valid_plan(
            actions=[{"verb": "contain", "affects_others": True}]
        )
        res = sr.validate_response_plan(plan)
        self.assertIn("authorization:missing_for_action_affecting_others", res["violations"])
        self.assertIn("notification:operator_notification_missing", res["violations"])

    def test_authorization_fields_complete(self):
        plan = valid_plan(
            actions=[
                {
                    "verb": "remediate",
                    "affects_others": True,
                    "post_change_check": "service smoke test after patch",
                    "operator_notified": {
                        "addressee": "peer@example",
                        "channel": "signed mail",
                        "sent_on": "2026-11-21",
                    },
                }
            ],
            authorization={
                "authorized_by": "owner",
                "scope": "own node services",
                "date": "2026-11-21",
            },
        )
        res = sr.validate_response_plan(plan)
        self.assertEqual(res["violations"], [])

    def test_authorization_scope_missing_rejected(self):
        plan = valid_plan(
            actions=[
                {
                    "verb": "contain",
                    "affects_others": True,
                    "operator_notified": {
                        "addressee": "peer@example",
                        "channel": "signed mail",
                        "sent_on": "2026-11-21",
                    },
                }
            ],
            authorization={"authorized_by": "owner", "scope": "", "date": "2026-11-21"},
        )
        self.assertIn("authorization:scope_missing", sr.validate_response_plan(plan)["violations"])

    def test_critical_impact_needs_continuity(self):
        plan = valid_plan(
            actions=[{"verb": "contain", "critical_service": True}]
        )
        res = sr.validate_response_plan(plan)
        self.assertIn("critical:impact_without_proven_continuity", res["violations"])

    def test_critical_impact_with_continuity_ok(self):
        plan = valid_plan(
            actions=[{"verb": "contain", "critical_service": True, "continuity_equivalent_proven": True}]
        )
        res = sr.validate_response_plan(plan)
        self.assertEqual(res["violations"], [])


class TestLifecycleOrder(unittest.TestCase):
    def test_isolate_needs_recovery_path(self):
        plan = valid_plan(actions=[{"verb": "isolate"}])
        self.assertIn("isolate_not_destroy:recovery_path_missing", sr.validate_response_plan(plan)["violations"])

    def test_isolate_with_recovery_path_ok(self):
        plan = valid_plan(actions=[{"verb": "isolate", "recovery_path": "re-enable via config"}])
        self.assertEqual(sr.validate_response_plan(plan)["violations"], [])

    def test_remediate_needs_post_change_check(self):
        plan = valid_plan(actions=[{"verb": "remediate"}])
        self.assertIn("remediate:post_change_check_missing", sr.validate_response_plan(plan)["violations"])

    def test_recover_requires_verify_in_same_plan(self):
        plan = valid_plan(
            actions=[
                {"verb": "contain"},
                {"verb": "recover"},
            ]
        )
        self.assertIn("recover:verify_before_recover_missing", sr.validate_response_plan(plan)["violations"])

    def test_recover_after_verify_ok(self):
        plan = valid_plan(
            actions=[
                {"verb": "contain"},
                {"verb": "remediate", "post_change_check": "service smoke test"},
                {"verb": "verify"},
                {"verb": "recover"},
            ]
        )
        self.assertEqual(sr.validate_response_plan(plan)["violations"], [])


class TestHonesty(unittest.TestCase):
    def test_honesty_limits_present(self):
        res = sr.validate_response_plan(valid_plan())
        self.assertIn("PLAN != AUSFUEHRUNG", res["honesty_limits"])
        self.assertIn("DETECTION != AUTHORIZATION", res["honesty_limits"])
        self.assertIn("ISOLATE_NOT_DESTROY", res["honesty_limits"])


if __name__ == "__main__":
    unittest.main()
