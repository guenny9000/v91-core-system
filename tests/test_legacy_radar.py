"""Tests fuer controller.legacy_radar (Issue #503, proaktive Legacy-Aufdeckung).

REUSE-Kern: Alle Validierungsregeln bleiben in node_inventory; der Radar
aggregiert nur zu Arbeitsauftraegen. Jeder Item verlangt
FREIGABE_BETREIBER; der Radar entscheidet nichts.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from controller import legacy_radar as lr
from controller.legacy_radar import (
    ITEM_INCOMPLETE,
    ITEM_ISOLATE,
    ITEM_MODERNIZE,
    ITEM_OWNER_UNKNOWN,
    ITEM_RETIRE,
    ITEM_UNKNOWN_EOL,
    NOT_REPORTED,
    RADAR_REPORTED_COMPLETE,
    RADAR_REPORTED_ON_INCOMPLETE_BASIS,
    radar_report,
)

ROOT = Path(__file__).resolve().parents[1]


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
        "migration_plan": "move to open standard replacement",
        "rollback": "reinstall prior version via package cache",
        "continuity_checks": "service check plus smoke test",
    }


def inventory_with(components):
    return {
        "node_id": "node-alpha",
        "date": "2026-11-24",
        "reviewer": "vibe",
        "components": components,
    }


def legacy_component(cid, eol, **extra):
    return valid_component(component_id=cid, eol_status=eol,
                           lifecycle=valid_lifecycle(), **extra)


class RadarReportTest(unittest.TestCase):
    def test_all_supported_no_items(self):
        report = radar_report(inventory_with([
            legacy_component("CMP-1", "supported"),
            legacy_component("CMP-2", "supported"),
        ]))
        self.assertEqual(report["state"], RADAR_REPORTED_COMPLETE)
        self.assertEqual(report["attention_items"], 0)
        self.assertEqual(report["attention_ratio_raw"], 0.0)
        self.assertEqual(report["items"], [])

    def test_replace_yields_modernization_item(self):
        report = radar_report(inventory_with([legacy_component("CMP-1", "replace")]))
        self.assertEqual(report["item_counts"][ITEM_MODERNIZE], 1)
        item = report["items"][0]
        self.assertEqual(item["component_id"], "CMP-1")
        self.assertEqual(item["item_class"], ITEM_MODERNIZE)
        self.assertIn("FREIGABE_BETREIBER", item["required_owner_action"])

    def test_isolate_yields_isolate_item(self):
        report = radar_report(inventory_with([legacy_component("CMP-1", "isolate")]))
        self.assertEqual(report["item_counts"][ITEM_ISOLATE], 1)

    def test_isolate_critical_warning(self):
        lifecycle = valid_lifecycle()
        lifecycle["reversible_in_principle"] = True
        report = radar_report(inventory_with([
            valid_component(component_id="CMP-1", eol_status="isolate",
                            critical_service=True, lifecycle=lifecycle,
                            continuity_equivalent_proven=True),
        ]))
        items = [i for i in report["items"] if i["item_class"] == ITEM_ISOLATE]
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertIn("critical_service_warning", item)
        self.assertIn("Betreiber", item["critical_service_warning"])

    def test_retire_yields_retire_item(self):
        report = radar_report(inventory_with([
            legacy_component("CMP-1", "retire", retire_reversibility="restore from archive"),
        ]))
        self.assertEqual(report["item_counts"][ITEM_RETIRE], 1)

    def test_unknown_eol_item(self):
        report = radar_report(inventory_with([legacy_component("CMP-1", "unknown")]))
        self.assertEqual(report["item_counts"][ITEM_UNKNOWN_EOL], 1)
        self.assertIn("UNKNOWN != PASS", report["items"][0]["reason"])

    def test_missing_owner_item(self):
        report = radar_report(inventory_with([
            legacy_component("CMP-1", "supported", owner="  "),
        ]))
        self.assertEqual(report["item_counts"][ITEM_OWNER_UNKNOWN], 1)

    def test_multiple_items_and_ratio_raw(self):
        report = radar_report(inventory_with([
            legacy_component("CMP-1", "replace"),
            legacy_component("CMP-2", "unknown"),
            legacy_component("CMP-3", "supported"),
            legacy_component("CMP-4", "supported"),
        ]))
        self.assertEqual(report["attention_items"], 2)
        self.assertEqual(report["attention_ratio_raw"], 0.5)
        self.assertEqual(report["components_total"], 4)

    def test_incomplete_base_entry_passthrough(self):
        bad = valid_component()
        bad.pop("owner")
        report = radar_report(inventory_with([bad]))
        self.assertEqual(report["item_counts"][ITEM_INCOMPLETE], 1)
        self.assertIn("Basis-Validierung INCOMPLETE", report["items"][0]["reason"])

    def test_incomplete_basis_state(self):
        bad = valid_component()
        bad.pop("owner")
        report = radar_report(inventory_with([bad, legacy_component("CMP-2", "supported")]))
        self.assertEqual(report["state"], RADAR_REPORTED_ON_INCOMPLETE_BASIS)
        self.assertEqual(report["basis_decision"], "INVENTORY_INCOMPLETE")

    def test_rejected_inventory_not_reported_no_numbers(self):
        report = radar_report(inventory_with([]))
        self.assertEqual(report["state"], NOT_REPORTED)
        self.assertIn("REJECTED", report["reason"])
        self.assertEqual(report["items"], [])

    def test_non_dict_input_not_reported(self):
        report = radar_report(["kein", "inventar"])
        self.assertEqual(report["state"], NOT_REPORTED)

    def test_item_counts_keys_complete(self):
        report = radar_report(inventory_with([legacy_component("CMP-1", "supported")]))
        self.assertEqual(set(report["item_counts"]),
                         {ITEM_MODERNIZE, ITEM_ISOLATE, ITEM_RETIRE,
                          ITEM_UNKNOWN_EOL, ITEM_OWNER_UNKNOWN, ITEM_INCOMPLETE})

    def test_honesty_limits_present(self):
        report = radar_report(inventory_with([legacy_component("CMP-1", "supported")]))
        self.assertIn("KLASSIFIKATION != EINGRIFF", report["honesty_limits"])

    def test_no_duplicate_of_coverage_kennzahlen(self):
        # Der Radar erzeugt Arbeitsauftraege, KEINE zweiten AK-1-Messzahlen.
        report = radar_report(inventory_with([legacy_component("CMP-1", "replace")]))
        self.assertNotIn("eol_distribution", report)
        self.assertNotIn("eol_status_known_ratio_raw", report)


class RadarCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.inv = Path(self.tmp.name) / "inventory.json"
        self.inv.write_text(json.dumps(inventory_with([
            legacy_component("CMP-1", "replace"),
        ])), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *args):
        env = {"PYTHONPATH": str(ROOT), "PATH": __import__("os").environ.get("PATH", "")}
        return subprocess.run(
            [sys.executable, "-m", "controller.legacy_radar", *args],
            capture_output=True, text=True, env=env, cwd=str(ROOT),
        )

    def test_cli_exit_0_report(self):
        result = self._run(str(self.inv))
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report["item_counts"][ITEM_MODERNIZE], 1)

    def test_cli_exit_2_on_unreadable_target(self):
        result = self._run(str(self.inv.with_name("fehlt.json")))
        self.assertEqual(result.returncode, 2)

    def test_cli_exit_2_on_invalid_json(self):
        self.inv.write_text("{kein json", encoding="utf-8")
        result = self._run(str(self.inv))
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
