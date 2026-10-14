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

**Prototyp: CI-geprüfte Funktionen sind konkret dokumentiert; keine pauschale Produktionsfreigabe.**

## Lizenz

© 2026 Sebastian (guenny9000) – Alle Rechte vorbehalten


## Live Docker control (host-side, opt-in)

The Docker Compose stack now runs a real local observer plus a shared-queue worker. The synthetic `controller/controller.py` demonstration remains available for manual testing only and is not used as the default Compose controller.

For real local observation and bounded worker scaling, use `controller/runtime_control.py` **on the Docker host**. It reads actual Compose container state and `docker stats`; missing or unhealthy observations fail closed instead of falling back to random values. It only controls the Compose service named `worker`, with a hard limit of 1–3 replicas. The worker service must not define a fixed `container_name`, because Docker Compose cannot scale such a service.

First run observe-and-plan mode (no infrastructure changes):

```powershell
.\scripts\Start-V91RuntimeControl.ps1
```

The script tries to identify one already-running Compose project by matching its recorded config file. If zero or multiple projects match, it refuses to guess. Then set `V91_PROJECT_NAME` to the exact existing project name and retry.

The command records a JSONL decision under `runtime/v91-actions.jsonl`, including the live observation, reason, expected effect, authorization state, and rollback plan. The log is append-only by this program, but it is not WORM or signed evidence.

Only after reviewing the plan, enable real **scale-up** actions explicitly:

```powershell
.\scripts\Start-V91RuntimeControl.ps1 -EnableRealActions
```

Scale-up requires live Docker resource pressure (CPU at least 75% or memory at least 80%), is limited to one replica per cycle, and is capped at three replicas. Scale-down requires three consecutive low-resource samples and a separate `V91_ALLOW_SCALE_DOWN=1`; it is not enabled by the general action switch. Post-action state is checked; if verification fails, the controller attempts to restore the previous replica count and records the result.

To keep observing with the Windows launcher, add `-Watch` (and optionally `-IntervalSeconds 60`). The minimum interval is 15 seconds. To permit capacity reduction as well, add `-AllowScaleDown`; this is a separate opt-in. Use the exact project name of the existing stack; the script does not create or switch to a guessed project. The host-side script must be run where the Docker CLI can access that stack. It is deliberately not given the Docker socket inside the controller container.

The worker now performs real offline tasks from `queue/pending/`: `health_snapshot`, `sha256_file`, and `verify_sha256`. The observer writes actual queue and audit-log state to `runtime/v91-observer.json`. Scaling verifies container capacity and records resource deltas; it does not by itself prove an application-level performance improvement.


## Submit a real offline task

Place the input file under `workspace/` and create one JSON file in `queue/pending/`. Example `queue/pending/hash-demo.json`:

```json
{
  "task_id": "hash-demo",
  "action": "sha256_file",
  "relative_path": "example.txt"
}
```

For an integrity comparison, use `"action": "verify_sha256"` and add `"expected_sha256": "64-hexadecimal-characters"`. For a worker health/queue snapshot, use `{"task_id":"health-demo","action":"health_snapshot"}`. Task IDs must be unique and match the filename stem. The worker claims tasks by atomic rename, rejects unsupported fields/actions, never overwrites an existing result, and records completion/failure in the shared audit log. The workspace is mounted read-only inside containers.

On Windows, create the host folders `queue`, `runtime`, and `workspace` next to `docker-compose.yml` if they do not exist, then start the stack with `docker compose up -d --build`. To scale workers under measured resource pressure, use the host-side controller documented above. No Docker socket is mounted inside the observer or worker containers.
