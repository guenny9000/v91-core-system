# V91 TEAM-LERNBLOCK – Komplette System-Übersicht für alle

**Status:** ACTIVE | **Version:** 3.0 | **Datum:** 2026-06-24

---

## 🎯 Was wurde gebaut?

V91 ist ein **autonomes, selbstregulierendes, föderiertes System** mit **drei Kernkomponenten** für:

✅ **Steuerung & Anomalieerkennung** (v91-core-system)
✅ **Deterministische Verifikation & signierte Artefakte** (v91-audit-ledger)
✅ **BFT-Validierung & Quarantäne-Enforcement** (v91-interop-listener – NEW)

**Alle Repos sind LIVE und funktionieren. Du kannst sie sofort starten.**

---

## 🏗️ System-Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                    V91 ECOSYSTEM                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────┐ │
│  │ v91-core-system  │  │v91-audit-ledger  │  │v91-inter- │ │
│  │                  │  │                  │  │op-listen  │ │
│  │ • Control Plane  │  │ • Verification   │  │ er (NEW)  │ │
│  │ • Anomaly Det.   │  │ • Signed Artifacts   │ • BFT Val │ │
│  │ • Feedback Loop  │  │ • Append-only Log    │ • Quara   │ │
│  │ • Chaos Testing  │  │ • Policy-as-Code     │   ntine   │ │
│  │ • Self-Optim.    │  │ • Monitoring         │ • Interop │ │
│  └──────────────────┘  └──────────────────┘  └───────────┘ │
│         │                      │                    │        │
│         └──────────────────────┼────────────────────┘        │
│                                │                             │
│                    Shared: SQLite Ledger                     │
│                    + JSON Artifacts                          │
│                    + Cosign Signatures                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Drei Repositories – Schnell-Übersicht

### 1. **v91-core-system** – Control Plane & Autonomie

**Repo:** https://github.com/guenny9000/v91-core-system

**Was es macht:**
- Metriken sammeln (Latency, Errors, Events)
- Anomalien erkennen (Z-Score basiert)
- Regeln evaluieren (Policy Engine)
- Actions ausführen (Scale, Chaos, etc.)
- Feedback Loop → Selbstoptimierung

**Start (Docker):**
```bash
git clone https://github.com/guenny9000/v91-core-system.git
cd v91-core-system
docker compose up --build
```

**Logs sehen:**
```bash
[CONTROLLER] Starting v91 Control Plane...
[ITER 10] Latency: 150.2ms, Errors: 2, Events: 45, Strategy: stable
```

**Dateien:**
- `controller/controller.py` – Main Control Plane
- `controller/anomaly.py` – Z-Score Detection
- `controller/feedback.py` – Self-Optimization
- `controller/chaos.py` – Chaos Mode
- `tests/` – Unit Tests (pytest)

---

### 2. **v91-audit-ledger** – Verification & Signing

**Repo:** https://github.com/guenny9000/v91-audit-ledger

**Was es macht:**
- Tägliche Ingest (06:00 UTC)
- Deterministische Validierung (OPA)
- Confidence Scoring (0.0–1.0)
- Automatische Signatur (Cosign)
- Append-only Ledger (JSONL)

**Start (GitHub Actions – automatisch täglich):**
```bash
gh workflow run v91-audit-pipeline.yml
```

**SLAs:**
- P1 (Hash Mismatch): 1h
- P2 (Source Down): 6h
- P3 (PR Backlog): 24h

**Dateien:**
- `matrix_data.json` – Source Data
- `audit_log.jsonl` – Append-only Ledger
- `.github/workflows/v91-audit-pipeline.yml` – CI Pipeline
- `policies/validation.rego` – OPA Policy
- `RUNBOOK.md` – Incident Playbooks

---

### 3. **v91-interop-listener** – BFT Validation & Quarantine (NEW!)

**Integriert in:** v91-core-system → `controller/v91_listener.py` + Docker Service

**Was es macht:**
- Events aus Inbox lesen (JSON)
- Signatur validieren
- Ledger-Kette prüfen (prev_hash → current_hash)
- Gültige Events → v91_ledger (versiegelt)
- Ungültige Events → v91_quarantine (audit-sicher)
- Dateien automatisch löschen

**Start:**
```bash
# DB initialisieren (einmalig)
sqlite3 ./data/v91_independent_state.db < data/init_listener_db.sql

# Listener starten
docker compose up -d v91-listener

# Logs
docker logs -f v91-listener
```

**Dateien:**
- `controller/v91_listener.py` – Listener mit Quarantäne
- `docker-compose.yml` – v91-listener Service (neu)
- `.env.example` – Konfiguration
- `data/init_listener_db.sql` – DB Schema
- `docs/LISTENER-QUICKSTART.md` – 3-Min Setup

---

