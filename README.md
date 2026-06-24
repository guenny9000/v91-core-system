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
