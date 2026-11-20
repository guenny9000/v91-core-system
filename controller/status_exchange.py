#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Canonical node status exchange payload for V91 federation (Issue #103).

The cooperative answer to "which version are you on, what can you
do, how are you": one bounded, validated, canonical payload a node
builds about ITSELF and parses about OTHERS. It rides inside an
authenticated federation envelope (controller/federation_sender.py);
this module opens no socket and runs no loop.

Rules (fail-closed everywhere):
- build_status_payload validates every field and refuses oversized or
  malformed self-descriptions instead of repairing them
- parse_status_payload re-validates foreign payloads as untrusted
  data: exact field set, known status_kind, bounded and sorted
  capabilities, lowercase hex digests only
- knowledge_digests compare WHAT A NODE POSSESSES, never what is true:
  equal digests prove bytes, unequal digests are divergence to
  review, never a merge order or an update instruction

Honest limits (DOCUMENTED != IMPLEMENTED here):
- NO network, NO scheduler, NO daemon, NO autonomic query loop:
  producing, sending and consuming the payload is the separately
  reviewed caller job (SHIPPING != INSTALLATION)
- NO global view: every node keeps its own local register
  (controller/cooperation_register.py); a merged status is refused
- DETECTION != AUTHORIZATION: a received status grants no rights and
  triggers no remote action; a version difference is evidence to
  review, never an upgrade command
"""
from __future__ import annotations

import json
from typing import Any, Mapping

STATUS_SCHEMA_VERSION = 1
STATUS_KIND = "NODE_STATUS"
ALLOWED_STATES = frozenset({"READY", "BUSY", "DEGRADED", "STOPPING"})
MAX_STATUS_BYTES = 4096
MAX_CAPABILITIES = 64
MAX_DIGESTS = 64
MAX_TEXT_BYTES = 256
STATUS_FIELDS = frozenset({
    "schema_version", "status_kind", "software_version",
    "capabilities", "state", "knowledge_digests",
})
_HEX_CHARS = frozenset("0123456789abcdef")


class StatusExchangeError(ValueError):
    """Raised when a status payload cannot be built or parsed (fail-closed)."""


def _bounded_text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StatusExchangeError("text fields must be non-empty strings")
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise StatusExchangeError("text field exceeds the byte bound")
    return value


def _validated_capabilities(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        raise StatusExchangeError("capabilities must be a list or tuple")
    if len(values) > MAX_CAPABILITIES:
        raise StatusExchangeError(f"at most {MAX_CAPABILITIES} capabilities allowed")
    caps = sorted(_bounded_text(item) for item in values)
    if len(set(caps)) != len(caps):
        raise StatusExchangeError("capabilities must be unique")
    return caps


def _validated_digests(values: Any) -> dict[str, str]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise StatusExchangeError("knowledge_digests must be a mapping")
    if len(values) > MAX_DIGESTS:
        raise StatusExchangeError(f"at most {MAX_DIGESTS} digests allowed")
    result: dict[str, str] = {}
    for name, digest in values.items():
        key = _bounded_text(name)
        if not isinstance(digest, str) or len(digest) != 64:
            raise StatusExchangeError("digests must be 64 lowercase hex chars")
        if not set(digest) <= _HEX_CHARS:
            raise StatusExchangeError("digests must be lowercase hex")
        result[key] = digest
    return dict(sorted(result.items()))


def canonical_status_bytes(payload: Mapping[str, Any]) -> bytes:
    """Canonical JSON bytes of a payload, for signing and size bounds."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def build_status_payload(
    *,
    software_version: str,
    capabilities: Any = (),
    state: str = "READY",
    knowledge_digests: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build one validated self-description. Refuses, never repairs."""
    if not isinstance(software_version, str):
        raise StatusExchangeError("software_version must be a string")
    version = _bounded_text(software_version)
    caps = _validated_capabilities(capabilities)
    if state not in ALLOWED_STATES:
        raise StatusExchangeError(f"state must be one of {sorted(ALLOWED_STATES)}")
    digests = _validated_digests(knowledge_digests)
    payload = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "status_kind": STATUS_KIND,
        "software_version": version,
        "capabilities": caps,
        "state": state,
        "knowledge_digests": digests,
    }
    if len(canonical_status_bytes(payload)) > MAX_STATUS_BYTES:
        raise StatusExchangeError(f"status payload exceeds {MAX_STATUS_BYTES} bytes")
    return payload


def parse_status_payload(payload: Any) -> dict[str, Any]:
    """Parse and re-validate a FOREIGN status payload as untrusted data."""
    if not isinstance(payload, Mapping):
        raise StatusExchangeError("status payload must be a JSON object")
    if set(payload) != STATUS_FIELDS:
        raise StatusExchangeError("status payload field set does not match the schema")
    if payload["schema_version"] != STATUS_SCHEMA_VERSION:
        raise StatusExchangeError("unsupported status schema version")
    if payload["status_kind"] != STATUS_KIND:
        raise StatusExchangeError(f"not a {STATUS_KIND} payload")
    version = _bounded_text(payload["software_version"])
    if not isinstance(payload["capabilities"], list):
        raise StatusExchangeError("capabilities must arrive as a JSON list")
    caps = _validated_capabilities(payload["capabilities"])
    if payload["state"] not in ALLOWED_STATES:
        raise StatusExchangeError(f"unknown state {payload['state']!r}")
    digests = _validated_digests(payload["knowledge_digests"])
    parsed = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "status_kind": STATUS_KIND,
        "software_version": version,
        "capabilities": caps,
        "state": payload["state"],
        "knowledge_digests": digests,
    }
    if len(canonical_status_bytes(parsed)) > MAX_STATUS_BYTES:
        raise StatusExchangeError(f"status payload exceeds {MAX_STATUS_BYTES} bytes")
    return parsed