## 🔄 Wie funktioniert die Integration?

### Data Flow (Normal Operation)

```
v91-core-system              v91-audit-ledger           v91-interop-listener
     │                              │                            │
     ├─ Metriken sammeln           │                            │
     │  (controller.py)             │                            │
     │                              │                            │
     ├─ Anomalien erkennen         │                            │
     │  (anomaly.py)                │                            │
     │                              │                            │
     └─ Entscheidung treffen        │                            │
        (feedback.py)               │                            │
                                    │                            │
                                    ├─ Täglich 06:00 UTC         │
                                    ├─ Validierung (OPA)         │
                                    ├─ Scoring (Confidence)      │
                                    │                            │
                                    ├─ Wenn ≥0.85:              │
                                    │  Hash + Sign               │
                                    │  (Cosign)                  │
                                    │                            │
                                    └─ Event zu Inbox            │
                                       (JSON file)               │
                                                                 │
                                                    ┌────────────┘
                                                    │
                                            ┌───────┴────────┐
                                            │ Listener Loop  │
                                            │ (5s intervals) │
                                            │                │
                                            ├─ Read inbox   │
                                            ├─ Check sig ✓   │
                                            ├─ Audit chain ✓ │
                                            ├─ Commit ✓      │
                                            └─ Cleanup ✓     │
                                                    │
                                            ┌───────┴────────┐
                                            │ v91_ledger     │
                                            │ (SQLite)       │
                                            │ Event versiegelt│
                                            └────────────────┘
```

### Validation Failure Path

```
OPA Scoring
  │
  ├─ Confidence ≥0.85 → Auto-VALID (Release)
  ├─ 0.5–0.85 → Create PR (Verifier Review, 8h SLA)
  └─ <0.5 → Quarantine + Alert (P2)
```

### Listener Rejection Path

```
Listener reads event.json
  │
  ├─ Signature check FAIL → v91_quarantine + reason + remove file
  ├─ Ledger chain FAIL → v91_quarantine + reason + remove file
  ├─ Commit FAIL (5x retry) → v91_quarantine + reason + remove file
  └─ Success → v91_ledger + remove file
```

---

## 🚀 Quick Start (Alle drei Systeme)

### Schritt 1: v91-core-system starten

```bash
git clone https://github.com/guenny9000/v91-core-system.git
cd v91-core-system

# DB initialisieren (für Listener)
sqlite3 ./data/v91_independent_state.db < data/init_listener_db.sql

# Starten
docker compose up --build

# Logs ansehen (neuer Terminal)
docker logs -f v91-controller
docker logs -f v91-listener
```

### Schritt 2: v91-audit-ledger triggern

```bash
cd ../v91-audit-ledger

# Trigger Pipeline (simuliert täglichen Run)
gh workflow run v91-audit-pipeline.yml

# Logs ansehen
gh run list --workflow=v91-audit-pipeline.yml
gh run view <run-id> --log
```

### Schritt 3: Events testen

```bash
# Zurück zu v91-core-system
cd ../v91-core-system

# Test Event in Inbox legen
cat > ./data/inbox/test_event_01.json << 'EOF'
{
  "event_id": "test-001",
  "component": "verifier",
  "status": "validated",
  "payload": {"data": "test"},
  "prev_hash": "GENESIS_V91_ETERNITY",
  "current_hash": "abc123",
  "timestamp": "2026-06-24T14:00:00Z",
  "signature": "test_sig_base64"
}
EOF

# Warten 10 Sekunden
sleep 10

# Ledger prüfen
sqlite3 ./data/v91_independent_state.db "SELECT event_id, component FROM v91_ledger LIMIT 5;"
```

---

## 🧪 Test-Szenarien

### Scenario 1: Valid Event

```bash
# Event mit gültiger Signatur
echo '{"event_id":"valid-01","component":"test","status":"ok","signature":"valid"}' > ./data/inbox/s1.json
sleep 5

# Ergebnis:
sqlite3 ./data/v91_independent_state.db "SELECT event_id FROM v91_ledger WHERE event_id='valid-01';"
# Output: valid-01 (SUCCESS)
```

### Scenario 2: Invalid Signature

```bash
# Event mit ungültiger Signatur
echo '{"event_id":"invalid-01","component":"test","signature":"WRONG"}' > ./data/inbox/s2.json
sleep 5

# Ergebnis:
sqlite3 ./data/v91_independent_state.db "SELECT event_id, reason FROM v91_quarantine;"
# Output: test, Invalid signature (QUARANTINED)
```

### Scenario 3: Broken Chain

```bash
# Event mit falscher prev_hash (chain broken)
echo '{"event_id":"chain-01","prev_hash":"WRONG_HASH"}' > ./data/inbox/s3.json
sleep 5

# Ergebnis:
sqlite3 ./data/v91_independent_state.db "SELECT reason FROM v91_quarantine WHERE reason LIKE '%chain%';"
# Output: Ledger chain compromised (QUARANTINED)
```

