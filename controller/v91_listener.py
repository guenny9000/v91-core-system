#!/usr/bin/env python3
"""
v91 Interop Listener – SafeSignal Protocol, HITL Queue, Audit Logging
Production-ready listener for the v91-core-system interop bus.

Architecture:
  Inbox (JSON files)
    → SafeSignal Verify (HMAC-SHA256)
    → Schema Validate
    → Route: Ledger | HITL Queue | Quarantine
    → Audit Log (append-only)

Environment:
  V91_DB_PATH         – SQLite DB path  (default: /app/data/v91_independent_state.db)
  V91_INBOX_PATH      – Inbox directory  (default: /app/data/inbox)
  V91_SECRET_KEY_PATH – Path to HMAC key file (default: /app/secrets/v91_secret.key)
  V91_POLL_INTERVAL   – Seconds between polls (default: 5)
  V91_HITL_THRESHOLD  – Confidence threshold below which events go to HITL (default: 0.75)
"""

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] v91-listener %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("v91-listener")

# ── Config ───────────────────────────────────────────────────────────────────

DB_PATH = os.environ.get("V91_DB_PATH", "/app/data/v91_independent_state.db")
INBOX_PATH = os.environ.get("V91_INBOX_PATH", "/app/data/inbox")
SECRET_KEY_PATH = os.environ.get("V91_SECRET_KEY_PATH", "/app/secrets/v91_secret.key")
POLL_INTERVAL = int(os.environ.get("V91_POLL_INTERVAL", "5"))
HITL_THRESHOLD = float(os.environ.get("V91_HITL_THRESHOLD", "0.75"))

# ── SafeSignal Protocol ───────────────────────────────────────────────────────

def load_secret_key() -> bytes:
    """Load HMAC secret key from file.  Falls back to env var V91_SECRET_KEY."""
    key_path = Path(SECRET_KEY_PATH)
    if key_path.exists():
        raw = key_path.read_bytes().strip()
        return raw
    env_key = os.environ.get("V91_SECRET_KEY", "")
    if env_key:
        return env_key.encode()
    raise RuntimeError(
        f"SafeSignal key not found at {SECRET_KEY_PATH} and V91_SECRET_KEY is not set"
    )


def compute_signature(payload: bytes, key: bytes) -> str:
    """Compute HMAC-SHA256 signature over raw payload bytes."""
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, provided_sig: str, key: bytes) -> bool:
    """Constant-time HMAC-SHA256 signature verification (SafeSignal protocol)."""
    expected = compute_signature(payload, key)
    return hmac.compare_digest(expected, provided_sig)


def safesignal_check(event: dict, raw_bytes: bytes, key: bytes) -> tuple[bool, str]:
    """
    Validate an event against the SafeSignal protocol.
    Returns (valid: bool, reason: str).

    Expected event envelope:
      {
        "safesignal": {
          "version": "1",
          "sig": "<hmac-sha256-hex>",
          "ts":  "<iso8601-utc>"
        },
        "payload": { ... }
      }
    """
    ss = event.get("safesignal")
    if not ss:
        return False, "missing safesignal envelope"

    version = ss.get("version", "")
    if version != "1":
        return False, f"unsupported SafeSignal version: {version!r}"

    provided_sig = ss.get("sig", "")
    if not provided_sig:
        return False, "safesignal.sig is empty"

    # The signature is over the canonical JSON of the 'payload' field only
    payload_bytes = json.dumps(event.get("payload", {}), sort_keys=True, separators=(",", ":")).encode()
    if not verify_signature(payload_bytes, provided_sig, key):
        return False, "signature mismatch"

    # Replay-attack guard: reject events older than 5 minutes
    ts_str = ss.get("ts", "")
    if ts_str:
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            age_seconds = (datetime.now(timezone.utc) - ts).total_seconds()
            if age_seconds > 300:
                return False, f"event too old: {age_seconds:.0f}s"
            if age_seconds < -60:
                return False, f"event timestamp in future: {age_seconds:.0f}s"
        except ValueError:
            return False, f"invalid timestamp: {ts_str!r}"

    return True, "ok"


