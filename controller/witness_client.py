"""Test-only asynchronous witness mock.

This class never opens a socket and is not an external trust anchor. It exists
for deterministic integration tests. Production witness transport and key
custody must be implemented by a separately operated service.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from controller.state_monotonicity import DOMAIN, _canonical


class V91WitnessMockNetworkClient:
    """In-process Ed25519 witness simulator; no REST/gRPC network I/O occurs."""

    def __init__(self, *, key_id: str = "v91-test-witness"):
        if not isinstance(key_id, str) or not key_id.strip():
            raise ValueError("key_id must be non-empty")
        self.key_id = key_id
        self._private_key = Ed25519PrivateKey.generate()
        self.public_key = self._private_key.public_key()
        self._issued_challenges: set[str] = set()

    async def async_request_challenge(self, witness_endpoint: str) -> str:
        """Return a one-use challenge after validating the mock endpoint scheme."""
        if not isinstance(witness_endpoint, str) or not witness_endpoint.startswith(
            ("http://", "https://", "grpc://")
        ):
            raise ValueError("unsupported witness endpoint scheme")
        challenge = secrets.token_hex(32)
        self._issued_challenges.add(challenge)
        return challenge

    async def async_submit_state_for_signing(
        self,
        *,
        database_id: str,
        epoch: int,
        sequence_id: int,
        state_hash: str,
        challenge: str,
    ) -> dict[str, Any]:
        """Sign the exact heartbeat envelope expected by V91StateMonotonicityGuard."""
        if challenge not in self._issued_challenges:
            raise ValueError("challenge is unknown, expired, or already consumed")
        self._issued_challenges.remove(challenge)
        if not isinstance(database_id, str) or not database_id:
            raise ValueError("database_id is required")
        for name, value in (("epoch", epoch), ("sequence_id", sequence_id)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if (
            not isinstance(state_hash, str)
            or len(state_hash) != 64
            or any(c not in "0123456789abcdef" for c in state_hash)
        ):
            raise ValueError("state_hash must be lowercase SHA-256 hex")
        payload = {
            "schema_version": 1,
            "database_id": database_id,
            "epoch": epoch,
            "sequence": sequence_id,
            "state_root_hash": state_hash,
            "issued_at_utc": datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
            "challenge": challenge,
        }
        signature = self._private_key.sign(DOMAIN + _canonical(payload)).hex()
        return {
            "algorithm": "Ed25519",
            "key_id": self.key_id,
            "payload": payload,
            "signature": signature,
        }
