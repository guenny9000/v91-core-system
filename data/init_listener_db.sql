-- v91 Interop Listener – Database Schema
-- Run once before starting the listener:
--   sqlite3 /app/data/v91_independent_state.db < data/init_listener_db.sql

-- ── Ledger (auto-accepted events) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS v91_ledger (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     TEXT    NOT NULL UNIQUE,
    event_type   TEXT    NOT NULL,
    source       TEXT    NOT NULL,
    payload_json TEXT    NOT NULL,
    raw_hash     TEXT    NOT NULL,
    received_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ledger_event_type ON v91_ledger (event_type);
CREATE INDEX IF NOT EXISTS idx_ledger_received_at ON v91_ledger (received_at);

-- ── Quarantine (rejected / invalid events) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS v91_quarantine (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT    NOT NULL UNIQUE,
    reason          TEXT    NOT NULL,
    raw_json        TEXT    NOT NULL,
    raw_hash        TEXT    NOT NULL,
    quarantined_at  TEXT    NOT NULL,
    reviewed        INTEGER NOT NULL DEFAULT 0,
    reviewed_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_quarantine_reason ON v91_quarantine (reason);
CREATE INDEX IF NOT EXISTS idx_quarantine_reviewed ON v91_quarantine (reviewed);

-- ── HITL Queue (Human-in-the-Loop – low confidence events) ───────────────────
CREATE TABLE IF NOT EXISTS v91_hitl_queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     TEXT    NOT NULL UNIQUE,
    event_type   TEXT    NOT NULL,
    source       TEXT    NOT NULL,
    payload_json TEXT    NOT NULL,
    confidence   REAL    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
    queued_at    TEXT    NOT NULL,
    resolved_at  TEXT,
    resolved_by  TEXT,
    resolution_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_hitl_status ON v91_hitl_queue (status);
CREATE INDEX IF NOT EXISTS idx_hitl_queued_at ON v91_hitl_queue (queued_at);

-- ── Audit Log (append-only) ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS v91_audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id    TEXT    NOT NULL UNIQUE,
    event_id  TEXT    NOT NULL,
    action    TEXT    NOT NULL,  -- ledger_accepted | hitl_queued | quarantined
    detail    TEXT    NOT NULL,
    logged_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_event_id ON v91_audit_log (event_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON v91_audit_log (action);
CREATE INDEX IF NOT EXISTS idx_audit_logged_at ON v91_audit_log (logged_at);

-- ── Lernblock (optional: educational event tracking) ─────────────────────────
CREATE TABLE IF NOT EXISTS v91_lernblock (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    block_id    TEXT    NOT NULL UNIQUE,
    event_id    TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    description TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);
