#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Signed update gate (Issue #8, stage: signed updates + isolation
boundary).

Purpose: verify publisher identity of update manifests with Ed25519
against explicitly configured trusted keys (a payload hash alone is
NOT publisher authentication) and stage verified payloads into a
separate staging directory without ever executing them.

Reuse (NO_DUPLICATE_SYSTEMS): Ed25519 signing/verification comes from
controller.crypto_receipts (sign_record / verify_record_signature);
canonical JSON and raw-32-byte key handling are NOT reimplemented here.

Fail-closed rules:
- manifest without a valid, current, non-revoked trusted signature is
  REJECTED; UNKNOWN is never ACCEPTED
- payload must match the signed payload_sha256 and payload_size_bytes
  exactly, otherwise staging is refused
- staging is atomic (temp file + fsync + rename), never overwrites an
  existing staged artifact
- this module has NO install/execute/promote function on purpose

Honest limits: SIGNATURE != TRUSTWORTHY AUTHOR (a trusted key proves
publisher identity, not content quality); STAGED != INSTALLED;
VERIFIED != TESTED; sandbox/actual isolation of staged files is the
operating system's job, not this module's; no network fetch, no key
creation, no key rotation daemon (trusted keys are administered by the
operator, revocation lists are plain configuration).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from controller.crypto_receipts import (
    CryptoReceiptError,
    SIGNATURE_FIELD,
    generate_signing_keypair,
    sign_record,
    verify_record_signature,
)
MANIFEST_KIND = "V91_UPDATE_MANIFEST"
SCHEMA_VERSION = 1
STATUS_ACCEPTED = "ACCEPTED_TRUSTED_STAGED"
STATUS_REJECTED = "REJECTED"
SIGNATURE_ALGO_FIELD = "signature_algorithm"


class UpdateGateError(ValueError):
    """Fail-closed update gate error."""


@dataclass(frozen=True)
class UpdateVerdict:
    status: str
    reason: str
    key_id: str | None = None
    staged_path: Path | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise UpdateGateError(message)


