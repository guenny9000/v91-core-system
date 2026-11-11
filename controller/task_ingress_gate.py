"""Authenticated, fail-closed task-ingress decision primitive.

This module authenticates the submitted bytes with a provider-specific HMAC
key and classifies the declared use domain. A valid HMAC proves possession of
the configured shared secret for these bytes; it does not prove benign intent,
legal authority, or truth of the declaration. No decision in this module
authorizes execution or performs an audit write.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from typing import Protocol

from controller.use_policy import PolicyDecision, evaluate_use_domain

_SIGNATURE_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_CRITICAL_SECTORS = {"WATER", "FOOD", "ENERGY", "MEDICINE", "COMMUNICATION"}
_NONCE_RE = re.compile(r"^[0-9a-fA-F]{32,128}$")


class KeyProvider(Protocol):
    def get_active_key(self, provider_id: str) -> bytes | None:
        """Return active provider secret bytes, or None when unavailable."""



class ReplayStore(Protocol):
    def claim(self, provider_id: str, task_id: str, nonce: str) -> bool:
        """Atomically claim a provider-scoped task ID and nonce exactly once."""


class SQLiteReplayStore:
    """Durable replay tombstones with cross-process uniqueness.

    Keep this database on a supported local filesystem. Rows are intentionally
    retained: deleting them could reopen replay opportunities.
    """

    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        with closing(sqlite3.connect(self._database_path, timeout=10)) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS ingress_replay ("
                "provider_id TEXT NOT NULL, task_id TEXT NOT NULL, nonce TEXT NOT NULL, "
                "claimed_at INTEGER NOT NULL, PRIMARY KEY(provider_id, task_id), "
                "UNIQUE(provider_id, nonce))"
            )
            connection.commit()

    def claim(self, provider_id: str, task_id: str, nonce: str) -> bool:
        try:
            with closing(sqlite3.connect(
                self._database_path, timeout=10, isolation_level=None
            )) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO ingress_replay(provider_id, task_id, nonce, claimed_at) "
                    "VALUES (?, ?, ?, ?)",
                    (provider_id, task_id, nonce, int(time.time())),
                )
                connection.commit()
                return True
        except sqlite3.IntegrityError:
            return False


@dataclass(frozen=True)
class IngressDecision:
    status: str
    provider_id: str
    task_id: str
    use_domain: str
    sector: str
    execution_authorized: bool
    reason: str


def canonical_payload_bytes(payload: dict) -> bytes:
    """Serialize the agreed Python JSON profile deterministically.

    This is not a claim of RFC 8785/JCS compatibility. Producers must use the
    same UTF-8, sorted-key, compact-separator, no-NaN serialization profile.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