# ── Schema Validation ─────────────────────────────────────────────────────────

REQUIRED_PAYLOAD_FIELDS = {"event_type", "source", "data"}


def validate_payload(payload: dict) -> tuple[bool, str]:
    """Basic schema validation for event payloads."""
    missing = REQUIRED_PAYLOAD_FIELDS - payload.keys()
    if missing:
        return False, f"missing payload fields: {sorted(missing)}"
    event_type = payload.get("event_type", "")
    if not isinstance(event_type, str) or not event_type.strip():
        return False, "payload.event_type must be a non-empty string"
    return True, "ok"


def compute_confidence(payload: dict) -> float:
    """
    Heuristic confidence score [0.0 – 1.0] for routing to HITL vs. auto-accept.
    Real implementations can use ML models here.
    """
    score = 1.0
    data = payload.get("data", {})
    # Penalise events with unknown or risky event types
    risky_types = {"delete", "override", "force_merge", "escalate", "admin_action"}
    if payload.get("event_type", "").lower() in risky_types:
        score -= 0.4
    # Penalise large or deeply nested payloads (may indicate injection)
    if len(json.dumps(data)) > 4096:
        score -= 0.2
    # Penalise if source is missing or 'unknown'
    if not payload.get("source") or payload.get("source") == "unknown":
        score -= 0.3
    return max(0.0, min(1.0, score))


# ── Database Helpers ──────────────────────────────────────────────────────────