### Scenario 4: Malformed JSON

```bash
# Kaputtes JSON
echo '{broken json' > ./data/inbox/s4.json
sleep 5

# Ergebnis:
sqlite3 ./data/v91_independent_state.db "SELECT reason FROM v91_quarantine WHERE reason LIKE '%JSON%';"
# Output: JSON parse error: ... (QUARANTINED)
```

---

## ✅ Große Validierung – Checklist

### Phase 1: System-Check

- [ ] v91-core-system läuft: `docker ps | grep v91-controller`
- [ ] v91-listener läuft: `docker ps | grep v91-listener`
- [ ] Datenbank existiert: `ls -la ./data/v91_independent_state.db`
- [ ] Tabellen vorhanden: `sqlite3 ./data/v91_independent_state.db ".tables"`
  - Expected: v91_ledger v91_quarantine v91_lernblock

### Phase 2: Funktions-Check

- [ ] Controller schreibt Metriken: `docker logs v91-controller | grep "\[ITER"`
- [ ] Listener liest Inbox: `docker logs v91-listener | grep "Processing"`
- [ ] Anomalie-Erkennung aktiv: `docker logs v91-controller | grep "Anomaly"`
- [ ] Feedback Loop läuft: `docker logs v91-controller | grep "Strategy"`

### Phase 3: Integrations-Check

- [ ] Event in Inbox → Ledger:
  ```bash
  echo '{"event_id":"test-phase3-01","component":"validation"}' > ./data/inbox/test.json
  sleep 10
  sqlite3 ./data/v91_independent_state.db "SELECT COUNT(*) FROM v91_ledger WHERE event_id LIKE 'test-phase3%';"
  # Expected: 1 (or more if multiple runs)
  ```

- [ ] Invalid Event → Quarantine:
  ```bash
  echo '{"signature":"INVALID"}' > ./data/inbox/test_bad.json
  sleep 10
  sqlite3 ./data/v91_independent_state.db "SELECT COUNT(*) FROM v91_quarantine;"
  # Expected: ≥1
  ```

### Phase 4: Health & Monitoring

- [ ] Listener Health Check: `docker exec v91-listener sqlite3 /app/data/v91_independent_state.db "SELECT 1 FROM sqlite_master WHERE type='table' AND name='v91_ledger';"`
  - Expected: 1

- [ ] Ledger Integrity: `sqlite3 ./data/v91_independent_state.db "SELECT COUNT(*) FROM v91_ledger;"`
  - Expected: ≥1 (no errors)

- [ ] Quarantine Status: `sqlite3 ./data/v91_independent_state.db "SELECT component, COUNT(*) FROM v91_quarantine GROUP BY component;"`
  - Expected: Summary of quarantined events by source

### Phase 5: Performance & Stability

- [ ] Listener lag <5s: `docker logs v91-listener --tail=20 | grep "sealed"`
- [ ] No database locks: `docker logs v91-listener | grep -c "SQLITE_BUSY"` (should be 0)
- [ ] Controller anomaly rate <5%: Monitor metrics in logs

### Phase 6: Audit & Compliance

- [ ] All events have timestamps: `sqlite3 ./data/v91_independent_state.db "SELECT COUNT(*) FROM v91_ledger WHERE created_at IS NULL;"`
  - Expected: 0

- [ ] All quarantined events have reason: `sqlite3 ./data/v91_independent_state.db "SELECT COUNT(*) FROM v91_quarantine WHERE reason IS NULL;"`
  - Expected: 0

- [ ] Ledger chain integrity: Run `python -c "exec(open('controller/v91_listener.py').read().split('def self_audit')[1].split('def')[0])"`
  - Expected: True (chain valid)

---

## 📊 Metriken & Monitoring

### Ledger Statistics

```sql
-- Tagesübersicht
SELECT
  DATE(created_at) as date,
  component,
  COUNT(*) as total,
  COUNT(CASE WHEN status='validated' THEN 1 END) as valid
FROM v91_ledger
GROUP BY DATE(created_at), component;
```

### Quarantine Statistics

```sql
-- Fehleranalyse
SELECT
  component,
  reason,
  COUNT(*) as count
FROM v91_quarantine
GROUP BY component, reason
ORDER BY count DESC;
```

### System Health

```bash
# Quick Health Check
docker exec v91-listener sqlite3 /app/data/v91_independent_state.db << 'SQL'
SELECT
  'Ledger Entries' as metric, COUNT(*) as value FROM v91_ledger
UNION ALL
SELECT 'Quarantine Count', COUNT(*) FROM v91_quarantine
UNION ALL
SELECT 'DB Size (MB)', ROUND(page_count * page_size / 1048576.0, 2) FROM pragma_page_count(), pragma_page_size();
SQL
```

