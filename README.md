# v91-core-system — Reality-First Control Plane

## Principle
Preserve and protect existing capabilities. Prefer repair, isolation, reversible changes, and recovery over destruction or unnecessary shutdown.

## Runtime modes
- `safe` (default): the controller remains running and reports `NO_DATA_AVAILABLE` while waiting for a verified real metrics adapter. It does not invent live telemetry.
- `simulation`: continuous synthetic test stream, explicitly labelled as synthetic. This tests logic, not real hardware or network health.
- `live`: currently refuses to start because this repository does not yet contain a provenance-checked real metrics adapter. This is a missing capability, not a reason to present synthetic data as real.

The service loop has no automatic time or iteration cut-off. Docker Compose restarts the controller after a crash. Recommendations do not execute shell commands or restart workers.

## Run
PowerShell simulation:
```powershell
$env:V91_MODE = "simulation"
python controller/controller.py
```
Safe long-running mode:
```powershell
$env:V91_MODE = "safe"
python controller/controller.py
```
Docker Compose:
```powershell
docker compose up --build -d
docker compose logs -f controller
```
No deployment has been performed by editing this repository.

## Tests
```bash
python -m pytest -q
```

## Hardware adaptation
Per-machine adaptation should use actual CPU, memory, GPU, thermal, OS, and workload measurements. Automatic hardware discovery and per-hardware policy selection are not yet implemented. They need source provenance, safe bounds, tests, and reversible policy changes.

## Evidence status
- Continuous controller loop: implemented in repository code.
- Synthetic simulation: implemented and labelled.
- Real metrics adapter: not implemented.
- Task-processing worker: placeholder.
- Real infrastructure action adapter: not implemented.
- Production deployment and live service health: unverified.

A successful CI run verifies only the tested branch and paths; it does not prove production operation.