def _parse_instant(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise UpdateGateError(f"{field} must be a non-empty ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise UpdateGateError(f"{field} is not a valid ISO-8601 timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise UpdateGateError(f"{field} must be timezone-aware (naive timestamps rejected)")
    return parsed


def _validate_manifest_structure(manifest: Any) -> dict[str, Any]:
    _require(isinstance(manifest, dict), "manifest must be a dict")
    _require(manifest.get("kind") == MANIFEST_KIND,
             f"manifest kind must be '{MANIFEST_KIND}'")
    _require(manifest.get("schema_version") == SCHEMA_VERSION,
             f"schema_version must be {SCHEMA_VERSION}")
    _require(isinstance(manifest.get("release_name"), str)
             and len(manifest["release_name"].strip()) > 0,
             "release_name must be a non-empty string")
    _require(isinstance(manifest.get("publisher_key_id"), str)
             and len(manifest["publisher_key_id"].strip()) > 0,
             "publisher_key_id must be a non-empty string")
    digest = manifest.get("payload_sha256")
    _require(isinstance(digest, str) and len(digest) == 64,
             "payload_sha256 must be a 64-char hex string")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise UpdateGateError("payload_sha256 must be hex") from exc
    size = manifest.get("payload_size_bytes")
    _require(isinstance(size, int) and not isinstance(size, bool) and size >= 0,
             "payload_size_bytes must be a non-negative int")
    _require(manifest.get(SIGNATURE_ALGO_FIELD) in ("ED25519",),
             "signature_algorithm must be ED25519")
    _require(SIGNATURE_FIELD in manifest, "manifest is unsigned (missing signature)")
    _parse_instant(manifest.get("created_at"), "created_at")
    _parse_instant(manifest.get("expires_at"), "expires_at")
    created = _parse_instant(manifest["created_at"], "created_at")
    expires = _parse_instant(manifest["expires_at"], "expires_at")
    _require(created <= expires, "expires_at must not be before created_at")
    return manifest


class TrustedUpdateKeys:
    """Explicitly configured trusted publisher keys with revocation."""

    def __init__(self, keys: Mapping[str, bytes],
                 revoked_key_ids: tuple[str, ...] = ()) -> None:
        if not isinstance(keys, Mapping) or len(keys) == 0:
            raise UpdateGateError("trusted key set must be a non-empty mapping")
        for key_id, public_key in keys.items():
            if not isinstance(key_id, str) or not key_id.strip():
                raise UpdateGateError("trusted key ids must be non-empty strings")
            if not isinstance(public_key, bytes) or len(public_key) != 32:
                raise UpdateGateError(
                    f"public key for '{key_id}' must be raw 32 bytes")
        for key_id in revoked_key_ids:
            if key_id not in keys:
                raise UpdateGateError(
                    f"revoked key id '{key_id}' is not in the trusted key set")
        self._keys = dict(keys)
        self._revoked = set(revoked_key_ids)

    def is_trusted(self, key_id: Any) -> bool:
        return (isinstance(key_id, str) and key_id in self._keys
                and key_id not in self._revoked)

    def public_key(self, key_id: str) -> bytes:
        return self._keys[key_id]


class UpdateGate:
    """Verify signed update manifests and stage verified payloads."""

    def __init__(self, trusted: TrustedUpdateKeys,
                 now: datetime | None = None) -> None:
        if not isinstance(trusted, TrustedUpdateKeys):
            raise UpdateGateError("trusted must be a TrustedUpdateKeys instance")
        if now is not None:
            _require(isinstance(now, datetime)
                     and now.utcoffset() is not None,
                     "now must be a timezone-aware datetime")
        self._trusted = trusted
        self._now = now

    def _current_now(self) -> datetime:
        now = self._now or datetime.now().astimezone()
        _require(now.utcoffset() is not None, "wall clock must be timezone-aware")
        return now

    def verify_manifest(self, manifest: Any) -> UpdateVerdict:
        try:
            _validate_manifest_structure(manifest)
        except UpdateGateError as exc:
            return UpdateVerdict(status=STATUS_REJECTED, reason=f"malformed manifest: {exc}")
        key_id = manifest["publisher_key_id"]
        if not self._trusted.is_trusted(key_id):
            if key_id in self._trusted._revoked:
                return UpdateVerdict(status=STATUS_REJECTED,
                                     reason=f"publisher key '{key_id}' is revoked")
            return UpdateVerdict(status=STATUS_REJECTED,
                                 reason=f"publisher key '{key_id}' is not trusted")
        try:
            signature_ok = verify_record_signature(manifest,
                                                   self._trusted.public_key(key_id))
        except CryptoReceiptError as exc:
            return UpdateVerdict(status=STATUS_REJECTED,
                                 reason=f"signature check failed: {exc}")
        if not signature_ok:
            return UpdateVerdict(status=STATUS_REJECTED,
                                 reason="Ed25519 signature invalid or malformed")
        now = self._current_now()
        created = datetime.fromisoformat(manifest["created_at"])
        expires = datetime.fromisoformat(manifest["expires_at"])
        if now < created:
            return UpdateVerdict(status=STATUS_REJECTED,
                                 reason="manifest not valid yet (created_at in the future)")
        if now > expires:
            return UpdateVerdict(status=STATUS_REJECTED,
                                 reason="manifest expired (expires_at in the past)")
        return UpdateVerdict(status="ACCEPTED_TRUSTED", reason="verified",
                             key_id=key_id)

    def stage_payload(self, manifest: Any,
                      payload: bytes, staging_dir: Path | str) -> UpdateVerdict:
        if not isinstance(payload, bytes):
            return UpdateVerdict(status=STATUS_REJECTED,
                                 reason="payload must be bytes")
        verdict = self.verify_manifest(manifest)
        if verdict.status != "ACCEPTED_TRUSTED":
            return verdict
        digest = hashlib.sha256(payload).hexdigest()
        if digest != manifest["payload_sha256"]:
            return UpdateVerdict(status=STATUS_REJECTED,
                                 reason="payload sha256 mismatch (signed digest)")
        if len(payload) != manifest["payload_size_bytes"]:
            return UpdateVerdict(status=STATUS_REJECTED,
                                 reason="payload size mismatch (signed size)")
        staging_dir = Path(staging_dir)
        try:
            staging_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise UpdateGateError(f"staging dir unusable: {exc}") from exc
        staged = staging_dir / f"{manifest['release_name']}.staged"
        staged_manifest = staging_dir / f"{manifest['release_name']}.manifest.json"
        if staged.exists() or staged_manifest.exists():
            return UpdateVerdict(status=STATUS_REJECTED,
                                 reason="staged artifact already exists; "
                                        "refusing to overwrite (clear the "
                                        "staging area first)")
        tmp = staged.with_name(staged.name + ".tmp")
        with open(tmp, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, staged)
        tmp_manifest = staged_manifest.with_name(staged_manifest.name + ".tmp")
        with open(tmp_manifest, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, sort_keys=True, ensure_ascii=False, indent=1)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_manifest, staged_manifest)
        return UpdateVerdict(status=STATUS_ACCEPTED, reason="verified and staged",
                             key_id=manifest["publisher_key_id"],
                             staged_path=staged)


def build_update_manifest(release_name: str, payload: bytes,
                          publisher_key_id: str, private_key: bytes,
                          created_at: datetime, expires_at: datetime) -> dict[str, Any]:
    """Operator/publisher helper: create a signed manifest. Private key
    stays with the caller; payloads are hashed, not embedded."""
    _require(isinstance(payload, bytes), "payload must be bytes")
    created_iso = created_at.isoformat()
    expires_iso = expires_at.isoformat()
    manifest: dict[str, Any] = {
        "kind": MANIFEST_KIND,
        "schema_version": SCHEMA_VERSION,
        "release_name": release_name,
        "publisher_key_id": publisher_key_id,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "payload_size_bytes": len(payload),
        "created_at": created_iso,
        "expires_at": expires_iso,
        SIGNATURE_ALGO_FIELD: "ED25519",
    }
    manifest[SIGNATURE_FIELD] = sign_record(manifest, private_key)
    return manifest


__all__ = [
    "UpdateGate",
    "UpdateGateError",
    "TrustedUpdateKeys",
    "UpdateVerdict",
    "build_update_manifest",
    "generate_signing_keypair",
]
