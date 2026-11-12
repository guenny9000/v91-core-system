"""Local emergency stop for V91-owned systems (Issue #70).

A tested, fail-closed kill-switch that ONLY affects the local V91 instance:
an atomic stop flag plus an HMAC-SHA256 hash-chained ledger. It never
touches external systems, networks, or third-party infrastructure.

SCRIPTED != INSTALLED: this module defines the primitive. Wiring it into
the actual runtime entry point is a separate, explicitly reviewed step.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

ACTIVATE_DOMAIN = b"V91-EMERGENCY-STOP-ACTIVATE-v1\x00"
RESET_DOMAIN = b"V91-EMERGENCY-STOP-RESET-v1\x00"
KEY_ENV = "V91_EMERGENCY_KEY"


class EmergencyStopError(RuntimeError):
    """The emergency-stop primitive cannot safely proceed."""


def _confirmation(key: bytes, domain: bytes, reason: str) -> str:
    return hmac.new(key, domain + reason.encode("utf-8"), hashlib.sha256).hexdigest()


def _canonical(record: dict) -> bytes:
    return json.dumps(
        record, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


class LocalEmergencyStop:
    """Atomic stop flag + HMAC-chained ledger; fail-closed on every error."""

    def __init__(
        self,
        flag_path: str | os.PathLike,
        ledger_path: str | os.PathLike,
        key: Optional[bytes] = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.flag_path = Path(os.path.abspath(Path(flag_path).expanduser()))
        self.ledger_path = Path(ledger_path).expanduser().resolve()
        if self.flag_path.resolve() == self.ledger_path.resolve():
            raise EmergencyStopError("flag and ledger paths must differ")
        resolved_key = key if key is not None else self._env_key()
        if not isinstance(resolved_key, bytes) or len(resolved_key) < 32:
            raise EmergencyStopError(
                "a V91_EMERGENCY_KEY of at least 32 bytes is required; refusing to start"
            )
        self._key = resolved_key
        self._clock = clock
        self.flag_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _env_key() -> Optional[bytes]:
        value = os.environ.get(KEY_ENV)
        return value.encode("utf-8") if isinstance(value, str) and value else None

    def _append_ledger(self, action: str, reason: str) -> dict:
        entries = self._read_ledger_or_empty()
        prev_hash = entries[-1]["entry_hmac"] if entries else "0" * 64
        record = {
            "seq": len(entries) + 1,
            "action": action,
            "reason": reason,
            "timestamp_utc": self._clock().isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "prev_hmac": prev_hash,
        }
        record["entry_hmac"] = hmac.new(
            self._key, _canonical(record), hashlib.sha256
        ).hexdigest()
        line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        with closing(open(self.ledger_path, "a", encoding="utf-8")) as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return record

    def _read_ledger_or_empty(self) -> list[dict]:
        if not self.ledger_path.exists():
            return []
        entries: list[dict] = []
        with closing(open(self.ledger_path, "r", encoding="utf-8")) as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise EmergencyStopError(f"corrupt ledger line: {exc}") from exc
        return entries

    def verify_ledger(self) -> bool:
        """Recompute the full HMAC chain; any deviation fails closed."""
        prev = "0" * 64
        for index, entry in enumerate(self._read_ledger_or_empty(), start=1):
            if entry.get("seq") != index or entry.get("prev_hmac") != prev:
                return False
            expected = {k: v for k, v in entry.items() if k != "entry_hmac"}
            mac = hmac.new(self._key, _canonical(expected), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(mac, str(entry.get("entry_hmac", ""))):
                return False
            prev = entry["entry_hmac"]
        return True

    def activate(self, reason: str, confirmation: str) -> dict:
        """Set the stop flag atomically; requires an HMAC confirmation bound to the reason."""
        if not isinstance(reason, str) or not reason.strip():
            raise EmergencyStopError("a non-empty reason is required")
        expected = _confirmation(self._key, ACTIVATE_DOMAIN, reason)
        if not isinstance(confirmation, str) or not hmac.compare_digest(expected, confirmation.lower()):
            raise EmergencyStopError("activation confirmation invalid; stop flag NOT set")
        tmp_fd, tmp_name = tempfile.mkstemp(dir=str(self.flag_path.parent), prefix=".stop-", suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                handle.write(reason)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.flag_path)
        except OSError as exc:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise EmergencyStopError(f"could not write stop flag: {exc}") from exc
        return self._append_ledger("ACTIVATE", reason)

    def is_stopped(self) -> tuple[bool, str]:
        """Fail-closed check: an unreadable or foreign-shaped flag counts as STOPPED."""
        return check_flag(self.flag_path)

    def reset(self, reason: str, confirmation: str) -> dict:
        """Remove the stop flag; only after the ledger chain verifies intact."""
        if not self.verify_ledger():
            raise EmergencyStopError("ledger chain verification failed; reset refused")
        if not self.flag_path.exists():
            raise EmergencyStopError("no stop flag present; nothing to reset")
        if not isinstance(reason, str) or not reason.strip():
            raise EmergencyStopError("a non-empty reason is required")
        expected = _confirmation(self._key, RESET_DOMAIN, reason)
        if not isinstance(confirmation, str) or not hmac.compare_digest(expected, confirmation.lower()):
            raise EmergencyStopError("reset confirmation invalid; stop flag kept")
        try:
            self.flag_path.unlink()
        except OSError as exc:
            raise EmergencyStopError(f"could not remove stop flag: {exc}") from exc
        return self._append_ledger("RESET", reason)


def check_flag(flag_path: str | os.PathLike) -> tuple[bool, str]:
    """Fail-closed flag check shared by writer and read-only reader."""
    path = Path(flag_path)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False, "RUNNING_NO_FLAG"
    except OSError:
        return True, "STOPPED_FLAG_UNREADABLE_FAIL_CLOSED"

    # A dangling symlink makes Path.exists() return False. Treat links and
    # non-regular filesystem objects as invalid stop state, never as RUNNING.
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        return True, "STOPPED_FLAG_INVALID_FAIL_CLOSED"

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return True, "STOPPED_FLAG_UNREADABLE_FAIL_CLOSED"
    if not isinstance(content, str):
        return True, "STOPPED_FLAG_INVALID_FAIL_CLOSED"
    return True, "STOPPED_FLAG_PRESENT"


class EmergencyStopFlagReader:
    """Read-only stop-flag check; no key required, never writes anything."""

    def __init__(self, flag_path: str | os.PathLike) -> None:
        self.flag_path = Path(flag_path).expanduser().resolve()

    def is_stopped(self) -> tuple[bool, str]:
        return check_flag(self.flag_path)