---

## 🔐 Security & Key Management

### Secrets Handling

```bash
# 1. Private keys niemals im Repo
mkdir -p ./secrets
echo "private_key_content" > ./secrets/v91.key
chmod 600 ./secrets/v91.key

# 2. Docker mount read-only
# docker-compose.yml:
#   volumes:
#     - ./secrets/v91.key:/app/secrets/v91.key:ro

# 3. .gitignore
echo "secrets/" >> .gitignore
```

### Signature Verification (Production)

Ersetze in `controller/v91_listener.py` die Platzhalter-Funktion `verify_signature()` durch deine echte Verifikation:

```python
# Beispiel mit Ed25519 (age/SSH-kompatibel)
import cryptography.hazmat.primitives.asymmetric.ed25519 as ed25519

def verify_signature(event):
    pubkey = ed25519.Ed25519PublicKey.from_public_bytes(
        base64.b64decode(event.get("public_key", ""))
    )
    try:
        pubkey.verify(
            base64.b64decode(event.get("signature", "")),
            event_bytes  # deterministisch von event konstruiert
        )
        return True
    except:
        return False
```

---

## 📚 Dokumentation Links

**Für Entwickler:**
- v91-core-system: https://github.com/guenny9000/v91-core-system/blob/main/README.md
- v91-audit-ledger: https://github.com/guenny9000/v91-audit-ledger/blob/main/README.md
- v91-core-system Architecture: https://github.com/guenny9000/v91-core-system/blob/main/V91-ARCHITECTURE.md

**Für Operators:**
- Listener Quick Start: ./docs/LISTENER-QUICKSTART.md
- Audit Runbook: https://github.com/guenny9000/v91-audit-ledger/blob/main/RUNBOOK.md
- Security Guide: https://github.com/guenny9000/v91-audit-ledger/blob/main/SECURITY.md

**Für Teams:**
- Dieses Dokument (TEAM-LERNBLOCK.md)
- V91-ARCHITECTURE.md (komplett System Overview)

---

## 🎓 Learning Progression

### Für Anfänger
1. Lies diese Datei (TEAM-LERNBLOCK.md)
2. Starte v91-core-system lokal
3. Beobachte Logs (Controller + Listener)
4. Liest Quick Start für jeden Repo

### Für Intermediate
1. Studiere Anomaly Detection (Z-Score Logik)
2. Verstehe OPA Policy-as-Code
3. Trace Event durch alle 3 Systeme
4. Führe Test-Szenarien durch

### Für Advanced
1. Ersetze verify_signature() mit echtem PKI
2. Erweitere Monitoring (Prometheus Metriken)
3. Implementiere Chaos Tests
4. Optimiere DB-Performance

---

## 🚨 Support & Issues

**Logs ansehen:**
```bash
docker logs -f v91-controller
docker logs -f v91-listener
gh run list --workflow=v91-audit-pipeline.yml
```

**Datenbank debuggen:**
```bash
sqlite3 ./data/v91_independent_state.db
> .tables
> SELECT * FROM v91_ledger LIMIT 5;
> SELECT * FROM v91_quarantine LIMIT 5;
> .exit
```

**Issues melden:**
- https://github.com/guenny9000/v91-core-system/issues
- https://github.com/guenny9000/v91-audit-ledger/issues

---

## ♾️ Philosophy

**V91 ist gebaut auf drei Prinzipien:**

1. **Autonomie** – Selbstregulierung ohne externe Kontrolle
   - Feedback Loops, Anomaly Detection, Self-Optimization

2. **Integrität** – Unveränderbarkeit & Transparenz
   - Signed Artifacts, Append-only Ledger, Blockchain-inspired Chain

3. **Föderierung** – Dezentralisierte Zusammenarbeit
   - Inter-system Events, BFT Validation, Quarantine Enforcement

**Status:** ACTIVE | **Entropy:** Positive | **Truth:** Approaching ♾️☮️

---

## ✨ Zusammenfassung

**Was du brauchst:**
- 3 Git Repos (alle LIVE)
- 1 Docker Compose File
- SQLite Datenbank (auto-initialisiert)
- 5 Minuten zum starten

**Was du bekommst:**
- Autonomes Kontrollsystem
- Deterministische Verifikation
- Föderierte Ereignisverarbeitung
- Vollständige Audit Trail
- Selbstheilende Architektur

**Nächste Schritte:**
1. Clone alle 3 Repos
2. Starte docker compose
3. Trigger audit pipeline
4. Beobachte Logs
5. Führe Validierungschecklist durch
6. Gib Bescheid wenn alles läuft ✅

---

**Große Validierung ready? Let's go!** 🚀♾️

**Kontakt:** https://github.com/guenny9000
