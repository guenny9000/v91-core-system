"""Pinned model-run manifests and exact replay comparison.

This module does not execute a model. It records the inputs and execution
conditions needed by an external runner, then compares independent replay
records. A matching digest is evidence of byte-identical output under the
recorded conditions; it is not proof that the model answer is true.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

SCHEMA_VERSION = 1
_DIGEST_FIELDS = ("model_digest", "tokenizer_digest", "runtime_digest", "input_digest", "output_digest", "settings_digest")
_CONDITION_FIELDS = ("model_digest", "tokenizer_digest", "runtime_digest", "input_digest", "settings_digest", "seed", "precision", "backend")


class ModelRunManifestError(ValueError):
    """Raised when a run manifest cannot be safely constructed or checked."""


def sha256_bytes(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise ModelRunManifestError("artifact content must be bytes")
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ModelRunManifestError("settings must be finite JSON-compatible data") from exc


def _validate_digest(name: str, value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ModelRunManifestError(f"{name} must be a 64-character SHA-256 hex digest")
    if any(char not in "0123456789abcdef" for char in value):
        raise ModelRunManifestError(f"{name} must be lowercase hexadecimal")
    return value


def build_run_manifest(
    *,
    model_digest: str,
    tokenizer_digest: str,
    runtime_digest: str,
    input_bytes: bytes,
    output_bytes: bytes,
    seed: int,
    parameters: Mapping[str, Any],
    precision: str,
    backend: str,
) -> dict[str, Any]:
    """Build a canonical run record from pinned artifacts and byte inputs."""
    for name, value in (("model_digest", model_digest), ("tokenizer_digest", tokenizer_digest), ("runtime_digest", runtime_digest)):
        _validate_digest(name, value)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ModelRunManifestError("seed must be a non-negative integer")
    if not isinstance(parameters, Mapping):
        raise ModelRunManifestError("parameters must be a mapping")
    if not isinstance(precision, str) or not precision.strip():
        raise ModelRunManifestError("precision is required")
    if not isinstance(backend, str) or not backend.strip():
        raise ModelRunManifestError("backend is required")
    settings = dict(parameters)
    settings_digest = sha256_bytes(_canonical_json(settings))
    return {
        "schema_version": SCHEMA_VERSION,
        "model_digest": model_digest,
        "tokenizer_digest": tokenizer_digest,
        "runtime_digest": runtime_digest,
        "input_digest": sha256_bytes(input_bytes),
        "output_digest": sha256_bytes(output_bytes),
        "settings": settings,
        "settings_digest": settings_digest,
        "seed": seed,
        "precision": precision,
        "backend": backend,
        "status": "COMPLETED_UNVERIFIED",
    }


def validate_run_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate the manifest shape and all digests before comparison."""
    if not isinstance(manifest, Mapping):
        raise ModelRunManifestError("manifest must be a mapping")
    required = {"schema_version", *_DIGEST_FIELDS, "settings", "seed", "precision", "backend", "status"}
    if set(manifest) != required:
        raise ModelRunManifestError("manifest fields do not match schema")
    if isinstance(manifest["schema_version"], bool) or manifest["schema_version"] != SCHEMA_VERSION:
        raise ModelRunManifestError("unsupported schema version")
    for field in _DIGEST_FIELDS:
        _validate_digest(field, manifest[field])
    if not isinstance(manifest["settings"], Mapping):
        raise ModelRunManifestError("settings must be a mapping")
    if sha256_bytes(_canonical_json(dict(manifest["settings"]))) != manifest["settings_digest"]:
        raise ModelRunManifestError("settings digest mismatch")
    seed = manifest["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ModelRunManifestError("invalid seed")
    for field in ("precision", "backend"):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            raise ModelRunManifestError(f"invalid {field}")
    if manifest["status"] != "COMPLETED_UNVERIFIED":
        raise ModelRunManifestError("only completed, unverified run records can be replay-compared")


def verify_exact_replay(reference: Mapping[str, Any], replay: Mapping[str, Any]) -> dict[str, str]:
    """Compare two independently produced run records without trusting either claim."""
    validate_run_manifest(reference)
    validate_run_manifest(replay)
    for field in _CONDITION_FIELDS:
        if reference[field] != replay[field]:
            return {"status": "CONDITIONS_MISMATCH", "reason": f"execution condition differs: {field}"}
    if reference["output_digest"] == replay["output_digest"]:
        return {"status": "VERIFIED_EXACT", "reason": "canonical output digests match under pinned conditions"}
    return {"status": "NONDETERMINISTIC", "reason": "output digests differ under matching recorded conditions"}
