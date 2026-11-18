#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Fail-closed staging area for untrusted artifacts (Issue #8,
isolation boundary, Stage 2).

New code, external model suggestions, downloaded artifacts and other
untrusted data must be staged and inspected separately BEFORE they can
reach any live location. This module implements the mechanical side of
that boundary, fail-closed:

- ingest copies files into the staging area (the source is never
  moved or modified), strips the executable bit, records sha256 and
  size in a manifest, and refuses oversized or duplicate entries.
- verify re-hashes every staged file (tamper evidence); a changed
  file is never silently re-baselined as healthy.
- approve runs a caller-supplied review callable per file and records
  APPROVED or REJECTED with a review reason. UNTESTED is the default
  and stays UNTESTED - no check, no verdict (CLAIM != EVIDENCE).
- promote copies ONLY files whose recorded verdict is APPROVED into a
  destination directory; REJECTED and UNTESTED files stay staged
  (ISOLATE_NOT_DESTROY: nothing is deleted during promotion).

Honest limits:
- STAGED != TESTED: ingest proves capture, never safety.
- VERDICT != TRUTH: an APPROVED verdict records that one explicit
  review callable ran and said yes, nothing more.
- No execution ever happens here: this module never runs any staged
  or promoted content as code. Execution stays with the caller.
- No network, no cross-process locking, no wipe operation: removing
  staged evidence is not part of this boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from pathlib import Path
from typing import Callable

REVIEW_MISSING = "UNTESTED"
REVIEW_APPROVED = "APPROVED"
REVIEW_REJECTED = "REJECTED"
STATUS_OK = "OK"
STATUS_CHANGED = "CHANGED"
STATUS_MISSING = "MISSING"
_FORBIDDEN_IN_NAME = frozenset({"/", chr(92)})


class StagingError(RuntimeError):
    """The staging boundary cannot work honestly (fail-closed)."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


class StagingArea:
    """On-disk artifact quarantine with manifest and explicit verdicts."""

    def __init__(self, directory, *, max_files=256,
                 max_bytes_per_file=64 * 1024 * 1024) -> None:
        self._root = Path(directory).expanduser().resolve()
        if (not isinstance(max_files, int) or type(max_files) is bool
                or max_files < 1):
            raise StagingError("max_files must be a positive integer")
        if (not isinstance(max_bytes_per_file, int)
                or type(max_bytes_per_file) is bool or max_bytes_per_file < 1):
            raise StagingError("max_bytes_per_file must be a positive integer")
        self._root.mkdir(parents=True, exist_ok=True)
        self._manifest = self._root / "staging_manifest.json"
        self._max_files = max_files
        self._max_bytes = max_bytes_per_file

    def _load(self) -> dict:
        if not self._manifest.exists():
            return {"schema_version": 1, "entries": {}}
        try:
            manifest = json.loads(self._manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StagingError(f"manifest unreadable: {exc}") from exc
        if (not isinstance(manifest, dict)
                or manifest.get("schema_version") != 1
                or not isinstance(manifest.get("entries"), dict)):
            raise StagingError("manifest schema mismatch; refusing to guess")
        return manifest

    def _save(self, manifest: dict) -> None:
        tmp = self._manifest.with_name("staging_manifest.json.tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self._manifest)

    def ingest(self, source, *, name=None) -> dict:
        """Copy one untrusted file into staging. Never executes it."""
        source_path = Path(source).expanduser().resolve()
        if not source_path.is_file():
            raise StagingError(f"source is not a regular file: {source_path}")
        entry_name = name if name is not None else source_path.name
        if (not isinstance(entry_name, str) or not entry_name.strip()
                or entry_name in (".", "..")
                or any(ch in _FORBIDDEN_IN_NAME for ch in entry_name)):
            raise StagingError("staging name must be a plain, non-empty file name")
        manifest = self._load()
        if entry_name in manifest["entries"]:
            raise StagingError(f"duplicate staging entry: {entry_name!r} (ISOLATE_NOT_DESTROY)")
        if len(manifest["entries"]) >= self._max_files:
            raise StagingError("staging file limit reached; refusing more input")
        size = source_path.stat().st_size
        if size > self._max_bytes:
            raise StagingError(f"source exceeds size limit ({size} > {self._max_bytes})")
        target = self._root / entry_name
        if target.exists():
            raise StagingError(f"staged file already exists on disk: {entry_name!r}")
        shutil.copyfile(source_path, target)
        os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
        entry = {
            "sha256": _sha256(target),
            "size_bytes": size,
            "verdict": REVIEW_MISSING,
            "review_reason": "",
        }
        manifest["entries"][entry_name] = entry
        self._save(manifest)
        return {"name": entry_name, **entry}

    def verify(self) -> dict:
        """Re-hash every staged file: tamper evidence, not a safety claim."""
        manifest = self._load()
        results = {}
        for name in sorted(manifest["entries"]):
            target = self._root / name
            if not target.is_file():
                results[name] = STATUS_MISSING
                continue
            recorded = manifest["entries"][name]["sha256"]
            results[name] = STATUS_OK if _sha256(target) == recorded else STATUS_CHANGED
        return results

    def approve(self, name: str, reviewer) -> str:
        """Run an explicit review callable on ONE staged file, record verdict."""
        if not callable(reviewer):
            raise StagingError("an explicit review callable is required")
        manifest = self._load()
        if name not in manifest["entries"]:
            raise StagingError(f"unknown staging entry: {name!r}")
        target = self._root / name
        if _sha256(target) != manifest["entries"][name]["sha256"]:
            raise StagingError(f"staged file changed since ingest: {name!r}")
        try:
            verdict, reason = reviewer(target, dict(manifest["entries"][name]))
        except Exception as exc:
            raise StagingError(f"review callable raised: {exc}") from exc
        if not isinstance(reason, str) or not reason.strip():
            raise StagingError("review reason must be a non-empty string")
        if verdict is True:
            recorded = REVIEW_APPROVED
        elif verdict is False:
            recorded = REVIEW_REJECTED
        else:
            raise StagingError("review callable must return (bool, reason)")
        manifest["entries"][name]["verdict"] = recorded
        manifest["entries"][name]["review_reason"] = reason
        self._save(manifest)
        return recorded

    def promote(self, destination, names=None) -> dict:
        """Copy ONLY APPROVED files to destination; others stay staged."""
        if names is None:
            manifest = self._load()
            names = sorted(manifest["entries"])
        elif not isinstance(names, (list, tuple)) or not names:
            raise StagingError("names must be a non-empty list or None")
        destination = Path(destination).expanduser().resolve()
        if not destination.is_dir():
            raise StagingError(f"destination must be an existing directory: {destination}")
        manifest = self._load()
        outcomes = {}
        for name in names:
            if name not in manifest["entries"]:
                outcomes[name] = "UNKNOWN_ENTRY";
                continue
            entry = manifest["entries"][name]
            if entry["verdict"] == REVIEW_APPROVED:
                target = self._root / name
                if _sha256(target) != entry["sha256"]:
                    outcomes[name] = "BLOCKED_CHANGED";
                    continue
                dest_path = destination / name
                if dest_path.exists():
                    raise StagingError(f"destination already holds: {name!r} (ISOLATE_NOT_DESTROY)")
                shutil.copyfile(target, dest_path)
                outcomes[name] = "PROMOTED";
            elif entry["verdict"] == REVIEW_REJECTED:
                outcomes[name] = "STAYED_REJECTED";
            else:
                outcomes[name] = "STAYED_UNTESTED";
        return outcomes


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit("StagingArea is a module, not a standalone program")