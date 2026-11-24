"""Tests fuer controller.legacy_coverage (Issue #276, AK-1-Messzahlen).

REUSE-Kern: Alle Validierungsregeln bleiben in node_inventory; hier wird
nur aggregiert. Ehrliche Grenzen: DECKUNG == ANTEIL_DER_ERFASSTEN,
UNKNOWN zaehlt nicht als bekannt, Zahlen nie ohne Zaehler+Nenner.
"""
import json
import tempfile
import unittest
from pathlib import Path

from controller import legacy_coverage as lc
from controller.legacy_coverage import (
    NOT_REPORTED,
    REPORTED_COMPLETE,
    REPORTED_ON_INCOMPLETE_BASIS,
    main as cli_main,
)


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


class TestCoverageReport(unittest.TestCase):
    def test_complete_inventory_full_owner_and_known_eol(self):
        inv = inventory_with([legacy_component("CMP-1", "supported"),
                               legacy_component("CMP-2", "replace")])
        report = lc.coverage_report(inv)
        self.assertEqual(report["state"], REPORTED_COMPLETE)
        self.assertEqual(report["basis_decision"], "INVENTORY_COMPLETE")
        self.assertEqual(report["components_total"], 2)
        self.assertEqual(report["owner_named"], 2)
        self.assertEqual(report["owner_named_ratio_raw"], 1.0)
        self.assertEqual(report["eol_distribution"]["supported"], 1)
        self.assertEqual(report["eol_distribution"]["replace"], 1)
        self.assertEqual(report["eol_status_known_ratio_raw"], 1.0)

    def test_unknown_eol_counts_total_but_not_known(self):
        comp = valid_component()
        comp["eol_status"] = "unknown"
        inv = inventory_with([comp])
        report = lc.coverage_report(inv)
        self.assertEqual(report["state"], REPORTED_COMPLETE)
        self.assertEqual(report["eol_distribution"]["unknown"], 1)
        self.assertEqual(report["eol_status_known"], 0)
        self.assertEqual(report["eol_status_known_ratio_raw"], 0.0)

    def test_incomplete_basis_is_reported_honestly(self):
        broken = valid_component()
        del broken["owner"]
        inv = inventory_with([legacy_component("CMP-1", "supported"), broken])
        report = lc.coverage_report(inv)
        self.assertEqual(report["state"], REPORTED_ON_INCOMPLETE_BASIS)
        self.assertEqual(report["basis_decision"], "INVENTORY_INCOMPLETE")
        self.assertEqual(report["components_total"], 2)
        self.assertEqual(report["owner_named"], 1)
        self.assertAlmostEqual(report["owner_named_ratio_raw"], 0.5)

    def test_rejected_inventory_yields_not_reported_no_numbers(self):
        inv = inventory_with([])  # components leer -> REJECTED im Validator
        report = lc.coverage_report(inv)
        self.assertEqual(report["state"], NOT_REPORTED)
        self.assertNotIn("components_total", report)

    def test_non_dict_inventory_is_not_reported(self):
        report = lc.coverage_report(["kein", "inventar"])
        self.assertEqual(report["state"], NOT_REPORTED)
        self.assertIn("rejected by validator", report["reason"])

    def test_missing_inventory_fields_not_reported(self):
        inv = {"components": [valid_component()]}
        report = lc.coverage_report(inv)
        self.assertEqual(report["state"], NOT_REPORTED)

    def test_critical_isolate_retire_flagged_even_on_incomplete_basis(self):
        # Ohne continuity_equivalent_proven bleibt die Basis INCOMPLETE
        # (Kritikalitaets-Waechter im Validator); die Warnung wird trotz
        # unvollstaendiger Basis NICHT verschwiegen.
        inv = inventory_with([
            legacy_component("CMP-1", "isolate", critical_service=True),
        ])
        report = lc.coverage_report(inv)
        self.assertEqual(report["state"], REPORTED_ON_INCOMPLETE_BASIS)
        flags = report["critical_plan_flags"]
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["component_id"], "CMP-1")
        self.assertIn("KLASSIFIKATION != EINGRIFF", flags[0]["warning"])

    def test_critical_isolate_with_proven_continuity_complete(self):
        lifecycle = valid_lifecycle()
        lifecycle["continuity_equivalent_proven"] = True
        comp = valid_component(component_id="CMP-1", eol_status="isolate",
                               critical_service=True, lifecycle=lifecycle)
        inv = inventory_with([comp])
        report = lc.coverage_report(inv)
        self.assertEqual(report["state"], REPORTED_COMPLETE)

    def test_critical_supported_not_flagged(self):
        inv = inventory_with([
            legacy_component("CMP-1", "supported", critical_service=True),
        ])
        report = lc.coverage_report(inv)
        self.assertEqual(report["critical_plan_flags"], [])

    def test_non_critical_retire_not_flagged(self):
        inv = inventory_with([legacy_component("CMP-1", "retire")])
        report = lc.coverage_report(inv)
        self.assertEqual(report["critical_plan_flags"], [])

    def test_eol_distribution_buckets_and_invalid(self):
        good = legacy_component("CMP-1", "supported")
        unclear = valid_component(eol_status="unknown")
        # Fuer den invalid-eol-Bucket: Eintrag mit ungueltigem eol_status
        # (Regeln bleiben im Validator; hier zaehlt nur die Aggregation).
        bad = valid_component()
        bad["eol_status"] = "sometime"
        inv = inventory_with([good, unclear, bad])
        report = lc.coverage_report(inv)
        dist = report["eol_distribution"]
        self.assertEqual(dist["supported"], 1)
        self.assertEqual(dist["unknown"], 1)
        self.assertEqual(dist["invalid_or_missing"], 1)
        self.assertEqual(report["components_total"], 3)
        self.assertAlmostEqual(report["eol_status_known_ratio_raw"], 1 / 3)

    def test_honesty_limits_in_every_report(self):
        inv = inventory_with([legacy_component("CMP-1", "supported")])
        report = lc.coverage_report(inv)
        self.assertIn("ANTEIL_DER_ERFASSTEN", report["honesty_limits"])
        self.assertIn("UNKNOWN_ZAEHLT_NICHT_ALS_BEKANNT", report["honesty_limits"])


class TestCli(unittest.TestCase):
    def _write(self, payload):
        tmp = tempfile.mkdtemp()
        path = Path(tmp) / "inventory.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_cli_complete_exit_zero(self):
        path = self._write(inventory_with([legacy_component("CMP-1", "supported")]))
        self.assertEqual(cli_main(["--inventory", str(path)]), 0)

    def test_cli_incomplete_basis_exit_zero(self):
        broken = valid_component()
        del broken["evidence"]
        path = self._write(inventory_with([broken]))
        self.assertEqual(cli_main(["--inventory", str(path)]), 0)

    def test_cli_rejected_exit_one(self):
        path = self._write({"components": []})
        self.assertEqual(cli_main(["--inventory", str(path)]), 1)

    def test_cli_missing_file_exit_two(self):
        self.assertEqual(cli_main(["--inventory", "/does/not/exist.json"]), 2)


if __name__ == "__main__":
    unittest.main()
