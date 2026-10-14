# V91 Core System – Architecture and verified scope

**Status:** documented prototype; CI-tested behavior is limited to the tests in this repository.
**Current mode:** synthetic simulation only. **No host or Docker control actions are enabled.**

## What exists in this repository

- `controller/controller.py`: creates synthetic metric samples, evaluates simple rules, and records proposed actions without executing them.
- `controller/anomaly.py`: sliding-window anomaly detection. Each sample is scored against prior observations before it is added to the window.
- `controller/metrics.py`: in-memory event counters and recent latency history.
- `controller/feedback.py`: in-memory strategy selection based on the supplied values.
- `controller/chaos.py`: helper functions for simulated degradation and exceptions. They are not wired to production infrastructure.
- `tests/`: unit and safety regression tests.
- `.github/workflows/audit.yml`: runs tests and produces source checksum artifacts.

## Data and action boundaries

The controller currently generates values with Python's random-number generator. These values are **synthetic**, not operating-system, Docker, network, energy, or production telemetry. Reports must preserve that distinction.

The action names `scale_up_workers`, `scale_down_workers`, and `activate_chaos_mode` are proposals only. The current controller does not execute shell commands, restart containers, scale workers, or change the host.

There is no implemented production metrics adapter, actuator authorization service, durable audit ledger, signed evidence envelope, external trust witness, or deployment verification in this repository. Other repositories may describe planned components, but those descriptions do not prove that the components are implemented or connected here.

## V91 operating principles

1. Unknown values remain `UNKNOWN`; missing data is not replaced by a success value.
2. A synthetic or simulated result must never be presented as live evidence.
3. Detection does not authorize an action. Any future actuator requires a separate, explicit authorization boundary and narrowly scoped privileges.
4. Invalid, non-finite, or negative metric values are rejected before evaluation.
5. Existing source data is not rewritten by tests. Test artifacts are not proof of immutability or production operation.
6. A checksum proves only that bytes match a specific digest; it does not prove who produced them, when they were produced, or that the underlying claim is true.

## Run locally

```bash
python -m pip install pytest
python -m pytest tests/ -v
python controller/controller.py
```

The controller command enters a synthetic demonstration loop and may run until stopped. It does not perform real-world control actions.

## CI evidence

A successful GitHub Actions run proves only that the configured steps passed for the exact commit tested. It does not prove deployment, live telemetry, offline isolation, WORM storage, or system-wide V91 compliance.

## Future work, not current capability

A future real-control design should first provide: a validated read-only metrics adapter; a typed proposal format; independent policy authorization; a separately deployed least-privilege actuator; bounded operations with rollback; structured audit events; and integration tests using a disposable environment. None of these future items should be marked implemented until the repository contains the code and repeatable evidence.
