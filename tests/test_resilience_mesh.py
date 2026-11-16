"""Tests: resilience mesh verify-only module."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.resilience_mesh import (
    MeshRegister,
    ResilienceMeshError,
    RestartVerifier,
    main,
    resolve_key,
    verify_local_units,
)

KEY = "k" * 32


class ResolveKeyTest(unittest.TestCase):
    def test_explicit_key_ok(self):
        self.assertEqual(resolve_key(KEY), KEY.encode())

    def test_no_key_refuses(self):
        with self.assertRaises(ResilienceMeshError):
            resolve_key("")

    def test_short_key_refuses(self):
        with self.assertRaises(ResilienceMeshError):
            resolve_key("too-short")


class MeshRegisterTest(unittest.TestCase):
    def setUp(self):
        self.register = MeshRegister(KEY.encode())

    def test_register_and_verify(self):
        entry = self.register.register_peer("node-a", "local://node-a")
        self.assertTrue(self.register.verify_peer(entry))
        self.assertEqual(len(self.register.peers()), 1)

    def test_tampered_entry_rejected(self):
        entry = self.register.register_peer("node-a", "local://node-a")
        entry["endpoint"] = "local://evil"
        self.assertFalse(self.register.verify_peer(entry))

    def test_wrong_key_register_rejects(self):
        entry = self.register.register_peer("node-a", "local://node-a")
        other = MeshRegister(("x" * 32).encode())
        self.assertFalse(other.verify_peer(entry))

    def test_empty_node_id_refused(self):
        with self.assertRaises(ResilienceMeshError):
            self.register.register_peer("  ", "local://x")

    def test_short_register_key_refused(self):
        with self.assertRaises(ResilienceMeshError):
            MeshRegister(b"short")


def ok_runner(command):
    return 0, "active\n", ""


def inactive_runner(command):
    return 3, "", "inactive"


def broken_runner(command):
    raise OSError("runner down")


class RestartVerifierTest(unittest.TestCase):
    def test_verified_active(self):
        result = RestartVerifier(ok_runner, "linux").verify("v91-cycle.service")
        self.assertEqual(result["status"], "VERIFIED_ACTIVE")
        self.assertEqual(result["command"][:2], ["systemctl", "is-active"])

    def test_not_active(self):
        result = RestartVerifier(inactive_runner, "linux").verify("v91-cycle.timer")
        self.assertEqual(result["status"], "NOT_ACTIVE")

    def test_systemd_error_exit_is_unknown(self):
        runner = lambda command: (1, "", "systemctl failed")
        result = RestartVerifier(runner, "linux").verify("v91-cycle.service")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_missing_systemd_unit_is_unknown(self):
        runner = lambda command: (4, "unknown", "Unit not found")
        result = RestartVerifier(runner, "linux").verify("v91-cycle.service")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_non_linux_nonzero_exit_is_unknown(self):
        result = RestartVerifier(inactive_runner, "darwin").verify("com.v91.cycle")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_runner_failure_is_unknown(self):
        result = RestartVerifier(broken_runner, "linux").verify("v91-cycle.service")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIn("runner failed", result["reason"])

    def test_unknown_unit_refused(self):
        with self.assertRaises(ResilienceMeshError):
            RestartVerifier(ok_runner, "linux").verify("nope.service")

    def test_unsupported_platform_refused(self):
        with self.assertRaises(ResilienceMeshError):
            RestartVerifier(ok_runner, "plan9")


class VerifyLocalUnitsTest(unittest.TestCase):
    def test_all_units_verified(self):
        result = verify_local_units(ok_runner, "linux")
        self.assertEqual([u["status"] for u in result["units"]], ["VERIFIED_ACTIVE", "VERIFIED_ACTIVE"])

    def test_unknown_unit_fails_closed(self):
        with self.assertRaises(ResilienceMeshError):
            verify_local_units(ok_runner, "linux", units=["ghost"])


class CliTest(unittest.TestCase):
    def test_cli_without_key_fails_closed(self):
        import os
        saved = os.environ.pop("V91_MESH_KEY", None)
        try:
            self.assertEqual(main(["--platform", "linux"]), 2)
        finally:
            if saved is not None:
                os.environ["V91_MESH_KEY"] = saved

    def test_cli_with_key_exit_zero(self):
        import os
        os.environ["V91_MESH_KEY"] = KEY
        try:
            self.assertEqual(main(["--platform", "linux"]), 0)
        finally:
            os.environ.pop("V91_MESH_KEY", None)


if __name__ == "__main__":
    unittest.main()
