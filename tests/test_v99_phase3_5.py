"""V99 Phase-3/5-Regressionstests (Reality-First, nur stdlib)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v99.recovery.integrity import file_sha256, verify_file
from v99.recovery.backup import create_backup, restore_backup
from v99.security.secret_store import (
    FileSecretStore, InMemorySecretStore, SecretStoreError,
)


class TestInMemorySecretStore(unittest.TestCase):
    def test_store_activate_read(self):
        store = InMemorySecretStore()
        store.store("api_token", "s" * 40)
        self.assertTrue(store.activate("api_token"))
        self.assertEqual(store.read("api_token"), "s" * 40)

    def test_activate_missing_secret_fails_closed(self):
        store = InMemorySecretStore()
        self.assertFalse(store.activate("gibts_nicht"))

    def test_empty_secret_rejected(self):
        store = InMemorySecretStore()
        with self.assertRaises(SecretStoreError):
            store.store("x", "")

    def test_empty_name_rejected(self):
        store = InMemorySecretStore()
        with self.assertRaises(SecretStoreError):
            store.store("  ", "value")

    def test_read_missing_raises_without_leaking(self):
        store = InMemorySecretStore()
        with self.assertRaises(SecretStoreError) as ctx:
            store.read("gibts_nicht")
        self.assertNotIn("value", str(ctx.exception))


class TestFileSecretStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = FileSecretStore(self.tmp)

    def test_roundtrip(self):
        self.store.store("api_token", "t" * 48)
        self.assertTrue(self.store.activate("api_token"))
        self.assertEqual(self.store.read("api_token"), "t" * 48)

    def test_missing_secret_fails_closed(self):
        self.assertFalse(self.store.activate("gibts_nicht"))
        with self.assertRaises(SecretStoreError):
            self.store.read("gibts_nicht")

    def test_posix_permissions_restricted(self):
        self.store.store("api_token", "t" * 48)
        if os.name != "posix":
            return  # Windows kennt keine Posix-Modusbits – dokumentiert
        mode = os.stat(os.path.join(self.tmp, "api_token.secret")).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_path_traversal_rejected(self):
        with self.assertRaises(SecretStoreError):
            self.store.store("../boese", "value")


class TestBackupRestore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.source = os.path.join(self.tmp, "ledger.jsonl")
        with open(self.source, "w", encoding="utf-8") as handle:
            handle.write('{"index":0,"hash":"a"}\n{"index":1,"hash":"b"}\n')
        self.backup_dir = os.path.join(self.tmp, "backups")
        self.dest = os.path.join(self.tmp, "restored.jsonl")

    def test_backup_creates_verifiable_copy(self):
        result = create_backup(self.source, self.backup_dir)
        self.assertTrue(result.sha256)
        self.assertTrue(verify_file(result.backup_path, result.sha256))

    def test_existing_backup_not_overwritten(self):
        first = create_backup(self.source, self.backup_dir)
        with open(self.source, "a", encoding="utf-8") as handle:
            handle.write('{"index":2,"hash":"c"}\n')
        second = create_backup(self.source, self.backup_dir)
        self.assertNotEqual(first.backup_path, second.backup_path)

    def test_restore_verified(self):
        result = create_backup(self.source, self.backup_dir)
        ok = restore_backup(result.backup_path, self.dest, result.sha256)
        self.assertTrue(ok)
        self.assertEqual(file_sha256(self.dest), result.sha256)

    def test_restore_tampered_backup_refused(self):
        result = create_backup(self.source, self.backup_dir)
        with open(result.backup_path, "a", encoding="utf-8") as handle:
            handle.write("MANIPULATION")
        self.assertFalse(restore_backup(result.backup_path, self.dest, result.sha256))
        self.assertFalse(os.path.exists(self.dest))

    def test_restore_over_existing_needs_explicit_allow(self):
        result = create_backup(self.source, self.backup_dir)
        with self.assertRaises(FileExistsError):
            restore_backup(result.backup_path, self.source, result.sha256)
        self.assertTrue(
            restore_backup(result.backup_path, self.source, result.sha256,
                           allow_overwrite=True)
        )

    def test_bad_hash_format_rejected(self):
        result = create_backup(self.source, self.backup_dir)
        self.assertFalse(restore_backup(result.backup_path, self.dest, "kurz"))


if __name__ == "__main__":
    unittest.main()
