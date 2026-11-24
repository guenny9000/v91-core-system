"""Tests fuer controller.cumulative_stress (kumulative Domaenen-Belastung).

Integrationstest gegen das ECHTE importierbare controller-Paket
(import controller.cumulative_stress steht fuer den echten Kontext,
kein Duplikat, NO_DUPLICATE_SYSTEMS).
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from controller.cumulative_stress import (
    INDEX_REPORTED,
    NOT_REPORTED,
    REPORTED_ON_INCOMPLETE_BASIS,
    stress_load_report,
)

ROOT = Path(__file__).resolve().parents[1]


def _payload(**overrides):
    base = {
        "domains": [
            {"domain": "soil", "load_raw": 0.7, "basis": "MEASURED"},
            {"domain": "energy", "load_raw": 0.5, "basis": "CALCULATED"},
        ],
        "high_threshold_raw": 0.6,
        "critical_threshold_raw": 0.75,
    }
    base.update(overrides)
    return base


class StressLoadReportTest(unittest.TestCase):
    def test_happy_path_reported_complete(self):
        report = stress_load_report(_payload())
        self.assertEqual(report["state"], INDEX_REPORTED)
        self.assertAlmostEqual(report["cumulative_index_raw"], 0.6)
        self.assertFalse(report["domains_unknown_excluded"])
        self.assertEqual(report["domains_invalid_or_missing"], 0)

    def test_weighted_mean_reuses_caller_weights(self):
        report = stress_load_report(_payload(weights={"soil": 1.5, "energy": 1.0}))
        self.assertAlmostEqual(
            report["cumulative_index_raw"], (1.5 * 0.7 + 1.0 * 0.5) / 2.5
        )

    def test_default_weights_are_equal(self):
        weights_default = stress_load_report(_payload())["weights"]
        self.assertEqual(weights_default, {"soil": 1.0, "energy": 1.0})

    def test_co_stress_counts_high_domains_only(self):
        report = stress_load_report(_payload())
        names = [d["domain"] for d in report["co_stress_domains"]]
        self.assertEqual(names, ["soil"])
        self.assertEqual(report["co_occurrence_note"], "CO_OCCURRENCE != SYNERGIE")

    def test_index_vs_critical_boundary(self):
        below = stress_load_report(_payload())
        self.assertEqual(below["index_vs_critical"], "BELOW")
        above = stress_load_report(_payload(critical_threshold_raw=0.6))
        self.assertEqual(above["index_vs_critical"], "AT_OR_ABOVE")

    def test_unknown_domain_excluded_and_counted(self):
        payload = _payload(
            domains=[
                {"domain": "soil", "load_raw": 0.7, "basis": "MEASURED"},
                {"domain": "food", "basis": "UNKNOWN"},
            ]
        )
        report = stress_load_report(payload)
        self.assertEqual(report["state"], REPORTED_ON_INCOMPLETE_BASIS)
        self.assertEqual(report["domains_unknown_excluded"], ["food"])
        self.assertEqual(report["domains_known"], 1)
        self.assertAlmostEqual(report["known_domain_ratio_raw"], 0.5)
        self.assertAlmostEqual(report["cumulative_index_raw"], 0.7)

    def test_unknown_basis_with_number_rejected(self):
        payload = _payload(
            domains=[
                {"domain": "soil", "load_raw": 0.7, "basis": "MEASURED"},
                {"domain": "food", "load_raw": 0.9, "basis": "UNKNOWN"},
            ]
        )
        report = stress_load_report(payload)
        self.assertEqual(report["state"], NOT_REPORTED)

    def test_invalid_entry_counted_basis_incomplete(self):
        payload = _payload(
            domains=[
                {"domain": "soil", "load_raw": 0.7, "basis": "MEASURED"},
                "kein dict",
                {"domain": "", "load_raw": 0.1, "basis": "MEASURED"},
                {"domain": "x", "load_raw": 0.1, "basis": "FANTASIE"},
            ]
        )
        report = stress_load_report(payload)
        self.assertEqual(report["state"], REPORTED_ON_INCOMPLETE_BASIS)
        self.assertEqual(report["domains_invalid_or_missing"], 3)

    def test_duplicate_domain_rejected(self):
        payload = _payload(
            domains=[
                {"domain": "soil", "load_raw": 0.7, "basis": "MEASURED"},
                {"domain": "soil", "load_raw": 0.9, "basis": "MEASURED"},
            ]
        )
        self.assertEqual(stress_load_report(payload)["state"], NOT_REPORTED)

    def test_bool_load_rejected(self):
        payload = _payload(
            domains=[{"domain": "soil", "load_raw": True, "basis": "MEASURED"}]
        )
        self.assertEqual(stress_load_report(payload)["state"], NOT_REPORTED)

    def test_out_of_range_load_rejected(self):
        payload = _payload(
            domains=[{"domain": "soil", "load_raw": 1.5, "basis": "MEASURED"}]
        )
        self.assertEqual(stress_load_report(payload)["state"], NOT_REPORTED)

    def test_nan_load_rejected(self):
        payload = _payload(
            domains=[
                {"domain": "soil", "load_raw": float("nan"), "basis": "MEASURED"}
            ]
        )
        self.assertEqual(stress_load_report(payload)["state"], NOT_REPORTED)

    def test_unknown_weight_key_rejected(self):
        payload = _payload(weights={"phantom": 1.0})
        self.assertEqual(stress_load_report(payload)["state"], NOT_REPORTED)

    def test_non_positive_weight_rejected(self):
        payload = _payload(weights={"soil": 0.0, "energy": 1.0})
        self.assertEqual(stress_load_report(payload)["state"], NOT_REPORTED)

    def test_all_unknown_no_number(self):
        payload = _payload(domains=[{"domain": "soil", "basis": "UNKNOWN"}])
        report = stress_load_report(payload)
        self.assertEqual(report["state"], NOT_REPORTED)
        self.assertNotIn("cumulative_index_raw", report)

    def test_invalid_threshold_rejected(self):
        payload = _payload(critical_threshold_raw=1.2)
        self.assertEqual(stress_load_report(payload)["state"], NOT_REPORTED)

    def test_non_object_payload_rejected(self):
        self.assertEqual(stress_load_report(["liste"])["state"], NOT_REPORTED)

    def test_index_never_rounded(self):
        payload = _payload(
            domains=[
                {"domain": "a", "load_raw": 0.1, "basis": "MEASURED"},
                {"domain": "b", "load_raw": 0.2, "basis": "MEASURED"},
                {"domain": "c", "load_raw": 0.35, "basis": "MEASURED"},
            ]
        )
        index = stress_load_report(payload)["cumulative_index_raw"]
        self.assertTrue(math.isclose(index, (0.1 + 0.2 + 0.35) / 3.0))

    def test_honesty_limits_present(self):
        for state in (INDEX_REPORTED, NOT_REPORTED):
            payload = (
                _payload()
                if state == INDEX_REPORTED
                else {"domains": []}
            )
            report = stress_load_report(payload)
            self.assertEqual(report["state"], state)
            self.assertTrue(report["honesty_limits"])

    def test_basis_breakdown(self):
        report = stress_load_report(_payload())
        self.assertEqual(report["basis_breakdown"]["MEASURED"], ["soil"])
        self.assertEqual(report["basis_breakdown"]["CALCULATED"], ["energy"])


class CliTest(unittest.TestCase):
    def _run(self, payload_text):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(payload_text)
            path = handle.name
        proc = subprocess.run(
            [sys.executable, str(ROOT / "controller" / "cumulative_stress.py"), path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc

    def test_cli_exit_0_on_reported(self):
        proc = self._run(json.dumps(_payload()))
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["state"], INDEX_REPORTED)

    def test_cli_exit_1_on_not_reported(self):
        proc = self._run(json.dumps({"domains": []}))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["state"], NOT_REPORTED)

    def test_cli_exit_2_on_unreadable_input(self):
        proc = self._run("kein json")
        self.assertEqual(proc.returncode, 2)

    def test_cli_sys_path_regression_no_controller_shadow(self):
        # #460-Lektion: Skriptstart darf 'controller' nicht auf
        # controller/controller.py schatten.
        proc = self._run(json.dumps(_payload()))
        self.assertEqual(proc.returncode, 0)
        self.assertIn(INDEX_REPORTED, proc.stdout)


if __name__ == "__main__":
    unittest.main()
