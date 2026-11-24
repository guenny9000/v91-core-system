"""Tests fuer controller.uas_record (V91CycleActionSchema 112.0.0).

Integrationstest gegen das ECHTE importierbare controller-Paket
(NO_DUPLICATE_SYSTEMS). Der Validierer ist stdlib-only.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from controller.uas_record import (
    ALLOWED_DRIFT_STATUS,
    HONESTY_LIMITS,
    SCHEMA_VERSION,
    batch_report,
    validate_record,
)

ROOT = Path(__file__).resolve().parents[1]


def _record(**overrides):
    base = {
        "schema_version": SCHEMA_VERSION,
        "action_id": "BLK-TEST-01",
        "cycle_stage": "LEDGER",
        "hypothesis": "Schema-vertragliche Uebergaben reduzieren stille Annahmen.",
        "pr_and_vibe": {
            "pr_ref": "guenny9000/v91-core-system#480",
            "vibe_mark": "VIBE-LXXXCXLVI",
            "commit_sha": "ea098e3",
            "next_free_vibe_mark": "LXXXCXLVII",
        },
        "ci_checks": {
            "overall_status": "PASS",
            "head_sha": "f451efe",
            "checks": [
                {"name": "audit-checks", "status": "PASS"},
                {"name": "disarmament-tests", "status": "PASS", "details": "success via check-runs API"},
            ],
        },
        "drift": {
            "status": "NONE",
            "observed_count": 0,
            "threshold": 3,
            "affected_targets": [],
        },
        "follow_up_checks": [
            {
                "check_id": "OPS-239",
                "description": "Credential-Rotation",
                "status": "OPEN",
                "owner": "Betreiber",
            }
        ],
        "evidence": ["Merge ea098e3, CI 2/2 am Head f451efe"],
        "unknowns": ["Laufzeit-Metriken nach dem Merge"],
    }
    base.update(overrides)
    return base


class ValidateRecordTest(unittest.TestCase):
    def test_valid_record_passes(self):
        ok, errors = validate_record(_record())
        self.assertTrue(ok, errors)

    def test_missing_required_field_rejected(self):
        rec = _record()
        del rec["drift"]
        ok, errors = validate_record(rec)
        self.assertFalse(ok)
        self.assertTrue(any("Pflichtfeld" in e for e in errors))

    def test_unknown_top_level_field_rejected(self):
        ok, errors = validate_record(_record(phantom_feld="x"))
        self.assertFalse(ok)
        self.assertTrue(any("unbekannte Felder" in e for e in errors))

    def test_invalid_cycle_stage_rejected(self):
        ok, _ = validate_record(_record(cycle_stage="HARMONIE"))
        self.assertFalse(ok)

    def test_invalid_ci_overall_rejected(self):
        ci = _record()["ci_checks"].copy()
        ci["overall_status"] = "OPTIMAL"
        ok, _ = validate_record(_record(ci_checks=ci))
        self.assertFalse(ok)

    def test_invalid_check_status_rejected(self):
        ci = _record()["ci_checks"].copy()
        ci["checks"] = [{"name": "x", "status": "GRUEN"}]
        ok, _ = validate_record(_record(ci_checks=ci))
        self.assertFalse(ok)

    def test_bool_observed_count_rejected(self):
        drift = _record()["drift"].copy()
        drift["observed_count"] = True
        ok, _ = validate_record(_record(drift=drift))
        self.assertFalse(ok)

    def test_invalid_drift_threshold_rejected(self):
        drift = _record()["drift"].copy()
        drift["threshold"] = 0
        ok, _ = validate_record(_record(drift=drift))
        self.assertFalse(ok)

    def test_invalid_drift_status_rejected(self):
        drift = _record()["drift"].copy()
        drift["status"] = "GELOESCHT"
        ok, _ = validate_record(_record(drift=drift))
        self.assertFalse(ok)

    def test_missing_pr_and_vibe_fields_rejected(self):
        ok, _ = validate_record(_record(pr_and_vibe={"pr_ref": "x"}))
        self.assertFalse(ok)

    def test_unknown_pr_and_vibe_field_rejected(self):
        prv = _record()["pr_and_vibe"].copy()
        prv["harmonie"] = "100%"
        ok, _ = validate_record(_record(pr_and_vibe=prv))
        self.assertFalse(ok)

    def test_follow_up_unknown_status_rejected(self):
        fups = [{"check_id": "x", "description": "y", "status": "ERLEDIGT_SUPER"}]
        ok, _ = validate_record(_record(follow_up_checks=fups))
        self.assertFalse(ok)

    def test_empty_evidence_entry_rejected(self):
        ok, _ = validate_record(_record(evidence=[""]))
        self.assertFalse(ok)

    def test_empty_evidence_list_allowed_but_unproven(self):
        ok, _ = validate_record(_record(evidence=[]))
        self.assertTrue(ok)

    def test_non_object_root_rejected(self):
        ok, _ = validate_record(["liste"])
        self.assertFalse(ok)

    def test_honesty_limits_content(self):
        self.assertIn("SCHEMA_KONFORM != WAHR", HONESTY_LIMITS)
        self.assertIn("STATUSZEILE != EVIDENZ", HONESTY_LIMITS)

    def test_all_drift_states_defined(self):
        self.assertEqual(set(ALLOWED_DRIFT_STATUS), {"NONE", "DETECTED", "ISOLATED", "UNKNOWN"})


class BatchReportTest(unittest.TestCase):
    def test_batch_over_directory_json_and_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.json").write_text(json.dumps(_record()), encoding="utf-8")
            with open(tmp_path / "b.jsonl", "w", encoding="utf-8") as handle:
                handle.write(json.dumps(_record(action_id="B-1")) + "\n")
                handle.write("\n")  # Leerzeile wird uebersprungen
                handle.write(json.dumps(_record(action_id="B-2")) + "\n")
            code, report = batch_report(tmp_path)
            self.assertEqual(code, 0)
            self.assertEqual(report["files_scanned"], 2)
            self.assertEqual(report["records_total"], 3)
            self.assertEqual(report["records_valid"], 3)
            self.assertEqual(report["records_invalid"], 0)
            self.assertEqual(len(report["open_follow_ups"]), 3)
            self.assertEqual(report["drift_counts"]["NONE"], 3)

    def test_batch_counts_invalid_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad = _record()
            bad["cycle_stage"] = "HARMONIE"
            (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
            (tmp_path / "broken.json").write_text("kein json", encoding="utf-8")
            code, report = batch_report(tmp_path)
            self.assertEqual(code, 1)
            self.assertEqual(report["records_invalid"], 2)
            self.assertTrue(report["validation_errors"])

    def test_batch_empty_target_exit_2(self):
        code, report = batch_report(Path("/nicht/vorhanden/xyz"))
        self.assertEqual(code, 2)
        self.assertEqual(report["files_scanned"], 0)

    def test_batch_drift_event_collected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            drift = {"status": "DETECTED", "observed_count": 2, "threshold": 3, "affected_targets": ["mesh"]}
            (tmp_path / "d.json").write_text(json.dumps(_record(drift=drift)), encoding="utf-8")
            code, report = batch_report(tmp_path)
            self.assertEqual(code, 0)
            self.assertEqual(report["drift_counts"]["DETECTED"], 1)
            self.assertEqual(len(report["drift_events"]), 1)
            self.assertEqual(report["drift_events"][0]["affected_targets"], ["mesh"])


class CliTest(unittest.TestCase):
    def _run(self, args):
        return subprocess.run(
            [sys.executable, str(ROOT / "controller" / "uas_record.py")] + args,
            capture_output=True, text=True, timeout=120,
        )

    def test_cli_exit_0_and_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.json"
            path.write_text(json.dumps(_record()), encoding="utf-8")
            proc = self._run([str(path)])
            self.assertEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertEqual(data["records_valid"], 1)
            self.assertTrue(data["honesty_limits"])

    def test_cli_exit_1_on_invalid_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.json"
            path.write_text(json.dumps(_record(cycle_stage="FANTASIE")), encoding="utf-8")
            proc = self._run([str(path)])
            self.assertEqual(proc.returncode, 1)

    def test_cli_exit_2_on_missing_target(self):
        proc = self._run(["/nicht/vorhanden"])
        self.assertEqual(proc.returncode, 2)

    def test_cli_sys_path_regression_no_controller_shadow(self):
        # #460-Lektion: Skriptstart darf 'controller' nicht schatten.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.json"
            path.write_text(json.dumps(_record()), encoding="utf-8")
            proc = self._run([str(path)])
            self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
