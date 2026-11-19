"""Signed capability manifests: validation, Ed25519 signing, freshness, revocation.

Issue #47, stage 1. Validates the machine-readable schema's structural
constraints without a jsonschema dependency. Signature verification and
policy authorization live outside JSON Schema by design.

Rules (fail-closed everywhere):
- A manifest is only valid if its structure is complete, signature verifies
  (Ed25519 over canonical JSON of the unsigned manifest), its time window
  contains now, and neither node_id nor key_id is revoked.
- Times must be timezone-aware ISO-8601 strings; naive timestamps are rejected.
- A verified manifest proves authorship and freshness of an ADVERTISEMENT
  only. It does not prove resources exist and authorizes nothing by itself.
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Optional

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
_ALLOWED_TOP_LEVEL = set(REQUIRED_TOP_LEVEL) | {"model_runners", "limits", "data_classes"}
_ALLOWED_RESOURCES = set(REQUIRED_RESOURCES) | {"bandwidth_mbps_available", "measured_at", "measurement_source"}
_ALLOWED_LIMITS = {"max_task_bytes", "max_concurrent_tasks", "storage_quota_mb", "retention_seconds", "max_network_mbps"}
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_DETERMINISM = {"EXACT_REPLAY_SUPPORTED", "TOLERANCE_ONLY", "NONDETERMINISTIC", "UNKNOWN"}
_DATA_CLASSES = {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "PERSONAL"}


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


def _finite_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _validate_digest(value: Any, field: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ManifestError(f"{field} must be a lowercase SHA-256 hex digest" + (" or null" if nullable else ""))


def _validate_structure(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be a dict")
    unknown = set(manifest) - _ALLOWED_TOP_LEVEL
    if unknown:
        raise ManifestError(f"unknown top-level fields: {sorted(unknown)}")
    missing = [key for key in REQUIRED_TOP_LEVEL if key not in manifest]
    if missing:
        raise ManifestError(f"manifest is missing required fields: {missing}")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ManifestError(f"unsupported schema_version: {manifest['schema_version']!r}")
    for field in ("node_id", "key_id", "software_version", "policy_version"):
        if not isinstance(manifest[field], str) or not manifest[field].strip() or len(manifest[field]) > 128:
            raise ManifestError(f"{field} must be a non-empty string of at most 128 characters")
    issued = _parse_instant(manifest["issued_at"])
    expires = _parse_instant(manifest["expires_at"])
    if expires <= issued:
        raise ManifestError("expires_at must be later than issued_at")

    resources = manifest["resources"]
    if not isinstance(resources, dict):
        raise ManifestError("resources must be an object")
    unknown_resources = set(resources) - _ALLOWED_RESOURCES
    if unknown_resources:
        raise ManifestError(f"unknown resource fields: {sorted(unknown_resources)}")
    if any(k not in resources for k in REQUIRED_RESOURCES):
        raise ManifestError(f"resources must contain all of {list(REQUIRED_RESOURCES)}")
    for key in ("cpu_cores_available",):
        value = resources[key]
        if not _finite_number(value) or value < 0:
            raise ManifestError(f"resources.{key} must be a finite non-negative number")
    for key in ("ram_mb_available", "vram_mb_available", "disk_mb_available"):
        value = resources[key]
        if type(value) is not int or value < 0:
            raise ManifestError(f"resources.{key} must be a non-negative integer")
    if "bandwidth_mbps_available" in resources:
        value = resources["bandwidth_mbps_available"]
        if value is not None and (not _finite_number(value) or value < 0):
            raise ManifestError("resources.bandwidth_mbps_available must be null or a finite non-negative number")
    if "measured_at" in resources:
        _parse_instant(resources["measured_at"])
    if "measurement_source" in resources:
        value = resources["measurement_source"]
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise ManifestError("resources.measurement_source must be a non-empty string of at most 128 characters")

    contributions = manifest["contributions"]
    if not isinstance(contributions, dict):
        raise ManifestError("contributions must be an object")
    unknown_contributions = set(contributions) - set(REQUIRED_CONTRIBUTIONS)
    if unknown_contributions:
        raise ManifestError(f"unknown contribution fields: {sorted(unknown_contributions)}")
    if any(k not in contributions for k in REQUIRED_CONTRIBUTIONS):
        raise ManifestError(f"contributions must contain all of {list(REQUIRED_CONTRIBUTIONS)}")
    for key in REQUIRED_CONTRIBUTIONS:
        if not isinstance(contributions[key], bool):
            raise ManifestError(f"contributions.{key} must be a boolean")

    if "model_runners" in manifest:
        runners = manifest["model_runners"]
        if not isinstance(runners, list) or len(runners) > 64:
            raise ManifestError("model_runners must be an array of at most 64 items")
        for index, runner in enumerate(runners):
            if not isinstance(runner, dict):
                raise ManifestError(f"model_runners[{index}] must be an object")
            allowed = {"runner_id", "model_digest", "tokenizer_digest", "runtime_digest", "determinism", "precision", "backend"}
            required = {"runner_id", "model_digest", "determinism"}
            if set(runner) - allowed or required - set(runner):
                raise ManifestError(f"model_runners[{index}] has unknown or missing fields")
            if not isinstance(runner["runner_id"], str) or not runner["runner_id"].strip() or len(runner["runner_id"]) > 128:
                raise ManifestError(f"model_runners[{index}].runner_id is invalid")
            _validate_digest(runner["model_digest"], f"model_runners[{index}].model_digest")
            for field in ("tokenizer_digest", "runtime_digest"):
                if field in runner:
                    _validate_digest(runner[field], f"model_runners[{index}].{field}", nullable=True)
            if not isinstance(runner["determinism"], str) or runner["determinism"] not in _DETERMINISM:
                raise ManifestError(f"model_runners[{index}].determinism is invalid")
            for field, limit in (("precision", 64), ("backend", 128)):
                if field in runner and runner[field] is not None and (not isinstance(runner[field], str) or len(runner[field]) > limit):
                    raise ManifestError(f"model_runners[{index}].{field} is invalid")

    if "limits" in manifest:
        limits = manifest["limits"]
        if not isinstance(limits, dict) or set(limits) - _ALLOWED_LIMITS:
            raise ManifestError("limits must be an object with only schema-defined fields")
        for field, value in limits.items():
            if field == "max_network_mbps":
                if not _finite_number(value) or value < 0:
                    raise ManifestError(f"limits.{field} must be a finite non-negative number")
            elif type(value) is not int or value < 0:
                raise ManifestError(f"limits.{field} must be a non-negative integer")

    if "data_classes" in manifest:
        classes = manifest["data_classes"]
        if (not isinstance(classes, list)
                or any(not isinstance(item, str) or item not in _DATA_CLASSES for item in classes)
                or len(classes) != len(set(classes))):
            raise ManifestError("data_classes must contain unique supported data-class strings")


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

    A True result means 'authored and fresh advertisement', never a resource
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
    try:
        bytes.fromhex(value)
    except ValueError:
        return False, "malformed signature value"
    unsigned = {k: v for k, v in signed_manifest.items() if k != "signature"}
    try:
        _validate_structure(unsigned)
        now_dt = _parse_instant(now)
        issued = _parse_instant(unsigned["issued_at"])
        expires = _parse_instant(unsigned["expires_at"])
    except ManifestError as exc:
        return False, f"manifest validation failed: {exc}"
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        verification_key = Ed25519PublicKey.from_public_bytes(public_key)
        verification_key.verify(bytes.fromhex(value), canonical_record_bytes(unsigned))
    except Exception:
        return False, "signature verification failed"
    if now_dt < issued:
        return False, "manifest not yet valid (issued_at in the future)"
    if now_dt > expires:
        return False, "manifest expired"
    if revoked_node_ids and unsigned["node_id"] in revoked_node_ids:
        return False, f"node_id revoked: {unsigned['node_id']}"
    if revoked_key_ids and unsigned["key_id"] in revoked_key_ids:
        return False, f"key_id revoked: {unsigned['key_id']}"
    return True, "signed, fresh, unrevoked advertisement (no resource existence proof, no authorization)"
