# V91 Core System – Architecture and verified scope

**Status:** documented prototype; CI-tested behavior is limited to the tests in this repository.
**Deployment mode:** Compose runs a local filesystem observer and real offline task workers. The synthetic controller is manual/demo only. Bounded host-side Docker control is available through an explicit opt-in CLI; it is not automatically enabled by the container.

## What exists in this repository

- `controller/controller.py`: manual synthetic demonstration only; random samples are never used by the live actuator.
- `controller/observer.py`: records actual local queue counts and audit-log parsing state in `runtime/v91-observer.json`.
- `controller/worker.py`: processes an offline JSON task queue with an allowlist: health snapshot, SHA-256 calculation, and SHA-256 comparison. It rejects arbitrary shell/code and workspace path traversal.
- `controller/runtime_control.py`: host-side adapter reads actual Docker Compose container state and Docker CPU/memory percentages. It can scale only the `worker` service, within hard bounds, after explicit opt-in.
- `controller/anomaly.py`, `metrics.py`, `feedback.py`, and `chaos.py`: reusable algorithm/demo modules; the synthetic/demo paths are not treated as live telemetry.
- `tests/`: unit and safety regression tests for decisions, queue processing, audit order, effect measurement, rollback, and input boundaries.
- `.github/workflows/audit.yml`: validates Compose configuration, runs tests/compilation, and produces source checksum artifacts.

## Data and action boundaries

The manual demonstration in `controller/controller.py` generates random values. These values are **synthetic**, not operating-system, Docker, network, energy, or production telemetry. The Compose stack does not use these values for control decisions.

The host-side runtime controller reads live Docker/Compose state. Scale-up requires `V91_ENABLE_REAL_ACTIONS=1`; scale-down additionally requires `V91_ALLOW_SCALE_DOWN=1`. Only the allow-listed `worker` service can be scaled, between one and three replicas. Each decision is written before an action; after an action, the replica/running state is checked, resource deltas are recorded, and a failed verification triggers a rollback attempt.

The task worker accepts only `health_snapshot`, `sha256_file`, and `verify_sha256`. It uses no network, shell, or arbitrary code execution. Inputs are bounded and file paths must remain inside the read-only workspace.

Remaining gaps: application-level latency/error metrics are not connected; the audit JSONL file is not WORM or signed; event truth and real-world identity are not independently attested; and no useful application workload or production deployment has been verified.

## V91 operating principles

1. Unknown values remain `UNKNOWN`; missing data is not replaced by a success value.
2. A synthetic or simulated result must never be presented as live evidence.
3. Detection does not authorize an action. Every real actuator requires a separate, explicit authorization boundary and narrowly scoped privileges.
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

Next improvements should connect actual application-level health/latency/error telemetry, strengthen audit durability and signing, add explicit worker health checks, and test action/rollback against a disposable Compose project. The current CI tests logic with mocked Docker responses; it does not prove that this user's Docker host is running or that a live scaling operation succeeded.
