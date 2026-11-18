#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Update promotion and rollback (Issue #8, stage: rollback/recovery for
signed updates; builds on controller/update_gate.py, PR #145).

Purpose: promote signature-verified staged updates into a versioned
deployment tree and roll back to a previously promoted version. Known
versions are retained forever (never delete the last known-good state
as part of an update: ISOLATE_NOT_DESTROY).

Reuse (NO_DUPLICATE_SYSTEMS): signature verification is delegated to
controller.update_gate.UpdateGate (which reuses crypto_receipts); no
second crypto path exists here. The deployment tree is NOT a ledger -
measurement ledgers keep their own chain elsewhere.

Fail-closed rules:
- promote() re-verifies manifest signature AND staged payload digest
  before anything moves; trusting the staging state is not allowed
- a release name may be promoted exactly once (duplicate refused)
- the staged artifact must live on the same filesystem as the
  deployment root (os.replace); cross-device staging is refused
  rather than silently copied
- rollback() re-verifies the target manifest and payload digest
  before switching the active pointer
- ACTIVE pointer is swapped atomically (tmp + fsync + rename);
  PROMOTION_LOG is append-only with fsync

Honest limits: PROMOTED != INSTALLED - this module never executes,
starts, stops or wires anything; runtime activation is the operator's
separate step. The promotion log is an append-only audit trail, NOT a
tamper-proof hash chain (integrity comes from the signed manifests,
not the log). No automatic rollback triggers; no network.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from controller.update_gate import (
    STATUS_REJECTED,
    UpdateGate,
")

ACTIVE_POINTER = "ACTIVE.json"
VERSIONS_DIR = "versions"
PROMOTION_LOG = "PROMOTION_LOG.jsonl"
ACTION_PROMOTE = "promote"
ACTION_ROLLBACK = "rollback"
STATUS_PROMOTED = "PROMOTED_SIGNED_RETAINED"
STATUS_ROLLED_BACK = "ROLLED_BACK_SIGNED_RETAINED"
PAYLOAD_FILE = "payload.bin"
MANIFEST_FILE = "manifest.json"


class PromotionError(ValueError):
    """Fail-closed promotion error."""


@dataclass(frozen=True)
class PromotionVerdict:
    status: str
    reason: str
    release_name: str | None = None
    active_release: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PromotionError(message)


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, ensure_ascii=False, indent=1)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PromotionError(f"unreadable/corrupt file {path.name}: {exc}") from exc
    _require(isinstance(data, dict), f"{path.name} must contain a JSON object")
    return data


def _now_iso(now: datetime | None) -> str:
    if now is not None:
        _require(now.utcoffset() is not None,
                 "now must be a timezone-aware datetime")
        return now.isoformat()
    current = datetime.now().astimezone()
    return current.isoformat() if current.utcoffset() is not None \
        else "UNKNOWN_WALL_CLOCK"


def _append_log(root: Path, entry: dict[str, Any]) -> None:
    log_path = root / PROMOTION_LOG
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


