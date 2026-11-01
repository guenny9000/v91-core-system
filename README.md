# v91-core-system – Stufe 6: Autonomous Control Plane

## Übersicht

v91-core-system ist ein **selbstregulierendes, verteiltes Backend-System** mit Anomaly Detection, Rule Engine, Chaos Simulation und automatischen Feedback-Loops.

## Architektur

```
Metrics Stream
     ↓
Anomaly Detector (z-score / sliding window)
     ↓
Rule Engine (Policy Evaluation)
     ↓
Control Actions (Scale, Throttle, Restart, Chaos)
```

## Features

### Reactive
- Worker Restart bei Fehlern
- Auto-Scaling (up/down bei Laständerung)

### Proactive
- Z-Score basierte Anomalie-Erkennung
- Sliding Window Detector
- Trendbasierte Entscheidungen

### Destructive
- Chaos Mode (gezielte Fehlerinjection)
- Controlled Fault Simulation

### Self-Optimization
- Feedback Loop passt Strategie dynamisch an
- Strategiewechsel: reduce_load, scale_up, conserve_resources, stable

## Installation

```bash
git clone https://github.com/guenny9000/v91-core-system.git
cd v91-core-system
```

## Starten

### Docker Compose (empfohlen)

```bash
docker compose up --build
```

Das startet:
- Controller Service
- Worker Service (on demand)

### Local (Python)

```bash
pip install numpy pytest
python controller/controller.py
```

## Tests

```bash
pytest tests/
```

Führt aus:
- `test_anomaly.py` – Anomaly Detection Tests
- `test_rules.py` – Rule Engine Tests
- `test_feedback.py` – Feedback Loop Tests

## Module

### controller.py
Hauptsteuerung: Rules evaluieren, Metrics ingesten, Actions triggern.

### anomaly.py
Sliding Window Anomaly Detector (z-score basiert).

### metrics.py
Metrics Aggregator Feed (Events, Errors, Latency).

### chaos.py
Chaos Mode: Gezielte Fehlerinjection für Resilience Testing.

### feedback.py
Feedback Loop: Self-Optimization basierend auf Systemzustand.

## Workflow

```
1. Metrics kommen rein (Events, Errors, Latency)
2. Anomaly Detector prüft z-score
3. Rule Engine evaluiert Policies
4. Control Actions werden triggered (Scale, Chaos, etc.)
5. Feedback Loop passt Strategie an
6. Loop wiederholt sich alle 5 Sekunden
```

## CI/CD

GitHub Actions Pipeline (`audit.yml`):
- Hash Verification (SHA256)
- Unit Tests (pytest)
- Dependency Checks

## Status

**Stable & Production-Ready für Self-Regulated Distributed Systems**

## Lizenz

© 2026 Sebastian (guenny9000) – Alle Rechte vorbehalten

## Ledger & Stewardship Gate (advisory)

- `controller/ledger.py`: append-only SHA-256 hash chain (tamper-evident, verifies on open, resumes head after restart).
- `controller/enforcement.py`: scores proposals, hard veto on human impact, records decisions only (`executed: false`). It never shuts down anything; execution needs a separate, explicitly authorised interface.
- Claims such as global operation or enforcement are not provided by this code; only what the tests verify.


### CLI

```bash
python controller/v91_cli.py evaluate TARGET --resource-util 0.8 --entropy 0.7 --environment 0.6 --human-impact 0.1
python controller/v91_cli.py verify
```
Exit codes: 0 ok, 1 invalid input/broken ledger, 2 rejected (human impact).


### Impact from real measurements

```bash
python controller/v91_cli.py collect-local --out base.csv --samples 10   # real RAM-in-use samples
# ... apply a real measure, then:
python controller/v91_cli.py collect-local --out after.csv --samples 10
python controller/v91_cli.py impact my-measure --baseline base.csv --after after.csv --unit MB --co2-factor <kg/unit, cite source>
python controller/v91_cli.py report
```
CSV format: `timestamp,value,source_type` (direct_sensor|calculated|estimated|manual_entry). A saving is VALID only with enough samples, DQI >= 0.85, baseline before after-period, and a difference above 2x measurement noise; everything else is QUARANTINE. The CO2 factor is never assumed.

