"""Signed capability manifests: validation, Ed25519 signing, freshness, revocation.

Issue #47, stage 1. Works against schemas/node-capabilities.schema.json
(structural subset, checked by hand - no jsonschema dependency). Signature
verification and policy authorization live outside JSON Schema by design
(see schema description), and this module IS that outside part.

Rules (fail-closed everywhere):
- A manifest is only valid if: structure complete, signature verifies
  (Ed25519 over the canonical JSON of the unsigned manifest), the time
  window [issued_at, expires_at] contains now, and neither node_id nor
  key_id is revoked.
- Times must be timezone-aware ISO-8601 strings; naive timestamps are
  rejected (UNKNOWN is never HEALTHY).
- DETECTION != AUTHORIZATION: a verified manifest proves authorship and
  freshness of an ADVERTISEMENT only. It is not proof that the resources
  actually exist, and it authorizes nothing by itself.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Optional

from controller.crypto_receipts import canonical_record_bytes

SIGNATURE_ALGORITHM = "Ed25519"

REQUIRED_TOP_LEVEL = (
    "schema_version", "node_id", "key_id", "software_version",
    "issued_at", "expires_at", "resources", "contributions", "policy_version",
)
REQUIRED_RESOURCES = (
    "cpu_cores_available", "ram_mb_available", "vram_mb_available", "disk_mb_available",
)
REQUIRED_CONTRIBUTIONS = ("compute", "verification", "encrypted_storage", "metadata_index")


class ManifestError(ValueError):
    """Raised when signing fails structurally."""


def _parse_instant(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ManifestError("timestamp must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestError(f"unparsable timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ManifestError(f"naive timestamp rejected (timezone required): {value!r}")
    return parsed


def _validate_structure(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be a dict")
    missing = [key for key in REQUIRED_TOP_LEVEL if key not in manifest]
    if missing:
        raise ManifestError(f"manifest is missing required fields: {missing}")
    if manifest["schema_version"] != 1:
        raise ManifestError(f"unsupported schema_version: {manifest['schema_version']!r}")
    for field in ("node_id", "key_id", "software_version", "policy_version"):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            raise ManifestError(f"{field} must be a non-empty string")
    _parse_instant(manifest["issued_at"])
    _parse_instant(manifest["expires_at"])
    resources = manifest["resources"]
    if not isinstance(resources, dict) or any(k not in resources for k in REQUIRED_RESOURCES):
        raise ManifestError(f"resources must contain all of {list(REQUIRED_RESOURCES)}")
    for key in REQUIRED_RESOURCES:
        value = resources[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ManifestError(f"resources.{key} must be a non-negative number")
    contributions = manifest["contributions"]
    if not isinstance(contributions, dict) or any(k not in contributions for k in REQUIRED_CONTRIBUTIONS):
        raise ManifestError(f"contributions must contain all of {list(REQUIRED_CONTRIBUTIONS)}")
    for key in REQUIRED_CONTRIBUTIONS:
        if not isinstance(contributions[key], bool):
            raise ManifestError(f"contributions.{key} must be a boolean")


def sign_manifest(manifest: dict[str, Any], private_key: bytes) -> dict[str, Any]:
    """Validate structure and return a new manifest with an embedded Ed25519 signature."""
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be a dict")
    if "signature" in manifest:
        raise ManifestError("manifest already carries a signature")
    _validate_structure(manifest)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if not isinstance(private_key, bytes) or len(private_key) != 32:
        raise ManifestError("private signing key must be raw 32 bytes")
    signing_key = Ed25519PrivateKey.from_private_bytes(private_key)
    signature = signing_key.sign(canonical_record_bytes(manifest)).hex()
    signed = dict(manifest)
    signed["signature"] = {"algorithm": SIGNATURE_ALGORITHM, "value": signature}
    return signed


def verify_manifest(
    signed_manifest: Any,
    public_key: bytes,
    *,
    now: str,
    revoked_node_ids: Optional[set[str]] = None,
    revoked_key_ids: Optional[set[str]] = None,
) -> tuple[bool, str]:
    """Full fail-closed verification: structure, signature, time window, revocation.

    Returns (valid, reason). valid=False always comes with a concrete reason;
    valid=True means 'authored and fresh advertisement', never a resource
    existence proof or an authorization.
    """
    if not isinstance(signed_manifest, dict):
        return False, "manifest must be a dict"
    if "signature" not in signed_manifest:
        return False, "manifest carries no signature"
    signature = signed_manifest["signature"]
    if not isinstance(signature, dict) or signature.get("algorithm") != SIGNATURE_ALGORITHM:
        return False, "unsupported or missing signature algorithm"
    value = signature.get("value")
    if not isinstance(value, str) or len(value) != 128:
        return False, "malformed signature value"
    unsigned = {k: v for k, v in signed_manifest.items() if k != "signature"}
    try:
        _validate_structure(unsigned)
    except ManifestError as exc:
        return False, f"structural validation failed: {exc}"
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        verification_key = Ed25519PublicKey.from_public_bytes(public_key)
        verification_key.verify(bytes.fromhex(value), canonical_record_bytes(unsigned))
    except Exception:
        return False, "signature verification failed"
    now_dt = _parse_instant(now)
    issued = _parse_instant(signed_manifest["issued_at"])
    expires = _parse_instant(signed_manifest["expires_at"])
    if now_dt < issued:
        return False, "manifest not yet valid (issued_at in the future)"
    if now_dt > expires:
        return False, "manifest expired"
    if revoked_node_ids and signed_manifest["node_id"] in revoked_node_ids:
        return False, f"node_id revoked: {signed_manifest['node_id']}"
    if revoked_key_ids and signed_manifest["key_id"] in revoked_key_ids:
        return False, f"key_id revoked: {signed_manifest['key_id']}"
    return True, "signed, fresh, unrevoked advertisement (no resource existence proof, no authorization)"
