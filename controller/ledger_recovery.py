#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Ledger backup and recovery drill for the measurement store
(Issue #100, recovery part).

Fail-closed backup/restore for the HMAC-chained JSONL ledger:
- create_backup: verifies the source chain first (a corrupt source is
  reported, not silently copied as if healthy), copies atomically
  (temp file + fsync + rename) and writes a manifest with sha256,
  record count and verification status
- verify_backup: full chain verification of the backup with the real
  MeasurementStore logic (evidence, not claim)
- restore: ONLY from a chain-verified backup. The current source file
  is moved to a quarantine location, NEVER deleted
  (ISOLATE_NOT_DESTROY). The restored file is re-verified after the
  swap; a failed re-verification raises (fail-closed).

Honest limits: no scheduling, no daemon, no remote copies, no
encryption of backups (caller's responsibility), no partial-tail
repair (a torn last record is preserved for forensics, not trimmed);
DRILL != DEPLOYED: this module proves the mechanics in tests, not
that a production host has working backups.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from controller.measurement_store import MeasurementStore, MeasurementStoreError


class LedgerRecoveryError(Exception):
    """Fail-closed recovery error."""


@dataclass(frozen=True)
class BackupReport:
    backup_path: Path
    sha256: str
    record_count: int
    source_chain_verified: bool


@dataclass(frozen=True)
class RestoreReport:
    restored_path: Path
    quarantined_previous: Path
    records_restored: int
    post_restore_verified: bool


class LedgerRecovery:
    """Backup and restore for a MeasurementStore JSONL ledger."""

    def __init__(self, key: bytes) -> None:
        if not isinstance(key, bytes) or len(key) < 32:
            raise LedgerRecoveryError("key must be bytes of at least 32 bytes")
        self._key = key

    # -- backup ---------------------------------------------------------

    def create_backup(self, source: Path | str, backup_path: Path | str) -> BackupReport:
        source = Path(source)
        backup_path = Path(backup_path)
        if not source.exists():
            raise LedgerRecoveryError(f"source ledger not found: {source}")
        if backup_path.exists():
            raise LedgerRecoveryError(
                f"backup target already exists; refusing to overwrite: {backup_path}")

        store = MeasurementStore(source, key=self._key)
        try:
            chain_ok = store.verify_chain()
            count = store.count()
        except MeasurementStoreError as exc:
            raise LedgerRecoveryError(f"source ledger unreadable: {exc}") from exc
        if not chain_ok:
            # Copy for forensics is allowed, but the report must say so;
            # restore will refuse this backup.
            chain_ok = False

        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        tmp = backup_path.with_name(backup_path.name + ".tmp")
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, backup_path)

        manifest = {
            "kind": "V91_MEASUREMENT_LEDGER_BACKUP",
            "sha256": digest,
            "record_count": count,
            "source_chain_verified_at_backup": chain_ok,
            "source": str(source),
        }
        manifest_path = backup_path.with_name(backup_path.name + ".manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, sort_keys=True, ensure_ascii=False, indent=1)
            handle.write("\n")
        return BackupReport(backup_path=backup_path, sha256=digest,
                            record_count=count, source_chain_verified=chain_ok)

    # -- verification ----------------------------------------------------

    def verify_backup(self, backup_path: Path | str) -> bool:
        backup_path = Path(backup_path)
        if not backup_path.exists():
            raise LedgerRecoveryError(f"backup not found: {backup_path}")
        store = MeasurementStore(backup_path, key=self._key)
        try:
            return store.verify_chain()
        except MeasurementStoreError as exc:
            raise LedgerRecoveryError(f"backup unreadable: {exc}") from exc

    # -- restore ----------------------------------------------------------

    def restore(self, source: Path | str, backup_path: Path | str,
                quarantine_dir: Path | str) -> RestoreReport:
        source = Path(source)
        backup_path = Path(backup_path)
        quarantine_dir = Path(quarantine_dir)
        if not backup_path.exists():
            raise LedgerRecoveryError(f"backup not found: {backup_path}")
        if not self.verify_backup(backup_path):
            raise LedgerRecoveryError(
                "backup chain is NOT verified; restore refused (FAIL-CLOSED)")

        quarantine_dir.mkdir(parents=True, exist_ok=True)
        suffix = 0
        quarantined = quarantine_dir / (source.name + ".quarantined-0")
        while quarantined.exists():
            suffix += 1
            quarantined = quarantine_dir / (f"{source.name}.quarantined-{suffix}")
        if source.exists():
            shutil.move(str(source), str(quarantined))
        else:
            quarantined = quarantine_dir / (source.name + ".quarantined-missing-source")

        data = backup_path.read_bytes()
        tmp = source.with_name(source.name + ".restore-tmp")
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, source)

        post_store = MeasurementStore(source, key=self._key)
        try:
            post_ok = post_store.verify_chain()
            records = post_store.count()
        except MeasurementStoreError as exc:
            raise LedgerRecoveryError(
                f"restored ledger unreadable after swap: {exc}") from exc
        if not post_ok:
            raise LedgerRecoveryError(
                "restored ledger failed chain verification after swap; "
                "quarantined previous file was preserved")
        return RestoreReport(restored_path=source, quarantined_previous=quarantined,
                             records_restored=records, post_restore_verified=True)
