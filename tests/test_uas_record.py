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


class ValidateRecord113Test(unittest.TestCase):
    """Erweiterung 113.0.0: Herkunft/Autorisierung/Risiko/Rueckweg + Gates."""

    def _record113(self, **overrides):
        base = _record(
            schema_version="113.0.0",
            cycle_stage="EXECUTION",
            origin={
                "actor_id": "peer-model-omega",
                "actor_type": "AGENT",
                "source": "conversation handover text (no repo access)",
            },
            authorization={
                "auth_verified": True,
                "scope": "docs-only review, no repo write",
                "credential_ref": "operator-approved chat session",
                "isolation_policy": "ISOLATE_NOT_DESTROY",
            },
            risk_level="LOW",
        )
        base.update(overrides)
        return base

    def test_v113_full_record_passes(self):
        ok, errors = validate_record(self._record113())
        self.assertTrue(ok, errors)

    def test_v113_input_and_schema_pass_without_authorization(self):
        for stage in ("INPUT", "SCHEMA"):
            ok, errors = validate_record(self._record113(cycle_stage=stage))
            self.assertTrue(ok, errors)

    def test_v113_hypothesis_112_stage_still_passes(self):
        ok, errors = validate_record(self._record113(cycle_stage="HYPOTHESIS"))
        self.assertTrue(ok, errors)

    def test_v113_backward_compatible_without_new_fields(self):
        # LEDGER/COMMIT bleiben gate-geschuetzt; ein 112-artiger Record
        # ohne neue Felder bleibt auf nicht-ausfuehrenden Stufen gueltig.
        ok, errors = validate_record(_record(
            schema_version="113.0.0", cycle_stage="HYPOTHESIS"))
        self.assertTrue(ok, errors)

    def test_v113_ledger_without_authorization_stays_rejected(self):
        ok, errors = validate_record(_record(schema_version="113.0.0"))
        self.assertFalse(ok)
        self.assertTrue(any("KEINE_AUSFUEHRUNG_OHNE_AUTORISIERUNG" in e for e in errors))

    def test_unsupported_schema_version_rejected(self):
        ok, errors = validate_record(_record(schema_version="99.0.0"))
        self.assertFalse(ok)
        self.assertTrue(any("schema_version ungueltig" in e for e in errors))

    def test_invalid_risk_level_rejected(self):
        ok, errors = validate_record(self._record113(risk_level="EXTREME"))
        self.assertFalse(ok)
        self.assertTrue(any("risk_level" in e for e in errors))

    def test_high_risk_requires_recovery_path(self):
        ok, errors = validate_record(self._record113(risk_level="HIGH"))
        self.assertFalse(ok)
        self.assertTrue(any("RECOVERY_FIRST" in e for e in errors))

    def test_high_risk_without_available_rollback_rejected(self):
        ok, errors = validate_record(self._record113(
            risk_level="HIGH",
            rollback={"available": False, "procedure": "n/a"},
        ))
        self.assertFalse(ok)
        self.assertTrue(any("RECOVERY_FIRST" in e for e in errors))

    def test_high_risk_with_valid_rollback_passes(self):
        ok, errors = validate_record(self._record113(
            risk_level="HIGH",
            rollback={"available": True, "procedure": "branch revert, merge rueckgaengig"},
        ))
        self.assertTrue(ok, errors)

    def test_execution_without_authorization_rejected(self):
        rec = self._record113()
        del rec["authorization"]
        ok, errors = validate_record(rec)
        self.assertFalse(ok)
        self.assertTrue(any("KEINE_AUSFUEHRUNG_OHNE_AUTORISIERUNG" in e for e in errors))

    def test_execution_with_unverified_authorization_rejected(self):
        ok, errors = validate_record(self._record113(
            authorization={"auth_verified": False, "scope": "none", "credential_ref": "x"},
        ))
        self.assertFalse(ok)
        self.assertTrue(any("SYNTAX_ERTEILT_KEINE_BERECHTIGUNG" in e for e in errors))

    def test_commit_requires_ci_pass(self):
        ok, errors = validate_record(self._record113(
            cycle_stage="COMMIT",
            ci_checks={"overall_status": "UNKNOWN", "checks": []},
        ))
        self.assertFalse(ok)
        self.assertTrue(any("EVIDENCE_BEFORE_COMMITMENT" in e for e in errors))

    def test_commit_requires_nonempty_evidence(self):
        ok, errors = validate_record(self._record113(
            cycle_stage="COMMIT", evidence=[]))
        self.assertFalse(ok)
        self.assertTrue(any("evidence-Eintrag" in e for e in errors))

    def test_origin_bad_actor_type_rejected(self):
        rec = self._record113()
        rec["origin"]["actor_type"] = "ROBOT_OVERLORD"
        ok, errors = validate_record(rec)
        self.assertFalse(ok)
        self.assertTrue(any("actor_type" in e for e in errors))

    def test_rollback_unknown_field_rejected(self):
        ok, errors = validate_record(self._record113(
            risk_level="HIGH",
            rollback={"available": True, "procedure": "revert merge", "phantom": "x"},
        ))
        self.assertFalse(ok)
        self.assertTrue(any("rollback" in e for e in errors))

    def test_112_still_rejects_new_fields(self):
        ok, errors = validate_record(_record(risk_level="LOW"))
        self.assertFalse(ok)
        self.assertTrue(any("unbekannte Felder" in e for e in errors))
