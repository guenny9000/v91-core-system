#!/usr/bin/env python3
"""V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
---------------------------------------------------------------------
Grundversorgungs-/Notfallkommunikations-Check als Betreiber-Skript.
Prueft ein JSON-Manifest zur Grundversorgung (z. B. Notvorrat Wasser,
Nahrung, Verbandskasten, Kommunikationsweg), bewertet fehlende,
korrupte oder unklare Angaben fail-closed (UNKNOWN != PASS, nichts
wird als 'alles ok' angenommen), dedupliziert Alerts ueber SHA-256,
schreibt append-only mit fsync in einen EIGENEN Alert-Ledger
(emergency_alerts.jsonl; NICHT der kern_bridge-Inbox #496) und sendet
optional, nur bei neuen Alerts, an einen Betreiber-Webhook.

Fremdbeitrag 25.11.2026 (Office-Agent-Entwurf), PRUEBFUND vor Uebernahme:
- keine der genannten Dateien existierte im Repo (404) => es entsteht keine
  Dopplung, aber auch KEINE Uebernahme von behaupteten Zustaenden.
- DER ENTWURF SCHRIEB IN 'v91_bridge_inbox.jsonl' - das ist der
  LEDGER VON KERN_BRIDGE (#496). Schreiben heterogener Alert-Records in
  fremde Ledger-Semantik waere Sabotage des Intake-Vertraegens
  [NO_DUPLICATE_SYSTEMS]; korrigiert: eigener Ledger-Name.

Ehrliche Grenzen: MANIFEST == BETREIBER-ANGABE != GEPRUEFTE REALITAET
(CLAIM != EVIDENCE), CHECK != INTERVENTION (keine Aktion, kein Daemon,
kein Prozess-Control; Scripts != Installation), ALERT != BERECHTIGUNG,
WEBHOOK == OPTIONALER AUSGANG unter Betreiber-Freigabe via Env-Variable
(AUSGANG != EINGRIFF, Netzwerk bleibt Flusskontrolle des Betreibers),
DEDUP == HASH GLEICHER KERNDATEN != SEMANTISCHE GLEICHHEIT,
EXIT 0 = OK, EXIT 1 = Befund (MISSING/UNKNOWN), EXIT 2 = Ledgerfehler.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib import error, request

DEFAULT_MANIFEST_PATH = Path("config/emergency_manifest.json")
DEFAULT_LEDGER_PATH = Path("emergency_alerts.jsonl")
DEFAULT_REQUIRED_ITEMS = ["food", "water", "medical_kit", "comms"]
MAX_TEXT_LEN = 240
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_text(value: Any, max_len: int = MAX_TEXT_LEN) -> str:
    if value is None:
        return "UNKNOWN"
    text = str(value)
    text = CONTROL_CHARS_RE.sub(" ", text)
    text = " ".join(text.split()).strip()
    if not text:
        return "UNKNOWN"
    return text[:max_len]


def _parse_required_items(raw_env: str | None) -> list[str]:
    if not raw_env:
        return list(DEFAULT_REQUIRED_ITEMS)
    try:
        parsed = json.loads(raw_env)
        if isinstance(parsed, list) and parsed:
            cleaned = [_sanitize_text(item, 64).lower() for item in parsed]
            valid = [c for c in cleaned if c and c != "unknown"]
            if valid:
                return valid
    except json.JSONDecodeError:
        pass
    parts = [_sanitize_text(p, 64).lower() for p in raw_env.split(",")]
    valid = [p for p in parts if p and p != "unknown"]
    return valid if valid else list(DEFAULT_REQUIRED_ITEMS)


def _parse_timeout_seconds(raw_val: str | None, default: float = 4.0) -> float:
    if not raw_val:
        return default
    try:
        val = float(raw_val)
        if 0.5 <= val <= 30.0:
            return val
    except ValueError:
        pass
    return default


def _load_manifest(manifest_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not manifest_path.exists() or not manifest_path.is_file():
        return None, "manifest_missing"
    try:
        raw = manifest_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None, "manifest_not_object"
        return data, None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, "manifest_invalid"


def _evaluate_item(item_name: str, raw_entry: Any) -> dict[str, Any]:
    """Bewertet einen Versorgungs- oder Kommunikationsposten fail-closed.

    bool: True -> OK, False -> MISSING. dict: 'status' ok/available/
    ready -> OK, missing/empty/out/down -> MISSING (days_remaining <= 0
    bei ok -> MISSING), alles andere (auch Strukturfehler) -> UNKNOWN.
    """
    if raw_entry is None:
        return {"item": item_name, "state": "UNKNOWN",
                "reason": "entry_missing", "days_remaining": None,
                "note": "UNKNOWN"}

    if isinstance(raw_entry, bool):
        # bool MUSS vor int geprueft werden (bool ist int-Subtyp).
        return {"item": item_name,
                "state": "OK" if raw_entry else "MISSING",
                "reason": "boolean_ok" if raw_entry else "boolean_false",
                "days_remaining": None, "note": "UNKNOWN"}

    days_remaining: float | None = None
    if isinstance(raw_entry, dict):
        raw_status = _sanitize_text(raw_entry.get("status", ""), 32).lower()
        note = _sanitize_text(raw_entry.get("note", "UNKNOWN"), 120)
        raw_days = raw_entry.get("days_remaining")
        if raw_days is not None:
            if isinstance(raw_days, bool):
                days_remaining = None
            else:
                try:
                    num = float(raw_days)
                    if num >= 0:
                        days_remaining = round(num, 2)
                except (TypeError, ValueError):
                    days_remaining = None
        if raw_status in ("ok", "available", "ready"):
            if days_remaining is not None and days_remaining <= 0:
                return {"item": item_name, "state": "MISSING",
                        "reason": "zero_days_remaining",
                        "days_remaining": days_remaining, "note": note}
            return {"item": item_name, "state": "OK", "reason": "status_ok",
                    "days_remaining": days_remaining, "note": note}
        if raw_status in ("missing", "empty", "out", "down"):
            return {"item": item_name, "state": "MISSING",
                    "reason": "status_missing",
                    "days_remaining": days_remaining, "note": note}
        return {"item": item_name, "state": "UNKNOWN",
                "reason": "invalid_or_unknown_status",
                "days_remaining": days_remaining, "note": note}

    return {"item": item_name, "state": "UNKNOWN",
            "reason": "unsupported_entry_type", "days_remaining": None,
            "note": "UNKNOWN"}


def _compute_dedup_hash(alert_core: dict[str, Any]) -> str:
    canonical = json.dumps(alert_core, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_existing_hashes(ledger_path: Path) -> set[str]:
    hashes: set[str] = set()
    if not ledger_path.exists() or not ledger_path.is_file():
        return hashes
    try:
        with ledger_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        h = obj.get("dedup_sha256")
                        if isinstance(h, str) and len(h) == 64:
                            hashes.add(h)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return hashes


def _append_ledger_fsync(ledger_path: Path, record: dict[str, Any]) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(record, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True) + "\n"
    encoded = serialized.encode("utf-8")
    fd = os.open(str(ledger_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                 0o644)
    try:
        view = memoryview(encoded)
        total_written = 0
        while total_written < len(encoded):
            written = os.write(fd, view[total_written:])
            if written <= 0:
                raise OSError("short_write_to_ledger")
            total_written += written
        os.fsync(fd)
    finally:
        os.close(fd)


def _send_webhook_with_timeout(webhook_url: str, payload: dict[str, Any],
                               timeout_s: float) -> tuple[bool, str]:
    if not webhook_url.startswith(("https://", "http://")):
        return False, "invalid_webhook_scheme"
    body = json.dumps(payload, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")
    req = request.Request(url=webhook_url, data=body, headers={
        "Content-Type": "application/json",
        "User-Agent": "V91-Emergency-Supply/1.0"}, method="POST")
    try:
        with request.urlopen(req, timeout=timeout_s) as resp:
            status = int(getattr(resp, "status", 200))
            if 200 <= status < 300:
                return True, "http_%d" % status
            return False, "http_non_2xx_%d" % status
    except error.HTTPError as exc:
        return False, "http_error_%d" % exc.code
    except (error.URLError, TimeoutError, OSError) as exc:
        return False, "network_error_%s" % type(exc).__name__


def run_check() -> int:
    manifest_path = Path(os.environ.get(
        "EMERGENCY_MANIFEST", str(DEFAULT_MANIFEST_PATH)))
    ledger_path = Path(os.environ.get(
        "EMERGENCY_LEDGER", str(DEFAULT_LEDGER_PATH)))
    required_items = _parse_required_items(os.environ.get("EMERGENCY_REQUIRED_ITEMS"))
    webhook_url = os.environ.get("EMERGENCY_WEBHOOK_URL", "").strip()
    webhook_timeout_s = _parse_timeout_seconds(
        os.environ.get("EMERGENCY_WEBHOOK_TIMEOUT_S"), 4.0)

    checked_at = _utc_now_iso()
    manifest, manifest_err = _load_manifest(manifest_path)

    if manifest is None:
        evaluations = [{"item": it, "state": "UNKNOWN",
                        "reason": manifest_err or "manifest_unavailable",
                        "days_remaining": None, "note": "UNKNOWN"}
                       for it in required_items]
    else:
        evaluations = [_evaluate_item(it, manifest.get(it))
                       for it in required_items]

    problem_items = [e for e in evaluations if e["state"] != "OK"]
    overall = "OK" if not problem_items else (
        "MISSING" if any(e["state"] == "MISSING" for e in problem_items)
        else "UNKNOWN")

    if not problem_items:
        print(json.dumps({"status": "OK", "checked_at": checked_at,
                          "required_count": len(required_items),
                          "ledger_appended": False}, ensure_ascii=True))
        return 0

    alert_core = {
        "schema": "v91.emergency_supply.v1",
        "overall_status": overall,
        "manifest_error": manifest_err or "NONE",
        "incidents": [{"item": p["item"], "state": p["state"],
                       "reason": p["reason"],
                       "days_remaining": p["days_remaining"]}
                      for p in problem_items],
    }
    dedup_hash = _compute_dedup_hash(alert_core)
    is_duplicate = dedup_hash in _load_existing_hashes(ledger_path)

    uas_payload = {
        "type": "V91_EMERGENCY_SUPPLY_ALERT",
        "severity": "HIGH" if overall == "MISSING" else "WARN_UNKNOWN",
        "timestamp_utc": checked_at,
        "summary": _sanitize_text(
            "status=%s; issues=%s" % (
                overall,
                ",".join("%s:%s" % (p["item"], p["state"])
                         for p in problem_items))),
        "core": alert_core,
    }
    ledger_record = {
        "recorded_at_utc": checked_at,
        "dedup_sha256": dedup_hash,
        "duplicate_suppressed": is_duplicate,
        "uas_alert": uas_payload,
    }
    ledger_written = False
    if not is_duplicate:
        try:
            _append_ledger_fsync(ledger_path, ledger_record)
            ledger_written = True
        except OSError as exc:
            print(json.dumps({"status": "ERROR_LEDGER_WRITE",
                              "reason": type(exc).__name__,
                              "dedup_sha256": dedup_hash},
                             ensure_ascii=True), file=sys.stderr)
            return 2

    webhook_result = "skipped_no_url"
    if webhook_url and not is_duplicate:
        ok, info = _send_webhook_with_timeout(
            webhook_url, uas_payload, webhook_timeout_s)
        webhook_result = "%s:%s" % ("sent" if ok else "failed", info)
    elif webhook_url and is_duplicate:
        webhook_result = "skipped_duplicate"

    print(json.dumps({
        "status": overall, "checked_at": checked_at,
        "dedup_sha256": dedup_hash,
        "duplicate_suppressed": is_duplicate,
        "ledger_written": ledger_written,
        "webhook": webhook_result,
        "issue_count": len(problem_items)}, ensure_ascii=True))
    return 1


if __name__ == "__main__":
    sys.exit(run_check())
