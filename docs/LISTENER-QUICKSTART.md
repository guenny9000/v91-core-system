# LISTENER QUICKSTART – v91 Interop Listener

Get the v91-interop-listener running in **under 5 minutes**.

---

## Prerequisites

- Docker & Docker Compose installed
- `sqlite3` CLI available (for DB init)
- Repository cloned locally

---

## Step 1 – Configure environment

```bash
cp .env.example .env
# Edit .env to set V91_SECRET_KEY or mount a key file
```

For a quick local test you can use an inline key:

```bash
# In .env
V91_SECRET_KEY=my-local-dev-secret-change-in-prod
```

> **Production:** Mount a key file at `./secrets/v91_secret.key` (read-only).
> Never commit the key to version control.

---

## Step 2 – Initialise the database

```bash
mkdir -p data
sqlite3 ./data/v91_independent_state.db < data/init_listener_db.sql
# Expected: no output = success
```

---

## Step 3 – Start the listener

```bash
docker compose up --build -d v91-listener
docker logs -f v91-listener
```

Expected output:

```
2026-01-01T12:00:00Z [INFO] v91-listener Starting v91 Interop Listener (SafeSignal v1)
2026-01-01T12:00:00Z [INFO] v91-listener DB=/app/data/v91_independent_state.db  INBOX=/app/data/inbox  POLL=5s  HITL_THRESHOLD=0.75
2026-01-01T12:00:00Z [INFO] v91-listener SafeSignal key loaded (32 bytes)
```

---

## Step 4 – Send a test event

### Generate a valid signed event

```python
# /tmp/gen_test_event.py
import hashlib, hmac, json, time
from datetime import datetime, timezone

SECRET = b"my-local-dev-secret-change-in-prod"
payload = {
    "event_type": "user_login",
    "source": "web-frontend",
    "data": {"user_id": "u-001", "ip": "192.168.1.1"}
}
payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
sig = hmac.new(SECRET, payload_bytes, hashlib.sha256).hexdigest()

event = {
    "safesignal": {
        "version": "1",
        "sig": sig,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    },
    "payload": payload
}
print(json.dumps(event, indent=2))
```

```bash
python /tmp/gen_test_event.py > ./data/inbox/test_event_001.json
```

Watch the logs – within 5 seconds you should see:

```
[INFO] v91-listener LEDGER       event_id=<uuid> type=user_login confidence=1.000
```

### Test HITL routing

Use `event_type: "delete"` – confidence drops below the threshold and the event is queued for human review:

```bash
# edit the payload event_type to "delete" and regenerate the signature
```

Logs will show:

```
[INFO] v91-listener HITL QUEUED  event_id=<uuid> type=delete confidence=0.600
```

### Test quarantine

Drop a file with an invalid signature or malformed JSON:

```bash
echo '{"not": "valid"}' > ./data/inbox/bad_event.json
```

Logs:

```
[WARNING] v91-listener QUARANTINE   event_id=<uuid> reason=safesignal_fail: missing safesignal envelope
```

---

## Step 5 – Verify audit trail

```bash
sqlite3 ./data/v91_independent_state.db \
  "SELECT action, detail, logged_at FROM v91_audit_log ORDER BY logged_at DESC LIMIT 10;"
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `SafeSignal key not found` | Set `V91_SECRET_KEY` in `.env` or mount `./secrets/v91_secret.key` |
| `DB still missing – skipping poll` | Run `sqlite3 ... < data/init_listener_db.sql` |
| Events stay in inbox | Check signature generation – ensure same secret both sides |
| Healthcheck fails | Confirm DB is initialised and `v91_ledger` table exists |

---

## DB Inspection Cheat Sheet

```bash
# Ledger (accepted events)
sqlite3 ./data/v91_independent_state.db "SELECT * FROM v91_ledger ORDER BY received_at DESC LIMIT 5;"

# HITL queue (pending human review)
sqlite3 ./data/v91_independent_state.db "SELECT * FROM v91_hitl_queue WHERE status='pending';"

# Quarantine
sqlite3 ./data/v91_independent_state.db "SELECT event_id, reason, quarantined_at FROM v91_quarantine ORDER BY quarantined_at DESC LIMIT 5;"

# Audit log
sqlite3 ./data/v91_independent_state.db "SELECT action, COUNT(*) FROM v91_audit_log GROUP BY action;"
```

---

## Full Stack Start

```bash
# DB init (once)
sqlite3 ./data/v91_independent_state.db < data/init_listener_db.sql

# Start all services
docker compose up --build -d

# Verify all healthy
docker compose ps
```
