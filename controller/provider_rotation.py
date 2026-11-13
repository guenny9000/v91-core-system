"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Deterministische, fail-closed Provider-Auswahl (Vorbereitung fuer
Issue #239). Ehrliche Grenzen:

- SELECTION != ROTATION: dieses Modul waehlt aus und signiert die
  Entscheidung. Rotierte Credentials werden NUR vom Operator in den
  Provider-Konten (GitHub/Google/Stripe) - das kann kein Code hier.
- Health-Status sind gelieferte Messungen (injizierbar, mit
  Freshness-Fenster); fehlende/veraltete Messungen sind UNKNOWN und
  werden nie als gesund angenommen (UNKNOWN != HEALTHY).
- Kompatibel mit v99/security/key_rotation.py: der alte Provider
  bleibt aktiv, bis die neue Verbindung verifiziert ist; Widerruf
  erst nach erfolgreichem activate.
- Fail-closed Key: nur explizit oder V91_MESH_KEY, >= 32 Bytes,
  kein Default. Jede Entscheidung wird per HMAC-SHA256 ueber
  kanonisches JSON signiert.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping

MIN_KEY_BYTES = 32


class VerificationState(str, Enum):
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


class ProviderRotationError(RuntimeError):
    """Provider selection cannot be performed honestly."""


def resolve_key(explicit_key: str | None = None) -> bytes:
    """Fail-closed: no default key, minimum 32 bytes."""
    key = explicit_key if explicit_key is not None else os.environ.get("V91_MESH_KEY", "")
    if not isinstance(key, str) or len(key.encode("utf-8")) < MIN_KEY_BYTES:
        raise ProviderRotationError(
            f"key missing or shorter than {MIN_KEY_BYTES} bytes; refusing to operate (fail-closed, no default)"
        )
    return key.encode("utf-8")


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sign(key: bytes, payload: Mapping[str, Any]) -> str:
    return hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()


def _parse_iso(ts: str) -> datetime:
    if not isinstance(ts, str):
        raise ProviderRotationError("measured_at must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderRotationError(f"measured_at is not a valid ISO-8601 timestamp: {ts!r}") from exc
    if parsed.tzinfo is None:
        raise ProviderRotationError("measured_at must be timezone-aware ISO-8601")
    return parsed


@dataclass(frozen=True)
class HealthSignal:
    """One measured health observation for one provider."""
    provider: str
    healthy: bool
    measured_at: str
    source: str


def signals_from_records(records: Any) -> list[HealthSignal]:
    """Parse supplied health records; malformed entries fail closed."""
    if not isinstance(records, list):
        raise ProviderRotationError("health records must be a list")
    signals: list[HealthSignal] = []
    for record in records:
        if not isinstance(record, dict):
            raise ProviderRotationError("each health record must be an object")
        provider = record.get("provider")
        healthy = record.get("healthy")
        measured_at = record.get("measured_at")
        source = record.get("source")
        if not isinstance(provider, str) or not provider.strip():
            raise ProviderRotationError("health record needs a non-empty provider")
        if not isinstance(healthy, bool):
            raise ProviderRotationError(f"health record for {provider!r} needs a boolean 'healthy' (measured, not assumed)")
        if not isinstance(source, str) or not source.strip():
            raise ProviderRotationError(f"health record for {provider!r} needs a non-empty source")
        _parse_iso(measured_at)  # validates
        signals.append(HealthSignal(provider.strip(), healthy, measured_at, source.strip()))
    return signals


class ProviderRotationManager:
    """Deterministic selection from measured health signals only."""

    def __init__(self, providers: list[str], key: bytes,
                 now_provider: Callable[[], datetime] | None = None,
                 max_signal_age_seconds: float = 900.0) -> None:
        if not isinstance(key, bytes) or len(key) < MIN_KEY_BYTES:
            raise ProviderRotationError(f"key must be at least {MIN_KEY_BYTES} bytes")
        cleaned: list[str] = []
        for name in providers:
            if not isinstance(name, str) or not name.strip():
                raise ProviderRotationError("provider names must be non-empty strings")
            cleaned.append(name.strip())
        if len(set(cleaned)) != len(cleaned):
            raise ProviderRotationError("duplicate provider names are not allowed")
        if not cleaned:
            raise ProviderRotationError("at least one provider must be configured")
        self._providers = sorted(cleaned)
        self._key = key
        self._now = now_provider or (lambda: datetime.now(timezone.utc))
        self._max_age = float(max_signal_age_seconds)

    def select_active_provider(self, signals: list[HealthSignal]) -> dict[str, Any]:
        """Pick the first (alphabetically) provider with a fresh, measured healthy=True signal.

        No fresh measured signal for a provider -> that provider is UNKNOWN,
        never healthy. If no provider is verifiably healthy, the result is
        UNKNOWN with no active provider and nothing is signed as VERIFIED.
        """
        now = self._now()
        health: dict[str, str] = {}
        for signal in signals:
            if signal.provider not in self._providers:
                raise ProviderRotationError(f"health signal for unknown provider {signal.provider!r}")
            try:
                measured = _parse_iso(signal.measured_at)
            except ProviderRotationError:
                health[signal.provider] = "UNKNOWN"
                continue
            age = (now - measured).total_seconds()
            if age < 0 or age > self._max_age:
                health[signal.provider] = "UNKNOWN"
                continue
            health[signal.provider] = "VERIFIED_HEALTHY" if signal.healthy else "VERIFIED_UNHEALTHY"

        active: str | None = None
        for name in self._providers:
            if health.get(name) == "VERIFIED_HEALTHY":
                active = name
                break

        if active is not None:
            state = VerificationState.VERIFIED
            evidence = f"fresh measured healthy signal for {active!r} (source-bound, age <= {self._max_age:.0f}s)"
        elif all(health.get(name) == "VERIFIED_UNHEALTHY" for name in self._providers):
            state = VerificationState.UNKNOWN
            evidence = "all providers measured unhealthy; no active provider selected (fail-closed)"
        else:
            state = VerificationState.UNKNOWN
            evidence = "no fresh measured healthy signal for any provider (UNKNOWN != HEALTHY); nothing selected"

        decision = {
            "active_provider": active,
            "health": {name: health.get(name, "UNKNOWN") for name in self._providers},
            "state": state.value,
            "evidence": evidence,
            "decided_at": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "note": "SELECTION != ROTATION: credential rotation remains an operator action; old provider stays active until new one is verified (v99 key_rotation contract)",
        }
        signature = _sign(self._key, decision)
        return {**decision, "signature": signature}

    @classmethod
    def verify_decision(cls, key: bytes, decision: Mapping[str, Any]) -> bool:
        if not isinstance(decision, Mapping):
            return False
        supplied = decision.get("signature")
        payload = {k: v for k, v in decision.items() if k != "signature"}
        if not isinstance(supplied, str):
            return False
        return hmac.compare_digest(supplied, _sign(key, payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic fail-closed provider selection (SELECTION != ROTATION)")
    parser.add_argument("--providers", nargs="+", required=True)
    parser.add_argument("--health-json", required=True,
                        help="JSON file with a list of measured health records "
                             "[{provider, healthy, measured_at, source}]")
    args = parser.parse_args(argv)
    try:
        key = resolve_key()
        records = json.loads(Path(args.health_json).expanduser().resolve().read_text(encoding="utf-8"))
        signals = signals_from_records(records)
        manager = ProviderRotationManager(args.providers, key)
        result = manager.select_active_provider(signals)
    except (ProviderRotationError, OSError, ValueError) as exc:
        print(json.dumps({"status": "FAILED_CLOSED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["state"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