def get_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def insert_ledger(conn: sqlite3.Connection, event_id: str, event_type: str,
                  source: str, payload_json: str, raw_hash: str) -> None:
    conn.execute(
        """INSERT INTO v91_ledger
           (event_id, event_type, source, payload_json, raw_hash, received_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_id, event_type, source, payload_json, raw_hash, _utcnow()),
    )


def insert_quarantine(conn: sqlite3.Connection, event_id: str,
                      reason: str, raw_json: str, raw_hash: str) -> None:
    conn.execute(
        """INSERT INTO v91_quarantine
           (event_id, reason, raw_json, raw_hash, quarantined_at)
           VALUES (?, ?, ?, ?, ?)""",
        (event_id, reason, raw_json, raw_hash, _utcnow()),
    )


def insert_hitl_queue(conn: sqlite3.Connection, event_id: str,
                      event_type: str, source: str,
                      payload_json: str, confidence: float) -> None:
    conn.execute(
        """INSERT INTO v91_hitl_queue
           (event_id, event_type, source, payload_json, confidence, status, queued_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
        (event_id, event_type, source, payload_json, confidence, _utcnow()),
    )


def insert_audit_log(conn: sqlite3.Connection, event_id: str,
                     action: str, detail: str) -> None:
    conn.execute(
        """INSERT INTO v91_audit_log
           (log_id, event_id, action, detail, logged_at)
           VALUES (?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), event_id, action, detail, _utcnow()),
    )


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Event Processing Pipeline ─────────────────────────────────────────────────

def process_file(file_path: Path, key: bytes, db_path: str) -> None:
    """End-to-end processing of one inbox file."""
    raw_bytes = file_path.read_bytes()
    raw_hash = hashlib.sha256(raw_bytes).hexdigest()
    event_id = str(uuid.uuid4())

    logger.info("Processing %s  sha256=%s", file_path.name, raw_hash[:16])

    try:
        event = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        _quarantine_file(file_path, event_id, f"json_parse_error: {exc}",
                         raw_bytes.decode(errors="replace"), raw_hash, db_path)
        return

    # ── SafeSignal verification ───────────────────────────────────────────────
    valid, reason = safesignal_check(event, raw_bytes, key)
    if not valid:
        _quarantine_file(file_path, event_id, f"safesignal_fail: {reason}",
                         raw_bytes.decode(errors="replace"), raw_hash, db_path)
        return

    payload = event.get("payload", {})

    # ── Payload schema validation ─────────────────────────────────────────────
    schema_ok, schema_reason = validate_payload(payload)
    if not schema_ok:
        _quarantine_file(file_path, event_id, f"schema_error: {schema_reason}",
                         raw_bytes.decode(errors="replace"), raw_hash, db_path)
        return

    confidence = compute_confidence(payload)
    event_type = payload["event_type"]
    source = payload["source"]
    payload_json = json.dumps(payload, sort_keys=True)

    with get_db(db_path) as conn:
        if confidence < HITL_THRESHOLD:
            # ── Route to HITL queue ───────────────────────────────────────────
            insert_hitl_queue(conn, event_id, event_type, source, payload_json, confidence)
            insert_audit_log(conn, event_id, "hitl_queued",
                             f"confidence={confidence:.3f} threshold={HITL_THRESHOLD}")
            logger.info("HITL QUEUED  event_id=%s type=%s confidence=%.3f",
                        event_id, event_type, confidence)
        else:
            # ── Route to ledger (auto-accept) ─────────────────────────────────
            insert_ledger(conn, event_id, event_type, source, payload_json, raw_hash)
            insert_audit_log(conn, event_id, "ledger_accepted",
                             f"confidence={confidence:.3f}")
            logger.info("LEDGER       event_id=%s type=%s confidence=%.3f",
                        event_id, event_type, confidence)
        conn.commit()

    # Remove processed file from inbox to prevent re-processing
    file_path.unlink()
    logger.debug("Removed processed file: %s", file_path.name)


def _quarantine_file(file_path: Path, event_id: str, reason: str,
                     raw_text: str, raw_hash: str, db_path: str) -> None:
    """Write event to quarantine table and remove from inbox."""
    logger.warning("QUARANTINE   event_id=%s reason=%s file=%s",
                   event_id, reason, file_path.name)
    try:
        with get_db(db_path) as conn:
            insert_quarantine(conn, event_id, reason, raw_text, raw_hash)
            insert_audit_log(conn, event_id, "quarantined", reason)
            conn.commit()
    except sqlite3.Error as exc:
        logger.error("DB error during quarantine: %s", exc)
    try:
        file_path.unlink()
    except OSError as exc:
        logger.error("Could not remove quarantined file %s: %s", file_path, exc)


# ── Inbox Watcher ─────────────────────────────────────────────────────────────

def watch_inbox(inbox_path: str, key: bytes, db_path: str) -> None:
    """Poll inbox directory and process all .json files."""
    inbox = Path(inbox_path)
    inbox.mkdir(parents=True, exist_ok=True)

    json_files = sorted(inbox.glob("*.json"))
    if not json_files:
        return

    logger.info("Found %d file(s) in inbox", len(json_files))
    for f in json_files:
        try:
            process_file(f, key, db_path)
        except Exception as exc:
            logger.error("Unhandled error processing %s: %s", f.name, exc, exc_info=True)


# ── Health Check ──────────────────────────────────────────────────────────────

def health_check(db_path: str) -> bool:
    """Verify DB connectivity; used by Docker HEALTHCHECK."""
    try:
        with get_db(db_path) as conn:
            conn.execute("SELECT 1 FROM v91_ledger LIMIT 1")
        return True
    except sqlite3.Error:
        return False


# ── Main Loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("Starting v91 Interop Listener (SafeSignal v1)")
    logger.info("DB=%s  INBOX=%s  POLL=%ss  HITL_THRESHOLD=%.2f",
                DB_PATH, INBOX_PATH, POLL_INTERVAL, HITL_THRESHOLD)

    # Ensure DB exists (schema must be initialised separately via init_listener_db.sql)
    if not Path(DB_PATH).exists():
        logger.warning("DB not found at %s – will retry each poll cycle", DB_PATH)

    key: bytes | None = None
    try:
        key = load_secret_key()
        logger.info("SafeSignal key loaded (%d bytes)", len(key))
    except RuntimeError as exc:
        logger.critical("Cannot start without SafeSignal key: %s", exc)
        raise SystemExit(1)

    while True:
        if Path(DB_PATH).exists():
            try:
                watch_inbox(INBOX_PATH, key, DB_PATH)
            except Exception as exc:
                logger.error("Poll cycle error: %s", exc, exc_info=True)
        else:
            logger.warning("DB still missing – skipping poll cycle")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
