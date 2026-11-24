"""Fail-closed tests for the read-only V91 emergency supply assessment."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from controller.emergency_supply import (
    DEFAULT_REQUIRED_ITEMS,
    ManifestError,
    SCHEMA_VERSION,
    evaluate_manifest,
    load_manifest,
)

NOW = datetime(2026, 11, 24, 19, 0, tzinfo=timezone.utc)


def _entry(status="available", **overrides):
    value = {
        "status": status,
        "observed_at_utc": "2026-11-24T18:00:00Z",
        "source": "local_inventory_check",
        "evidence_ref": "inventory-record-001",
    }
    value.update(overrides)
    return value


def _manifest(items=None):
    return {
        "schema_version": SCHEMA_VERSION,
        "items": items if items is not None else {
            item: _entry() for item in DEFAULT_REQUIRED_ITEMS
        },
    }


class EmergencySupplyAssessmentTests(unittest.TestCase):
    def test_all_fresh_reports_are_reported_not_verified(self):
        report = evaluate_manifest(_manifest(), now=NOW)
        self.assertEqual(report["overall_status"], "REPORTED_AVAILABLE")
        self.assertEqual(report["reported_available_count"], 4)
        self.assertEqual(report["evidence_class"], "REPORTED_ONLY")
        self.assertEqual(report["independent_verification"], "NOT_PERFORMED")

    def test_missing_item_has_priority_over_unknown(self):
        items = {item: _entry() for item in DEFAULT_REQUIRED_ITEMS}
        items["water"] = _entry("missing")
        items["food"] = {"status": "available"}
        report = evaluate_manifest(_manifest(items), now=NOW)
        self.assertEqual(report["overall_status"], "REPORTED_MISSING")
        self.assertEqual(report["missing_count"], 1)
        self.assertEqual(report["unknown_count"], 1)

    def test_absent_item_is_unknown_not_pass(self):
        report = evaluate_manifest(_manifest({"water": _entry()}), now=NOW)
        self.assertEqual(report["overall_status"], "UNKNOWN")
        self.assertEqual(report["unknown_count"], 3)

    def test_boolean_claim_is_unknown(self):
        items = {item: _entry() for item in DEFAULT_REQUIRED_ITEMS}
        items["water"] = True
        report = evaluate_manifest(_manifest(items), now=NOW)
        self.assertEqual(report["items"][0]["state"], "UNKNOWN")

    def test_missing_provenance_is_unknown(self):
        for field in ("observed_at_utc", "source", "evidence_ref"):
            entry = _entry()
            entry.pop(field)
            items = {item: _entry() for item in DEFAULT_REQUIRED_ITEMS}
            items["water"] = entry
            report = evaluate_manifest(_manifest(items), now=NOW)
            self.assertEqual(report["items"][0]["state"], "UNKNOWN", field)

    def test_naive_timestamp_is_unknown(self):
        items = {item: _entry() for item in DEFAULT_REQUIRED_ITEMS}
        items["water"] = _entry(observed_at_utc="2026-11-24T18:00:00")
        report = evaluate_manifest(_manifest(items), now=NOW)
        self.assertEqual(report["items"][0]["reason"], "provenance_or_timezone_missing")

    def test_stale_observation_is_unknown(self):
        items = {item: _entry() for item in DEFAULT_REQUIRED_ITEMS}
        items["water"] = _entry(observed_at_utc="2026-11-20T18:00:00Z")
        report = evaluate_manifest(_manifest(items), now=NOW)
        self.assertEqual(report["items"][0]["reason"], "observation_stale")

    def test_future_observation_is_unknown(self):
        items = {item: _entry() for item in DEFAULT_REQUIRED_ITEMS}
        items["water"] = _entry(observed_at_utc="2026-11-25T18:00:00Z")
        report = evaluate_manifest(_manifest(items), now=NOW)
        self.assertEqual(report["items"][0]["reason"], "observation_in_future")

    def test_below_minimum_quantity_is_missing(self):
        items = {item: _entry() for item in DEFAULT_REQUIRED_ITEMS}
        items["water"] = _entry(quantity=2, minimum_quantity=5, unit="L")
        report = evaluate_manifest(_manifest(items), now=NOW)
        self.assertEqual(report["items"][0]["state"], "MISSING")

    def test_invalid_quantity_does_not_pass(self):
        for quantity in (True, 10 ** 1000):
            items = {item: _entry() for item in DEFAULT_REQUIRED_ITEMS}
            items["water"] = _entry(quantity=quantity, minimum_quantity=5, unit="L")
            report = evaluate_manifest(_manifest(items), now=NOW)
            self.assertEqual(report["items"][0]["state"], "UNKNOWN")

    def test_unknown_status_does_not_pass(self):
        items = {item: _entry("ready") for item in DEFAULT_REQUIRED_ITEMS}
        report = evaluate_manifest(_manifest(items), now=NOW)
        self.assertEqual(report["overall_status"], "UNKNOWN")

    def test_unsupported_schema_rejected(self):
        with self.assertRaises(ManifestError):
            evaluate_manifest({"schema_version": "other", "items": {}}, now=NOW)

    def test_duplicate_required_items_rejected(self):
        with self.assertRaises(ManifestError):
            evaluate_manifest(_manifest(), ["water", "water"], now=NOW)

    def test_bool_and_excessive_age_rejected(self):
        for age in (True, 31_536_001):
            with self.assertRaises(ManifestError):
                evaluate_manifest(_manifest(), now=NOW, max_age_seconds=age)

    def test_naive_assessment_clock_rejected(self):
        with self.assertRaises(ManifestError):
            evaluate_manifest(_manifest(), now=datetime(2026, 11, 24, 19, 0))

    def test_manifest_size_limit_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text('{"schema_version":"x","schema_version":"y"}', encoding="utf-8")
            with self.assertRaises(ManifestError):
                load_manifest(path)

    def test_manifest_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.json"
            target.write_text(json.dumps(_manifest()), encoding="utf-8")
            link = Path(tmp) / "link.json"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable in this environment")
            with self.assertRaises(ManifestError):
                load_manifest(link)

    def test_evaluation_is_read_only_and_has_no_network_import(self):
        import controller.emergency_supply as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("urllib", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("subprocess", source)
        self.assertEqual(evaluate_manifest(_manifest(), now=NOW)["overall_status"],
                         "REPORTED_AVAILABLE")

    def test_cli_unknown_exit_code_without_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "-m", "controller.emergency_supply",
                 "--manifest", str(Path(tmp) / "missing.json")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["overall_status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
