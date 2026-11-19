"""Tests fuer controller/offline_smoke (Issue #8: Offline-Smoke, Sync optional)."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from controller.offline_smoke import (
    DEFAULT_SYNC_STATUS,
    STATUS_NOT_READY,
    STATUS_PASS,
    STATUS_UNKNOWN,
    HONEST_LIMITS,
    OfflineSmokeError,
    build_smoke_report,
    main,
    smoke_exit_code,
)
from controller.measurement_store import MeasurementStore

NOW = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
KEY = b"x" * 32


def _env(tmpdir, *, stopped=False):
    """Baut eine Smoke-Umgebung: Flag-Datei (nur bei stopped) plus echter Ledger."""
    flag = Path(tmpdir) / "stopped.flag"
    if stopped:
        flag.touch()
    ledger = Path(tmpdir) / "ledger.jsonl"
    store = MeasurementStore(ledger, key=KEY)
    store.record_valid(sensor_id="s1", metric="load", normalized_value=1.0,
                       unit="percent", timestamp_utc="2026-11-20T11:00:00Z",
                       source="offline-smoke-test")
    return str(flag), {"main": str(ledger)}, KEY


class BuildSmokeReportTests(unittest.TestCase):
    def test_pass_with_verified_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, ledgers, key = _env(tmp)
            report = build_smoke_report(
                flag, ledgers, key=key, sync_status="OK", now=NOW)
            self.assertEqual(report["status"], STATUS_PASS)
            self.assertEqual(report["generated_at"], NOW.isoformat())
            self.assertTrue(report["local_checks"]["report_sha256"])

    def test_unknown_when_ledger_path_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, _, key = _env(tmp)
            missing = str(Path(tmp) / "gibt-es-nicht.jsonl")
            report = build_smoke_report(flag, {"main": missing}, key=key, now=NOW)
            self.assertEqual(report["status"], STATUS_UNKNOWN)

    def test_unknown_without_store_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, ledgers, _key = _env(tmp)
            report = build_smoke_report(flag, ledgers, key=None, now=NOW)
            self.assertEqual(report["status"], STATUS_UNKNOWN)

    def test_not_ready_when_stopped(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, ledgers, key = _env(tmp, stopped=True)
            report = build_smoke_report(flag, ledgers, key=key, now=NOW)
            self.assertEqual(report["status"], STATUS_NOT_READY)

    def test_bad_flag_argument_fail_closed(self):
        with self.assertRaises(OfflineSmokeError):
            build_smoke_report("", {}, now=NOW)

    def test_sync_never_gates_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, ledgers, key = _env(tmp)
            for sync in ("OK", "UNAVAILABLE", "DEGRADED", "UNKNOWN"):
                report = build_smoke_report(
                    flag, ledgers, key=key, sync_status=sync, now=NOW)
                self.assertEqual(report["status"], STATUS_PASS)
                self.assertFalse(
                    report["external_sync"]["gates_local_readiness"])

    def test_invalid_sync_status_rejected(self):
        with self.assertRaises(OfflineSmokeError):
            build_smoke_report("flag", sync_status="PASS", now=NOW)

    def test_deterministic_with_fixed_now(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, ledgers, key = _env(tmp)
            first = build_smoke_report(flag, ledgers, key=key,
                                       sync_status="UNKNOWN", now=NOW)
            second = build_smoke_report(flag, ledgers, key=key,
                                        sync_status="UNKNOWN", now=NOW)
            self.assertEqual(first, second)

    def test_bad_now_type_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, ledgers, key = _env(tmp)
            with self.assertRaises(OfflineSmokeError):
                build_smoke_report(flag, ledgers, key=key, now="2026-11-20")

    def test_evidence_references_startup_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, _, key = _env(tmp)
            report = build_smoke_report(flag, {}, key=key, now=NOW)
            for item in report["local_checks"]["evidence"]:
                self.assertEqual(
                    item["evidence_reference"],
                    "controller.startup_check.build_startup_report")

    def test_honest_limits_recorded(self):
        self.assertTrue(HONEST_LIMITS)
        with tempfile.TemporaryDirectory() as tmp:
            flag, _, key = _env(tmp)
            report = build_smoke_report(flag, {}, key=key, now=NOW)
            self.assertEqual(report["honest_limits"], HONEST_LIMITS)


class CliTests(unittest.TestCase):
    def test_cli_without_key_exit_unknown_honest(self):
        # CLI ohne Store-Key (ENV nicht gesetzt) ist ehrlich UNKNOWN, nie PASS
        with tempfile.TemporaryDirectory() as tmp:
            flag, ledgers, _key = _env(tmp)
            rc = main(["--flag-path", flag,
                       "--ledger", f"main={ledgers['main']}",
                       "--sync-status", "UNAVAILABLE"])
            self.assertEqual(rc, 1)

    def test_cli_not_ready_exit_two_on_stopped(self):
        with tempfile.TemporaryDirectory() as tmp:
            flag, ledgers, _key = _env(tmp, stopped=True)
            rc = main(["--flag-path", flag,
                       "--ledger", f"main={ledgers['main']}",
                       "--sync-status", "UNAVAILABLE"])
            self.assertEqual(rc, 2)

    def test_cli_missing_flag_argument_fails(self):
        with self.assertRaises(SystemExit):
            main([])

    def test_cli_exit_codes_map(self):
        self.assertEqual(smoke_exit_code(STATUS_PASS), 0)
        self.assertEqual(smoke_exit_code(STATUS_UNKNOWN), 1)
        self.assertEqual(smoke_exit_code(STATUS_NOT_READY), 2)


class NoNetworkByConstructionTests(unittest.TestCase):
    def test_module_imports_no_network_libraries(self):
        source = Path("controller/offline_smoke.py").read_text(encoding="utf-8")
        for banned in ("import socket", "import urllib", "import requests",
                       "import http", "import ssl"):
            self.assertNotIn(banned, source)

    def test_default_sync_status_is_unknown(self):
        self.assertEqual(DEFAULT_SYNC_STATUS, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
