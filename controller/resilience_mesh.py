#!/usr/bin/env python3
"""Local resilience mesh: peer register + restart verification (verify-only).

Portiert die tragfaehige Idee aus dem Fremd-Chat-Entwurf als ehrliches,
CI-getestetes Modul. Bewusst ANDERS als die Fiktion:

- KEIN Daemon, KEIN Port, KEIN Netzverkehr in diesem Modul. Peers sind
  registrierte Eintraege; der Transport bleibt injizierbar und opt-in.
- Fail-closed Key: das HMAC-Geheimnis kommt ausschliesslich explizit oder aus
  V91_MESH_KEY (mindestens 32 Bytes). Es gibt KEINEN Default-Key.
- Restart-Verifikation ist NUR Verifikation: ein injizierter Runner fuehrt
  ausschliesslich read-only Pruefbefehle aus. Neustarten/Isolieren gehoert
  dem Operator (DETECTION != AUTHORIZATION).
- Kompatibel mit den v99/os-Definitionen aus PR #60 (systemd/launchd/Taskplaner).
  VERIFIED_ACTIVE heisst: der Pruefbefehl hat es gemeldet. SHIPPING != INSTALLATION.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from typing import Any, Callable, Mapping, Optional

# Read-only verification commands per platform, aligned with v99/os unit names.
VERIFY_COMMANDS: dict[str, dict[str, list[str]]] = {
    "linux": {
        "v91-cycle.service": ["systemctl", "is-active", "v91-cycle.service"],
        "v91-cycle.timer": ["systemctl", "is-active", "v91-cycle.timer"],
    },
    "darwin": {
        "com.v91.cycle": ["launchctl", "list", "com.v91.cycle"],
    },
    "win32": {
        "V91-Cycle-Task": ["schtasks", "/query", "/tn", "V91-Cycle-Task"],
    },
}


class ResilienceMeshError(RuntimeError):
    """Mesh operation cannot be performed honestly."""


def resolve_key(explicit_key: str | None = None) -> bytes:
    """Fail-closed: no default key, minimum 32 bytes."""
    if explicit_key is not None:
        key = explicit_key
    else:
        key = os.environ.get("V91_MESH_KEY", "")
    if not isinstance(key, str) or len(key.encode("utf-8")) < 32:
        raise ResilienceMeshError(
            "V91_MESH_KEY missing or shorter than 32 bytes; refusing to start (fail-closed, no default key)"
        )
    return key.encode("utf-8")


class MeshRegister:
    """Local, HMAC-signed peer register. No network I/O happens here."""

    def __init__(self, key: bytes) -> None:
        if not isinstance(key, bytes) or len(key) < 32:
            raise ResilienceMeshError("key must be at least 32 bytes")
        self._key = key
        self._peers: dict[str, dict[str, Any]] = {}

    def register_peer(self, node_id: str, endpoint: str) -> dict[str, Any]:
        if not isinstance(node_id, str) or not node_id.strip():
            raise ResilienceMeshError("node_id must be a non-empty string")
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ResilienceMeshError("endpoint must be a non-empty string")
        record = {"node_id": node_id.strip(), "endpoint": endpoint.strip()}
        mac = hmac.new(self._key, json.dumps(record, sort_keys=True).encode("utf-8"), hashlib.sha256).hexdigest()
        entry = {**record, "mac": mac}
        self._peers[node_id.strip()] = entry
        return dict(entry)

    def verify_peer(self, entry: Mapping[str, Any]) -> bool:
        if not isinstance(entry, Mapping):
            return False
        supplied = entry.get("mac")
        record = {k: entry[k] for k in ("node_id", "endpoint") if k in entry}
        if set(record) != {"node_id", "endpoint"}:
            return False
        expected = hmac.new(self._key, json.dumps(record, sort_keys=True).encode("utf-8"), hashlib.sha256).hexdigest()
        return isinstance(supplied, str) and hmac.compare_digest(supplied, expected)

    def peers(self) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self._peers.values()]


# Runner contract: Callable[[list[str]], tuple[int, str, str]] -> (returncode, stdout, stderr)
Runner = Callable[[list[str]], "tuple[int, str, str]"]


class RestartVerifier:
    """Verify a local unit via an injected runner running a read-only command.

    Results are honest: VERIFIED_ACTIVE only from returncode 0, NOT_ACTIVE from
    a clean nonzero answer, UNKNOWN when the runner itself fails. The verifier
    never restarts, never kills, never reconfigures anything.
    """

    def __init__(self, runner: Runner, platform: str) -> None:
        if platform not in VERIFY_COMMANDS:
            raise ResilienceMeshError(f"unsupported platform: {platform!r}")
        self._runner = runner
        self._platform = platform

    def verification_command(self, unit: str) -> list[str]:
        commands = VERIFY_COMMANDS[self._platform]
        if unit not in commands:
            raise ResilienceMeshError(f"no read-only verification command for unit {unit!r} on {self._platform}")
        return list(commands[unit])

    def verify(self, unit: str) -> dict[str, Any]:
        command = self.verification_command(unit)
        try:
            returncode, stdout, stderr = self._runner(command)
        except Exception as exc:  # noqa: BLE001 – runner failure is UNKNOWN, never PASS
            return {"unit": unit, "status": "UNKNOWN", "reason": f"runner failed: {type(exc).__name__}"}
        if not isinstance(returncode, int):
            return {"unit": unit, "status": "UNKNOWN", "reason": "runner returned non-integer returncode"}
        if returncode == 0:
            return {"unit": unit, "status": "VERIFIED_ACTIVE", "command": command}
        return {
            "unit": unit,
            "status": "NOT_ACTIVE",
            "command": command,
            "reason": (stderr or stdout or "").strip()[:200] or f"returncode {returncode}",
        }


def verify_local_units(runner: Runner, platform: str,
                       units: Optional[list[str]] = None) -> dict[str, Any]:
    """Verify all (or selected) known units of a platform; fail-closed per unit."""
    verifier = RestartVerifier(runner, platform)
    known = list(VERIFY_COMMANDS[platform])
    selected = units if units is not None else known
    unknown = [unit for unit in selected if unit not in known]
    if unknown:
        raise ResilienceMeshError(f"unknown unit(s) for {platform}: {unknown}")
    return {
        "platform": platform,
        "units": [verifier.verify(unit) for unit in selected],
        "note": "VERIFIED_ACTIVE is a reported check result; SHIPPING != INSTALLATION and detection is not authorization",
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Local resilience mesh verify-only check (no network, read-only)")
    parser.add_argument("--platform", default=sys.platform if sys.platform in VERIFY_COMMANDS else
                        ("win32" if sys.platform.startswith("win") else "linux"))
    parser.add_argument("--units", nargs="*", default=None)
    args = parser.parse_args(argv)
    try:
        resolve_key()  # fail-closed: refuses without V91_MESH_KEY
        result = verify_local_units(_system_runner, args.platform, args.units)
    except ResilienceMeshError as exc:
        print(json.dumps({"status": "FAILED_CLOSED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def _system_runner(command: list[str]) -> "tuple[int, str, str]":
    import subprocess
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    return completed.returncode, completed.stdout, completed.stderr


if __name__ == "__main__":
    raise SystemExit(main())
