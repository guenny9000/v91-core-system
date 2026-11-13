"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Tests: deterministic fail-closed provider selection (Issue #239 prep).
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.provider_rotation import (
    HealthSignal,
    ProviderRotationError,
    ProviderRotationManager,
    main,
    resolve_key,
    signals_from_records,
)

KEY = "k" * 32
FIXED_NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def fresh(healthy=True, provider="alpha", offset=0.0):
    return HealthSignal(provider, healthy, iso(FIXED_NOW - timedelta(seconds=offset)), "test_probe")


def manager(providers=("alpha", "beta")):
    return ProviderRotationManager(list(providers), KEY.encode(),
                                   now_provider=lambda: FIXED_NOW)


class ResolveKeyTest(unittest.TestCase):
    def test_no_key_refuses(self):
        with self.assertRaises(ProviderRotationError):
            resolve_key("")

    def test_short_key_refuses(self):
        with self.assertRaises(ProviderRotationError):
            resolve_key("short")


class SignalsTest(unittest.TestCase):
    def test_malformed_records_fail_closed(self):
        with self.assertRaises(ProviderRotationError):
            signals_from_records({"provider": "alpha"})
        with self.assertRaises(ProviderRotationError):
            signals_from_records([{"provider": "alpha", "healthy": "yes", "measured_at": "2026-11-13T12:00:00Z", "source": "x"}])
        with self.assertRaises(ProviderRotationError):
            signals_from_records([{"provider": "alpha", "healthy": True, "measured_at": "not-a-date", "source": "x"}])
        with self.assertRaises(ProviderRotationError):
            signals_from_records([{"provider": "alpha", "healthy": True, "measured_at": "2026-11-13T12:00:00", "source": "x"}])  # naive

    def test_valid_records_parse(self):
        signals = signals_from_records([{"provider": "alpha", "healthy": True,
                                         "measured_at": "2026-11-13T12:00:00Z", "source": "probe"}])
        self.assertEqual(len(signals), 1)
        self.assertTrue(signals[0].healthy)


class SelectionTest(unittest.TestCase):
    def test_selects_first_verified_healthy_deterministically(self):
        result = manager().select_active_provider([fresh(True, "beta"), fresh(True, "alpha")])
        self.assertEqual(result["state"], "VERIFIED")
        self.assertEqual(result["active_provider"], "alpha")
        self.assertEqual(result["health"], {"alpha": "VERIFIED_HEALTHY", "beta": "VERIFIED_HEALTHY"})

    def test_unhealthy_provider_never_selected(self):
        result = manager().select_active_provider([fresh(False, "alpha"), fresh(True, "beta")])
        self.assertEqual(result["active_provider"], "beta")

    def test_stale_signal_is_unknown_not_healthy(self):
        result = manager().select_active_provider([fresh(True, "alpha", offset=3600)])
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIsNone(result["active_provider"])
        self.assertEqual(result["health"]["alpha"], "UNKNOWN")

    def test_future_signal_is_unknown(self):
        future = HealthSignal("alpha", True, iso(FIXED_NOW + timedelta(seconds=60)), "test_probe")
        result = manager().select_active_provider([future])
        self.assertEqual(result["state"], "UNKNOWN")

    def test_no_signals_is_unknown_nothing_selected(self):
        result = manager().select_active_provider([])
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIsNone(result["active_provider"])

    def test_all_unhealthy_is_unknown_fail_closed(self):
        result = manager().select_active_provider([fresh(False, "alpha"), fresh(False, "beta")])
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIsNone(result["active_provider"])

    def test_signal_for_unknown_provider_refused(self):
        with self.assertRaises(ProviderRotationError):
            manager().select_active_provider([fresh(True, "ghost")])

    def test_decision_is_signed_and_verifiable(self):
        result = manager().select_active_provider([fresh(True, "alpha")])
        self.assertTrue(ProviderRotationManager.verify_decision(KEY.encode(), result))
        tampered = {**result, "active_provider": "beta"}
        self.assertFalse(ProviderRotationManager.verify_decision(KEY.encode(), tampered))


class ManagerValidationTest(unittest.TestCase):
    def test_duplicates_empty_and_bad_names_refused(self):
        with self.assertRaises(ProviderRotationError):
            manager(providers=("alpha", "alpha"))
        with self.assertRaises(ProviderRotationError):
            manager(providers=())
        with self.assertRaises(ProviderRotationError):
            manager(providers=("  ",))

    def test_short_manager_key_refused(self):
        with self.assertRaises(ProviderRotationError):
            ProviderRotationManager(["alpha"], b"short")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.health = Path(self.tmp.name) / "health.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write_health(self, healthy: bool) -> None:
        # Relative to the real current time so the freshness window cannot flake.
        measured = datetime.now(timezone.utc) - timedelta(seconds=10)
        self.health.write_text(json.dumps([{
            "provider": "alpha", "healthy": healthy,
            "measured_at": iso(measured), "source": "probe",
        }]), encoding="utf-8")

    def test_cli_verified_exit_zero(self):
        os.environ["V91_MESH_KEY"] = KEY
        try:
            self.write_health(True)
            code = main(["--providers", "alpha", "beta", "--health-json", str(self.health)])
        finally:
            os.environ.pop("V91_MESH_KEY", None)
        self.assertEqual(code, 0)

    def test_cli_without_key_fails_closed(self):
        saved = os.environ.pop("V91_MESH_KEY", None)
        try:
            self.write_health(True)
            self.assertEqual(main(["--providers", "alpha", "beta", "--health-json", str(self.health)]), 2)
        finally:
            if saved is not None:
                os.environ["V91_MESH_KEY"] = saved

    def test_cli_unhealthy_exit_one(self):
        os.environ["V91_MESH_KEY"] = KEY
        try:
            self.write_health(False)
            self.assertEqual(main(["--providers", "alpha", "--health-json", str(self.health)]), 1)
        finally:
            os.environ.pop("V91_MESH_KEY", None)


if __name__ == "__main__":
    unittest.main()
