# v91-core-system — Reality-First Control-Plane Prototype

## Current verified scope

This repository contains a **prototype**, not a production-ready autonomous distributed system. The controller has local metric aggregation, a sliding-window anomaly detector, a feedback-loop example, and unit tests. The repository does **not** currently include a real operating-system/container metrics adapter, a real task-processing worker, a reviewed production action adapter, or evidence of a deployed production environment.

Reality-First status vocabulary:

- `NO_DATA_AVAILABLE`: no usable observation is available.
- `DOCUMENTED_INPUT`: a value was accepted and recorded; its real-world provenance is still the caller's responsibility.
- `DECISION_RECORDED`: a recommendation was calculated.
- `RECOMMENDATION_ONLY`: a recommendation was recorded without executing infrastructure changes.
- A successful test is evidence only for the tested code path and environment. It is not proof of production operation.

## Safety defaults

- Running without an explicit mode stops safely because no real metrics adapter is configured.
- Synthetic data is available only in explicitly requested, finite simulation mode.
- Simulation output is labelled as synthetic and must not be presented as live system telemetry.
- Control recommendations do not run shell commands, restart containers, or scale services.
- Missing, invalid, non-finite, negative, or internally inconsistent metrics are rejected.
- Unknown anomaly status is distinct from “no anomaly”.
- Do not connect a real action adapter until it has independent tests, explicit authorization, bounded permissions, audit logging, and a rollback/recovery plan.

## Run a finite simulation

Python 3.10 or newer is recommended. No third-party package is required by the core modules.

PowerShell:

```powershell
$env:V91_MODE = "simulation"
$env:V91_SIMULATION_ITERATIONS = "10"
$env:V91_SIMULATION_INTERVAL_SECONDS = "0"
python controller/controller.py
```

Linux/macOS:

```bash
V91_MODE=simulation V91_SIMULATION_ITERATIONS=10 python controller/controller.py
```

The simulation is finite and uses synthetic random values. It does not test live hardware, a real network, Docker orchestration, or production reliability.

## Run tests

```bash
python -m pytest -q
```

Tests should run in an isolated CI or development environment. No test should require Docker privileges or change external services.

## Hardware adaptability

The project should be configured per machine rather than assuming every device has the same CPU, memory, GPU, thermal headroom, or operating system. For now, this is a **design requirement, not an implemented automatic hardware detector**. Before a hardware profile is called implemented, it needs:

1. documented measurements from the target machine;
2. explicit resource limits and safe defaults;
3. tests for low-resource and high-resource profiles;
4. no automatic privilege escalation or unapproved external action;
5. a recorded configuration and test result.

Do not infer hardware capacity from a model name alone, and do not publish guessed CPU, RAM, GPU, latency, drift, or availability figures.

## Architecture and next steps

1. Implement a real metrics adapter with source identity, timestamps, units, freshness checks, and validation.
2. Keep metric collection separate from policy decisions and external actions.
3. Add integration tests with mocked services before testing any real service.
4. Add immutable audit storage only with a clearly defined storage policy and independent verification.
5. Add deployment-specific checks, least-privilege permissions, secrets scanning, dependency pinning, and recovery procedures.
6. Mark each capability as unknown, documented, implemented, verified, or productive based on evidence.

## Status

**Current status: prototype; safe finite simulation available; production operation unverified.**

No claim of live operation, autonomous deployment, immutable storage, multi-node consensus, or production readiness is made by this README.