class UpdatePromotion:
    """Promote signed staged updates; roll back to retained versions."""

    def __init__(self, root: Path | str,
                 gate: UpdateGate, now: datetime | None = None) -> None:
        if not isinstance(gate, UpdateGate):
            raise PromotionError("gate must be an UpdateGate instance")
        self._root = Path(root)
        self._gate = gate
        self._now = now
        self._versions = self._root / VERSIONS_DIR
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            self._versions.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PromotionError(f"deployment root unusable: {exc}") from exc

    def verify_staged(self, manifest: Any,
                      staged_payload: Path | str) -> PromotionVerdict:
        """Re-verify a staged artifact without moving it."""
        staged_payload = Path(staged_payload)
        verdict = self._gate.verify_manifest(manifest)
        if verdict.status != "ACCEPTED_TRUSTED":
            return PromotionVerdict(status=STATUS_REJECTED,
                                    reason=verdict.reason)
        try:
            payload = staged_payload.read_bytes()
        except OSError as exc:
            return PromotionVerdict(status=STATUS_REJECTED,
                                    reason=f"staged payload unreadable: {exc}")
        digest = hashlib.sha256(payload).hexdigest()
        if digest != manifest["payload_sha256"]:
            return PromotionVerdict(status=STATUS_REJECTED,
                                    reason="staged payload digest mismatch")
        if len(payload) != manifest["payload_size_bytes"]:
            return PromotionVerdict(status=STATUS_REJECTED,
                                    reason="staged payload size mismatch")
        return PromotionVerdict(status="ACCEPTED_TRUSTED",
                                reason="staged artifact verified",
                                release_name=manifest["release_name"])

    def promote(self, manifest: Any,
                staged_payload: Path | str,
                staged_manifest: Path | str | None = None) -> PromotionVerdict:
        """Promote a verified staged artifact into the version tree."""
        staged_payload = Path(staged_payload)
        check = self.verify_staged(manifest, staged_payload)
        if check.status != "ACCEPTED_TRUSTED":
            return check
        release = manifest["release_name"]
        target = self._versions / release
        if target.exists():
            return PromotionVerdict(status=STATUS_REJECTED,
                                    reason=f"release '{release}' already "
                                           "promoted; duplicate refused")
        try:
            staged_payload.is_relative_to(self._root)
        except ValueError as exc:
            raise PromotionError("invalid staged payload path") from exc
        if not staged_payload.is_relative_to(self._root):
            return PromotionVerdict(
                status=STATUS_REJECTED,
                reason="staged payload must live inside the deployment root "
                       "(same filesystem); cross-device staging refused")
        target.mkdir(parents=True, exist_ok=False)
        try:
            os.replace(staged_payload, target / PAYLOAD_FILE)
            staged_manifest_path = None
            if staged_manifest is not None:
                staged_manifest_path = Path(staged_manifest)
            if staged_manifest_path is not None and staged_manifest_path.exists():
                os.replace(staged_manifest_path, target / MANIFEST_FILE)
            _atomic_write_json(target / MANIFEST_FILE, manifest)
        except OSError as exc:
            raise PromotionError(f"promotion failed mid-move: {exc}") from exc
        pointer = {
            "release_name": release,
            "publisher_key_id": manifest["publisher_key_id"],
            "payload_sha256": manifest["payload_sha256"],
            "promoted_at": _now_iso(self._now),
            "action": ACTION_PROMOTE,
        }
        _atomic_write_json(self._root / ACTIVE_POINTER, pointer)
        _append_log(self._root, {
            "action": ACTION_PROMOTE,
            "release_name": release,
            "payload_sha256": manifest["payload_sha256"],
            "publisher_key_id": manifest["publisher_key_id"],
            "at": pointer["promoted_at"],
        })
        return PromotionVerdict(status=STATUS_PROMOTED,
                                reason="promoted; previous versions retained",
                                release_name=release,
                                active_release=release)

    def active_release(self) -> str | None:
        pointer_path = self._root / ACTIVE_POINTER
        if not pointer_path.exists():
            return None
        data = _read_json(pointer_path)
        name = data.get("release_name")
        return name if isinstance(name, str) and name else None

    def list_versions(self) -> list[str]:
        return sorted(p.name for p in self._versions.iterdir()
                      if p.is_dir() and (p / PAYLOAD_FILE).exists())

    def rollback(self, target_release: str | None = None) -> PromotionVerdict:
        """Re-verify and re-activate a previously promoted version."""
        versions = self.list_versions()
        if not versions:
            return PromotionVerdict(status=STATUS_REJECTED,
                                    reason="no retained versions to roll back to")
        current = self.active_release()
        candidates = [v for v in versions if v != current]
        if target_release is None and len(candidates) != 1:
            if not candidates:
                return PromotionVerdict(
                    status=STATUS_REJECTED,
                    reason="no other retained version to roll back to")
            return PromotionVerdict(
                status=STATUS_REJECTED,
                reason="rollback target ambiguous; specify one of: "
                       + ", ".join(candidates))
        target = target_release if target_release is not None else candidates[0]
        if target not in versions:
            return PromotionVerdict(status=STATUS_REJECTED,
                                    reason=f"target '{target}' not retained")
        if target == current:
            return PromotionVerdict(status=STATUS_REJECTED,
                                    reason=f"'{target}' is already the active release")
        target_dir = self._versions / target
        try:
            manifest = _read_json(target_dir / MANIFEST_FILE)
            payload = (target_dir / PAYLOAD_FILE).read_bytes()
        except (PromotionError, OSError) as exc:
            return PromotionVerdict(status=STATUS_REJECTED,
                                    reason=f"target unreadable/corrupt: {exc}")
        verdict = self._gate.verify_manifest(manifest)
        if verdict.status != "ACCEPTED_TRUSTED":
            return PromotionVerdict(status=STATUS_REJECTED,
                                    reason="target manifest failed "
                                           f"re-verification: {verdict.reason}")
        digest = hashlib.sha256(payload).hexdigest()
        if digest != manifest["payload_sha256"]:
            return PromotionVerdict(status=STATUS_REJECTED,
                                    reason="target payload digest mismatch")
        pointer = {
            "release_name": target,
            "publisher_key_id": manifest["publisher_key_id"],
            "payload_sha256": manifest["payload_sha256"],
            "promoted_at": _now_iso(self._now),
            "action": ACTION_ROLLBACK,
        }
        _atomic_write_json(self._root / ACTIVE_POINTER, pointer)
        _append_log(self._root, {
            "action": ACTION_ROLLBACK,
            "release_name": target,
            "payload_sha256": manifest["payload_sha256"],
            "publisher_key_id": manifest["publisher_key_id"],
            "at": pointer["promoted_at"],
        })
        return PromotionVerdict(status=STATUS_ROLLED_BACK,
                                reason="rolled back; failed version retained "
                                       "(ISOLATE_NOT_DESTROY)",
                                release_name=target,
                                active_release=target)


__all__ = [
    "UpdatePromotion",
    "PromotionError",
    "PromotionVerdict",
]
