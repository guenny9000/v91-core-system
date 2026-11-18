#!/usr/bin/env python3
"""Tests for ledger backup and recovery (Issue #100 recovery part)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from controller.ledger_recovery import LedgerRecovery, LedgerRecoveryError
from controller.measurement_store import MeasurementStore

KEY = b"0123456789abcdef0123456789abcdef"  # 32 bytes, test-only


class LedgerRecoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.ledger = self.root / "store.jsonl"
        self.store = MeasurementStore(self.ledger, key=KEY)
        self.store.record_valid(sensor_id="s1", metric="m", normalized_value=1.0,
                               unit="u", timestamp_utc="2026-11-19T10:00:00Z")
        self.store.quarantine({"sensor_id": "s2", "value": None}, reason="REJECTED: none")
        self.recovery = LedgerRecovery(KEY)

    def test_backup_creates_manifest_with_verification_status(self) -> None:
        report = self.recovery.create_backup(self.ledger, self.root / "backup.jsonl")
        self.assertTrue(report.source_chain_verified)
        self.assertEqual(report.record_count, 2)
        manifest = json.loads((self.root / "backup.jsonl.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "V91_MEASUREMENT_LEDGER_BACKUP")
        self.assertEqual(manifest["sha256"], report.sha256)

    def test_verify_backup_uses_real_chain_verification(self) -> None:
        self.recovery.create_backup(self.ledger, self.root / "backup.jsonl")
        self.assertTrue(self.recovery.verify_backup(self.root / "backup.jsonl"))

    def test_tampered_backup_is_not_verified(self) -> None:
        self.recovery.create_backup(self.ledger, self.root / "backup.jsonl")
        lines = (self.root / "backup.jsonl").read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["normalized_value"] = 999.0
        lines[0] = json.dumps(tampered, sort_keys=True, ensure_ascii=False)
        (self.root / "backup.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertFalse(self.recovery.verify_backup(self.root / "backup.jsonl"))

    def test_restore_refuses_unverified_backup(self) -> None:
        self.recovery.create_backup(self.ledger, self.root / "backup.jsonl")
        lines = (self.root / "backup.jsonl").read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["normalized_value"] = 999.0
        lines[0] = json.dumps(tampered, sort_keys=True, ensure_ascii=False)
        (self.root / "backup.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaises(LedgerRecoveryError):
            self.recovery.restore(self.ledger, self.root / "backup.jsonl", self.root / "quarantine")

    def test_restore_quarantines_corrupted_original_instead_of_deleting(self) -> None:
        self.recovery.create_backup(self.ledger, self.root / "backup.jsonl")
        # Corrupt the live ledger (truncated garbage tail)
        with open(self.ledger, "a", encoding="utf-8") as handle:
            handle.write("{torn")
        report = self.recovery.restore(self.ledger, self.root / "backup.jsonl", self.root / "quarantine")
        self.assertTrue(report.post_restore_verified)
        self.assertEqual(report.records_restored, 2)
        self.assertTrue(report.quarantined_previous.exists())
        self.assertIn("{torn", report.quarantined_previous.read_text(encoding="utf-8"))
        # Live ledger is healthy again
        self.assertTrue(MeasurementStore(self.ledger, key=KEY).verify_chain())

    def test_backup_refuses_overwrite_and_missing_source(self) -> None:
        with self.assertRaises(LedgerRecoveryError):
            self.recovery.create_backup(self.root / "does-not-exist.jsonl", self.root / "b.jsonl")
        self.recovery.create_backup(self.ledger, self.root / "b.jsonl")
        with self.assertRaises(LedgerRecoveryError):
            self.recovery.create_backup(self.ledger, self.root / "b.jsonl")

    def test_fail_closed_on_bad_key(self) -> None:
        with self.assertRaises(LedgerRecoveryError):
            LedgerRecovery(b"short")


if __name__ == "__main__":
    unittest.main()
