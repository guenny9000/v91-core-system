"""
Tests fuer controller/uas_contract (UAS-Vertragskanon, Issue #484).

Der Kanon darf nur abbilden, was der Validator wirklich tut. Diese
Tests sichern die Ableitung (KEINE zweite Wahrheit), die Sonden
(fail-closed gegen echte validate_record-Lauefe) und die
Autorisierungstrennung. ANZAHL_SONDE != ABDECKUNG bleibt ehrlich.
"""
from __future__ import annotations

import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from controller import uas_contract as uc
from controller import uas_record as ur


class ContractDerivationTest(unittest.TestCase):
    """Der Kanon ist Ableitung, keine Erstfindung (NO_DUPLICATE_SYSTEMS)."""

    def test_single_source_is_validator(self):
        contract = uc.build_contract()
        self.assertEqual(contract["single_source_of_truth"],
                         "controller/uas_record.py")

    def test_versions_match_validator(self):
        self.assertEqual(uc.build_contract()["supported_schema_versions"],
                         list(ur.SUPPORTED_SCHEMA_VERSIONS))
        self.assertIn("112.0.0", uc.build_contract()["supported_schema_versions"])
        self.assertIn("113.0.0", uc.build_contract()["supported_schema_versions"])

    def test_required_fields_match_validator(self):
        self.assertEqual(uc.build_contract()["required_top_level_fields"],
                         list(ur._REQUIRED_TOP))

    def test_stages_match_validator(self):
        contract = uc.build_contract()
        for stage in ur.ALLOWED_STAGES:
            self.assertIn(stage, contract["stages"]["112.0.0"])
            self.assertIn(stage, contract["stages"]["113.0.0"])
        for stage in ur.V113_EXTRA_STAGES:
            self.assertNotIn(stage, contract["stages"]["112.0.0"])
            self.assertIn(stage, contract["stages"]["113.0.0"])

    def test_enums_match_validator(self):
        enums = uc.build_contract()["enums"]
        self.assertEqual(enums["risk_levels"], list(ur.ALLOWED_RISK_LEVELS))
        self.assertEqual(enums["ci_overall_status"], list(ur.ALLOWED_CI_OVERALL))
        self.assertEqual(enums["follow_up_status"], list(ur.ALLOWED_FOLLOW_UP_STATUS))

    def test_reject_unknown_fields_documented(self):
        self.assertTrue(uc.build_contract()["additional_unknown_fields_rejected"])

    def test_honesty_limits_from_validator(self):
        limits = uc.build_contract()["honesty_limits"]
        self.assertIn(ur.HONESTY_LIMITS, limits)
        self.assertIn("UNKNOWN != PASS", limits)

    def test_not_verified_declared(self):
        not_verified = uc.build_contract()["not_verified"]
        for item in ("adapter_ende_zu_ende", "iacl_transport",
                     "ledger_schreibpfad", "dauerbetrieb"):
            self.assertIn(item, not_verified)

    def test_authorization_separation_declared(self):
        sep = uc.build_contract()["authorization_separation"]
        self.assertIn("AUFRUFER-ANGABE", sep)
        self.assertIn("ANGABE != BERECHTIGUNG", sep)


class ProbeTest(unittest.TestCase):
    """Sonden pruefen echtes Validator-Verhalten, nicht Behauptungen."""

    def test_all_probes_pass(self):
        results = uc.run_probes()
        self.assertEqual(len(results), 10)
        failed = [r for r in results if not r["passed"]]
        self.assertEqual(failed, [])

    def test_probe_failure_is_reported_not_hidden(self):
        with mock.patch.object(ur, "validate_record",
                               return_value=(True, [])):
            results = uc.run_probes()
        failed = [r for r in results if not r["passed"]]
        self.assertNotEqual(failed, [])

    def test_probe_exception_counts_as_failure(self):
        def _boom(_data):
            raise RuntimeError("PRUEFFEHLER")
        with mock.patch.object(ur, "validate_record", side_effect=_boom):
            results = uc.run_probes()
        failed = [r for r in results if not r["passed"]]
        # 8 Sonden laufen durch validate_record und schlagen fehl;
        # die 2 Kanon-Ableitungssonen benutzen den Mock nicht.
        self.assertEqual(len(failed), 8)
        passed = {r["probe"] for r in results if r["passed"]}
        self.assertIn("kanon_versionen_gleich_validator", passed)
        self.assertIn("PRUEFFEHLER", str(failed[0].get("error", "")))

    def test_compatibility_probe_semantics(self):
        ok112, _ = ur.validate_record(uc._min_record(
            schema_version=ur.SCHEMA_VERSION))
        self.assertTrue(ok112)
        bad112, _ = ur.validate_record(uc._min_record(
            schema_version=ur.SCHEMA_VERSION, risk_level="LOW"))
        self.assertFalse(bad112)  # VORWAERTS_STRENG


class CliTest(unittest.TestCase):
    """CLI: Kanon ausgeben (0), Sonden (--check), exit fail-closed (1)."""

    def test_plain_output_is_valid_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = uc.main([])
        self.assertEqual(exit_code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["contract_name"], "V91CycleActionSchema-Kanon")

    def test_check_exit_zero_when_consistent(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = uc.main(["--check"])
        self.assertEqual(exit_code, 0)
        report = json.loads(buf.getvalue())
        self.assertEqual(report["status"], "KANON_KONSISTENT")
        self.assertEqual(report["probes_failed"], 0)

    def test_check_exit_one_on_divergence(self):
        def _always_pass(_data):
            return True, []
        with mock.patch.object(ur, "validate_record",
                               side_effect=_always_pass):
            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = uc.main(["--check"])
        self.assertEqual(exit_code, 1)
        report = json.loads(buf.getvalue())
        self.assertEqual(report["status"], "KANON_ABWEICHUNG")

    def test_out_file_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "kanon.json"
            self.assertEqual(uc.main(["--out", str(out)]), 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("stages", data)


if __name__ == "__main__":
    unittest.main()
