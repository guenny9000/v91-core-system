'''Tests for controller.node_inventory (Issue #276, capabilities 1+2).

All test data remains pure ASCII (<= 0x7F) per repo convention.
'''

import unittest

from controller import node_inventory as ni


def valid_component(**overrides):
    base = {
        "component_id": "CMP-001",
        "kind": "software",
        "name": "example-package",
        "owner": "operator@example",
        "evidence": {"source": "repo lockfile", "checked_on": "2026-11-21"},
        "eol_status": "supported",
        "in_active_use": True,
    }
    base.update(overrides)
    return base


def valid_lifecycle():
    return {
        "dependency_map": "two deps, docs/depmap.md",
        "risk_assessment": "low, docs/risk.md",
        "migration_plan": "move to open_standard replacement",
        "rollback": "reinstall prior version via package cache",
        "continuity_checks": "service check plus user smoke test",
    }


class TestValidateComponent(unittest.TestCase):
    def test_valid_component_ok(self):
        self.assertEqual(ni.validate_component(valid_component())["result"], "OK")

    def test_missing_id_rejected(self):
        comp = valid_component()
        del comp["component_id"]
        res = ni.validate_component(comp)
        self.assertEqual(res["result"], "INCOMPLETE")
        self.assertIn("field_missing:component_id", res["violations"])

    def test_missing_owner_rejected(self):
        res = ni.validate_component(valid_component(owner=""))
        self.assertIn("field_missing:owner", res["violations"])

    def test_unknown_kind_rejected(self):
        res = ni.validate_component(valid_component(kind="magic"))
        self.assertIn("kind:unknown_or_missing", res["violations"])

    def test_missing_evidence_rejected(self):
        res = ni.validate_component(valid_component(evidence={}))
        self.assertIn("evidence:missing", res["violations"])

    def test_evidence_without_date_rejected(self):
        comp = valid_component(
            evidence={"source": "repo lockfile", "checked_on": ""}
        )
        self.assertIn("evidence:checked_on_missing", ni.validate_component(comp)["violations"])

    def test_unknown_eol_status_is_honest_not_violation(self):
        res = ni.validate_component(valid_component(eol_status="unknown"))
        self.assertEqual(res["result"], "OK")
        self.assertEqual(res["violations"], [])

    def test_eol_status_requires_known_value(self):
        res = ni.validate_component(valid_component(eol_status="later"))
        self.assertIn("eol_status:unknown_or_missing", res["violations"])

    def test_replace_requires_lifecycle(self):
        res = ni.validate_component(
            valid_component(eol_status="replace", lifecycle=None)
        )
        self.assertIn("lifecycle:plan_missing_for_legacy_classification", res["violations"])

    def test_lifecycle_missing_field_collected(self):
        lifecycle = valid_lifecycle()
        del lifecycle["rollback"]
        res = ni.validate_component(
            valid_component(eol_status="replace", lifecycle=lifecycle)
        )
        self.assertIn("lifecycle:rollback_missing", res["violations"])

    def test_lifecycle_rollback_none_rejected(self):
        lifecycle = valid_lifecycle()
        lifecycle["rollback"] = "none"
        res = ni.validate_component(
            valid_component(eol_status="replace", lifecycle=lifecycle)
        )
        self.assertIn("lifecycle:rollback_must_be_documented_path", res["violations"])

    def test_in_active_use_must_be_boolean(self):
        res = ni.validate_component(valid_component(in_active_use="yes"))
        self.assertIn("in_active_use:must_be_boolean", res["violations"])

    def test_critical_isolate_needs_continuity(self):
        lifecycle = valid_lifecycle()
        res = ni.validate_component(
            valid_component(
                kind="exposed_service",
                critical_service=True,
                eol_status="isolate",
                lifecycle=lifecycle,
            )
        )
        self.assertIn(
            "critical:isolate_or_retire_without_proven_continuity", res["violations"]
        )

    def test_critical_isolate_with_continuity_ok(self):
        lifecycle = valid_lifecycle()
        lifecycle["continuity_equivalent_proven"] = True
        res = ni.validate_component(
            valid_component(
                kind="exposed_service",
                critical_service=True,
                eol_status="isolate",
                lifecycle=lifecycle,
            )
        )
        self.assertNotIn(
            "critical:isolate_or_retire_without_proven_continuity", res["violations"]
        )

    def test_critical_not_on_cost_grounds_alone(self):
        res = ni.validate_component(
            valid_component(
                critical_service=True,
                cheaper_replacement_only=True,
                eol_status="replace",
                lifecycle=valid_lifecycle(),
            )
        )
        self.assertIn("critical:not_on_cost_grounds_alone", res["violations"])

    def test_retire_requires_preserved_records(self):
        res = ni.validate_component(
            valid_component(
                eol_status="retire",
                lifecycle=valid_lifecycle(),
            )
        )
        self.assertIn("isolate_not_destroy:records_must_be_preserved", res["violations"])

    def test_retire_reversible_in_principle(self):
        lifecycle = valid_lifecycle()
        lifecycle["reversible_in_principle"] = True
        res = ni.validate_component(
            valid_component(
                eol_status="retire", lifecycle=lifecycle, records_preserved=True
            )
        )
        self.assertEqual(res["result"], "OK")

    def test_non_dict_component_raises(self):
        with self.assertRaises(ni.NodeInventoryError):
            ni.validate_component(["not", "a", "dict"])


