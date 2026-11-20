"""Tests for controller.node_identity (fail-closed key Autarkie tool).

Generation-dependent tests are skipped where the cryptography package is
unavailable (same honest pattern as quorum ledger tests); all validation,
install/register/rotate and CLI logic runs stdlib-only locally.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.node_identity import (
    NodeIdentityError,
    install_identity,
    new_identity,
    read_public_key,
    register_identity,
    rotate_identity,
)
from controller.peer_directory import PeerDirectory
from v99.security.secret_store import FileSecretStore

try:
    import cryptography  # noqa: F401
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False

K1 = "a" * 64
K2 = "b" * 64
K1U = "A" * 64  # uppercase hex is accepted and normalized to lowercase


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = FileSecretStore(self.tmp.name)
        self.db = os.path.join(self.tmp.name, "dir.sqlite")
        self.directory = PeerDirectory(self.db, now_provider=lambda: 1000)

    def _register(self, peer_id="node-a", key=K1, expires=100000):
        return register_identity(self.directory, peer_id=peer_id,
                                 public_hex=key, expires_at=expires)


class ValidationTests(Base):
    def test_peer_id_rejected_when_empty_or_pathlike(self):
        for bad in ("", "   ", "a/b", "a\\b", ".."):
            with self.assertRaises(NodeIdentityError):
                register_identity(self.directory, peer_id=bad,
                                  public_hex=K1, expires_at=1)

    def test_key_hex_rejected_when_wrong_length_or_non_hex(self):
        for bad in (K1[:-1], K1 + "0", "z" * 64, 12345, None):
            with self.assertRaises(NodeIdentityError):
                register_identity(self.directory, peer_id="node-a",
                                   public_hex=bad, expires_at=1)

    def test_expires_at_rejected_when_not_positive_int(self):
        for bad in (0, -5, True, "123", 1.5):
            with self.assertRaises(NodeIdentityError):
                self._register(expires=bad)

    def test_uppercase_hex_normalized_to_lowercase(self):
        summary = self._register(key=K1U)
        self.assertEqual(summary["public_key_hex"], K1)


class InstallRegisterTests(Base):
    def test_install_stores_private_key_locally_and_reports_public_only(self):
        summary = install_identity(self.store, peer_id="node-a",
                                   private_hex=K1, public_hex=K2)
        self.assertTrue(summary["private_key_stored"])
        self.assertEqual(summary["public_key_hex"], K2)
        self.assertIn("node_identity_node-a_private.secret", os.listdir(self.tmp.name))
        self.assertNotIn(K1, str(summary))  # private key never echoed

    def test_duplicate_registration_refused(self):
        self._register()
        with self.assertRaises(NodeIdentityError):
            self._register()

    def test_read_public_key_requires_registration(self):
        with self.assertRaises(NodeIdentityError):
            read_public_key(self.directory, peer_id="node-a")
        self._register()
        summary = read_public_key(self.directory, peer_id="node-a")
        self.assertEqual(summary["public_key_hex"], K1)
        self.assertTrue(summary["active"])


class RotateTests(Base):
    def test_rotation_archives_old_private_key_and_publishes_new_public(self):
        install_identity(self.store, peer_id="node-a", private_hex=K1, public_hex=K1)
        self._register()
        summary = rotate_identity(self.store, self.directory, peer_id="node-a",
                                  new_public_hex=K2, new_private_hex=K2)
        self.assertTrue(summary["rotated"])
        self.assertEqual(summary["archived_private_key_index"], 0)
        # old key archived, new key active, nothing deleted
        self.assertIn("node_identity_node-a_private.secret",
                      os.listdir(self.tmp.name))
        self.assertIn("node_identity_node-a_private_archive_0000.secret",
                      os.listdir(self.tmp.name))
        self.assertEqual(self.store.read("node_identity_node-a_private"), K2)
        self.assertEqual(
            self.store.read("node_identity_node-a_private_archive_0000"), K1)
        self.assertEqual(self.directory.rotation_count("node-a"), 1)
        self.assertEqual(
            read_public_key(self.directory, peer_id="node-a")["public_key_hex"], K2)

    def test_rotation_refused_without_local_private_key(self):
        self._register()
        with self.assertRaises(NodeIdentityError):
            rotate_identity(self.store, self.directory, peer_id="node-a",
                            new_public_hex=K2, new_private_hex=K2)

    def test_rotation_refused_without_registration(self):
        install_identity(self.store, peer_id="node-a", private_hex=K1, public_hex=K1)
        with self.assertRaises(NodeIdentityError):
            rotate_identity(self.store, self.directory, peer_id="node-a",
                            new_public_hex=K2, new_private_hex=K2)

    def test_two_rotations_use_distinct_archive_names(self):
        install_identity(self.store, peer_id="node-a", private_hex=K1, public_hex=K1)
        self._register()
        rotate_identity(self.store, self.directory, peer_id="node-a",
                        new_public_hex=K2, new_private_hex=K2)
        summary = rotate_identity(self.store, self.directory, peer_id="node-a",
                                  new_public_hex=K1U, new_private_hex=K1)
        self.assertEqual(summary["archived_private_key_index"], 1)
        self.assertIn("node_identity_node-a_private_archive_0001.secret",
                      os.listdir(self.tmp.name))


class CLIAndGenerationTests(Base):
    def _cli(self, *argv):
        repo = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, "-m", "controller.node_identity", *argv],
            cwd=repo, capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)

    def test_cli_register_and_show(self):
        if not HAVE_CRYPTO:
            self.skipTest("cryptography not installed locally (generation is CI-only here)")
        rc, out = self._cli("new", "--peer-id", "node-a", "--store-dir",
                            self.tmp.name, "--directory-db", self.db,
                            "--expires-at", "100000")
        self.assertEqual(rc, 0)
        self.assertTrue(out["ok"])
        self.assertEqual(out["registered"], True)
        self.assertEqual(sorted(out), ["ok", "peer_id", "private_key_stored",
                                      "public_key_hex", "registered"])
        self.assertEqual(out["public_key_hex"], out["public_key_hex"].lower())
        rc, shown = self._cli("show", "--peer-id", "node-a", "--store-dir",
                              self.tmp.name, "--directory-db", self.db)
        self.assertEqual(rc, 0)
        self.assertEqual(shown["public_key_hex"], out["public_key_hex"])
        self.assertTrue(shown["active"])

    def test_cli_show_unknown_peer_fails_closed(self):
        rc, out = self._cli("show", "--peer-id", "ghost", "--store-dir",
                            self.tmp.name, "--directory-db", self.db)
        self.assertEqual(rc, 2)
        self.assertFalse(out["ok"])

    @unittest.skipUnless(HAVE_CRYPTO, "cryptography not installed locally")
    def test_new_identity_returns_distinct_valid_hex_pairs(self):
        priv1, pub1 = new_identity()
        priv2, pub2 = new_identity()
        self.assertNotEqual(priv1, priv2)
        self.assertNotEqual(pub1, pub2)
        for value in (priv1, pub1, priv2, pub2):
            self.assertEqual(len(value), 64)
            int(value, 16)  # valid hex


if __name__ == "__main__":
    unittest.main()