class TaskIngressGate:
    """Authenticate and classify a task; never execute or automatically approve."""

    def __init__(self, key_provider: KeyProvider, replay_store: ReplayStore, max_clock_skew_seconds: int = 300, clock=time.time) -> None:
        if (
            isinstance(max_clock_skew_seconds, bool)
            or not isinstance(max_clock_skew_seconds, int)
            or max_clock_skew_seconds < 1
        ):
            raise ValueError('max_clock_skew_seconds must be a positive integer')
        self._key_provider = key_provider
        self._replay_store = replay_store
        self._max_clock_skew_seconds = max_clock_skew_seconds
        self._clock = clock

    def _decision(
        self,
        status: str,
        provider_id: str,
        task_id: str,
        use_domain: str,
        sector: str,
        reason: str,
    ) -> IngressDecision:
        return IngressDecision(
            status=status,
            provider_id=provider_id,
            task_id=task_id,
            use_domain=use_domain,
            sector=sector,
            execution_authorized=False,
            reason=reason,
        )

    def validate(self, payload: object, signature: str) -> IngressDecision:
        if not isinstance(payload, dict):
            return self._decision(
                "REJECT_INVALID", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN",
                "Payload must be a JSON object.",
            )

        provider_id = payload.get("provider_id")
        task_id = payload.get("task_id")
        purpose = payload.get("purpose")
        if not isinstance(provider_id, str) or not provider_id.strip():
            provider_id = "UNKNOWN"
        if not isinstance(task_id, str) or not task_id.strip():
            task_id = "UNKNOWN"
        if not isinstance(purpose, dict):
            purpose = {}
        use_domain = purpose.get("classification")
        sector = purpose.get("sector")
        if not isinstance(use_domain, str):
            use_domain = "UNKNOWN"
        if not isinstance(sector, str):
            sector = "UNKNOWN"
        sector = sector.upper()

        if provider_id == "UNKNOWN":
            return self._decision(
                "REJECT_INVALID", provider_id, task_id, use_domain, sector,
                "Missing or invalid provider_id.",
            )

        if not isinstance(signature, str) or not _SIGNATURE_RE.fullmatch(signature):
            return self._decision(
                "REJECT_UNAUTHORIZED", provider_id, task_id, use_domain, sector,
                "Missing or malformed HMAC-SHA256 signature.",
            )

        try:
            payload_bytes = canonical_payload_bytes(payload)
        except (TypeError, ValueError, UnicodeError):
            return self._decision(
                "REJECT_INVALID", provider_id, task_id, use_domain, sector,
                "Payload cannot be serialized under the canonical JSON profile.",
            )

        try:
            key = self._key_provider.get_active_key(provider_id)
        except Exception:
            key = None
        if not isinstance(key, bytes) or len(key) < 32:
            return self._decision(
                "REJECT_UNAUTHORIZED", provider_id, task_id, use_domain, sector,
                "No usable provider key is available.",
            )

        expected = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature.lower()):
            return self._decision(
                "REJECT_UNAUTHORIZED", provider_id, task_id, use_domain, sector,
                "HMAC verification failed.",
            )


        # Timestamp and nonce are part of the authenticated payload.
        timestamp = payload.get("timestamp")
        nonce = payload.get("nonce")
        now = int(self._clock())
        if isinstance(timestamp, bool) or not isinstance(timestamp, int):
            return self._decision(
                "REJECT_INVALID", provider_id, task_id, use_domain, sector,
                "Signed timestamp must be an integer Unix timestamp.",
            )
        if abs(now - timestamp) > self._max_clock_skew_seconds:
            return self._decision(
                "REJECT_STALE", provider_id, task_id, use_domain, sector,
                "Signed timestamp is outside the permitted clock-skew window.",
            )
        if not isinstance(nonce, str) or not _NONCE_RE.fullmatch(nonce):
            return self._decision(
                "REJECT_INVALID", provider_id, task_id, use_domain, sector,
                "A cryptographically random hexadecimal nonce of at least 128 bits is required.",
            )
        try:
            claimed = self._replay_store.claim(provider_id, task_id, nonce)
        except Exception:
            claimed = False
        if not claimed:
            return self._decision(
                "REJECT_REPLAY_OR_STORE_FAILURE", provider_id, task_id, use_domain, sector,
                "Task ID or nonce was already used, or replay storage is unavailable.",
            )

        policy = evaluate_use_domain(use_domain)
        if policy.decision is PolicyDecision.BLOCK_RESTRICTED_DOMAIN:
            return self._decision(
                "BLOCK", provider_id, task_id, use_domain, sector,
                "Restricted use domain; task rejected before execution.",
            )
        if policy.decision is PolicyDecision.REVIEW_REQUIRED:
            return self._decision(
                "REVIEW_REQUIRED", provider_id, task_id, "UNKNOWN", sector,
                "Missing or unrecognized use domain; fail closed for manual review.",
            )

        if sector in _CRITICAL_SECTORS:
            return self._decision(
                "REVIEW_REQUIRED", provider_id, task_id, use_domain, sector,
                "Critical supply sector declared; independent human review is required.",
            )

        return self._decision(
            "REVIEW_REQUIRED", provider_id, task_id, use_domain, sector,
            "Authenticated declaration is eligible for review, not execution.",
        )