class TestValidateInventory(unittest.TestCase):
    def test_valid_inventory_complete(self):
        inv = {
            "node_id": "NODE-A",
            "date": "2026-11-21",
            "reviewer": "operator@example",
            "components": [valid_component(), valid_component(
                component_id="CMP-002", kind="key", name="ssh-host-key"
            )],
        }
        res = ni.validate_inventory(inv)
        self.assertEqual(res["decision"], "INVENTORY_COMPLETE")
        self.assertEqual(res["components_total"], 2)
        self.assertEqual(res["components_incomplete"], 0)
        self.assertEqual(res["components_by_kind"]["software"], 1)
        self.assertEqual(res["components_by_kind"]["key"], 1)

    def test_unknown_eol_counted(self):
        inv = {
            "node_id": "NODE-A",
            "date": "2026-11-21",
            "reviewer": "operator@example",
            "components": [valid_component(eol_status="unknown")],
        }
        res = ni.validate_inventory(inv)
        self.assertEqual(res["decision"], "INVENTORY_COMPLETE")
        self.assertEqual(res["components_unknown_eol"], 1)

    def test_incomplete_component_marked(self):
        inv = {
            "node_id": "NODE-A",
            "date": "2026-11-21",
            "reviewer": "operator@example",
            "components": [valid_component(), valid_component(component_id="")],
        }
        res = ni.validate_inventory(inv)
        self.assertEqual(res["decision"], "INVENTORY_INCOMPLETE")
        self.assertEqual(res["components_incomplete"], 1)

    def test_missing_header_fields_rejected(self):
        inv = {"node_id": "", "date": "2026-11-21", "reviewer": "x", "components": [valid_component()]}
        res = ni.validate_inventory(inv)
        self.assertEqual(res["decision"], "REJECTED")
        self.assertIn("field_missing:node_id", res["violations"])

    def test_empty_components_rejected(self):
        inv = {
            "node_id": "NODE-A",
            "date": "2026-11-21",
            "reviewer": "operator@example",
            "components": [],
        }
        res = ni.validate_inventory(inv)
        self.assertIn("components:empty_or_missing", res["violations"])

    def test_non_dict_component_in_list_handled(self):
        inv = {
            "node_id": "NODE-A",
            "date": "2026-11-21",
            "reviewer": "operator@example",
            "components": [valid_component(), "garbage"],
        }
        res = ni.validate_inventory(inv)
        self.assertEqual(res["components_incomplete"], 1)
        self.assertEqual(res["components_by_kind"]["unknown"], 1)

    def test_non_dict_inventory_raises(self):
        with self.assertRaises(ni.NodeInventoryError):
            ni.validate_inventory(["not", "inventory"])

    def test_honesty_limits_present(self):
        res = ni.validate_inventory(
            {
                "node_id": "N",
                "date": "2026-11-21",
                "reviewer": "r",
                "components": [valid_component()],
            }
        )
        self.assertIn("SCRIPTED != INSTALLED", res["honesty_limits"])
        self.assertIn("KLASSIFIKATION != EINGRIFF", res["honesty_limits"])


if __name__ == "__main__":
    unittest.main()
