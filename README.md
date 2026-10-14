# V91 Core System

## Purpose

V91 Core System is a Python project for experimenting with metrics processing, anomaly detection, rule evaluation, feedback strategies, and resilience testing. Its intended direction is a local-first resilience core with verifiable evidence and optional external synchronization.

**Current maturity: experimental. Not certified or demonstrated as production-ready.** A repository description, CI success, or generated status report is not evidence that a service is deployed, continuously running, secure in every environment, or operating globally.

## Reality-first status

Use these states precisely:

- `UNKNOWN`: no adequate evidence is available.
- `DOCUMENTED`: a requirement or design is written down.
- `IMPLEMENTED`: code exists at a named revision.
- `VERIFIED`: a specific, reproducible check passed for a specific revision and environment.
- `PRODUCTION`: only after deployment, monitoring, recovery, security, and operational acceptance evidence exists.

A claim is not evidence. Record the exact commit, command, environment, timestamp, result, and relevant artifact for each verification. Missing evidence must not be reported as a pass.

## Design goals

- Local checks should remain available when GitHub or the network is unavailable.
- GitHub should be an optional place to exchange source, reviews, and signed update proposals—not a runtime dependency.
- New code and external model suggestions should be staged and tested in isolation before use.
- Untrusted inputs must be validated as data, never executed as code.
- Updates should have explicit trust roots, signature verification, revocation handling, and a tested rollback path.
- Automatic actions must follow least privilege and be bounded by explicit resource and safety limits.
- Fault injection or chaos tests must remain opt-in and confined to a disposable test environment. Do not use them against a live system without a separately approved test plan.

These are design goals; this README does not assert that all of them are already implemented.

## Repository layout

- `controller/`: controller, metrics, anomaly detection, feedback, and fault-simulation modules.
- `tests/`: unit tests for selected modules.
- `Dockerfile` and `docker-compose.yml`: container configuration for development/testing.
- `V91-ARCHITECTURE.md`: broader architecture notes. Treat descriptions of services, endpoints, SLAs, signing, retention, or federation as proposals unless matching implementation and reproducible evidence are linked.

## Development checks

The repository has historically documented these commands; check the current environment and dependencies before running them:

```bash
pip install numpy pytest
pytest tests/
```

Container-based development has been documented as:

```bash
docker compose up --build
```

Run tests in a development or isolated environment first. Do not assume that the container configuration, health endpoints, or service integrations have been validated merely because files exist.

## Evidence and security limitations

- A passing unit test verifies only the behavior exercised by that test.
- A successful CI run applies only to the exact revision and checks shown by that run.
- A SHA-256 hash can help detect changes to recorded bytes; it does not establish that the underlying data is true, authenticate a publisher by itself, or make storage immutable.
- A digital signature proves that the signed bytes validate under a particular key; trusted identity, key distribution, rotation, and revocation require separate design and verification.
- No statement here claims global telemetry, autonomous global enforcement, continuous local operation, WORM compliance, or a production deployment.

## Remaining milestones

1. Verify signed updates, key revocation, and rollback against explicit test cases.
2. Add a trusted external anchor if WORM-like retention is required; do not label plain JSONL as immutable.
3. Connect real application-level latency/error metrics only through a named, tested source.
4. Run a small, reversible local pilot and preserve its raw measurements.

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
  "relative_path": "example.txt",
  "purpose": "Calculate a reproducible SHA-256 digest for the input file.",
  "expected_effect": "Return the digest and byte count in the result file."
}
```

For an integrity comparison, use `"action": "verify_sha256"` and add `"expected_sha256": "64-hexadecimal-characters"`. Every task must also include a short `purpose` and `expected_effect` (each at most 500 characters); the worker rejects undocumented tasks before performing work. For a worker health/queue snapshot, use `{"task_id":"health-demo","action":"health_snapshot","purpose":"Check local worker and queue state.","expected_effect":"Return observed queue counts and worker uptime."}`. Task IDs must be unique and match the filename stem. The worker claims tasks by atomic rename, rejects unsupported fields/actions, never overwrites an existing result, and records completion/failure in the shared audit log. The workspace is mounted read-only inside containers. Both services share a private Docker network marked `internal: true`: local services can communicate on that network when explicitly added, but it has no external-network route. The worker itself makes no network calls. No Docker socket is mounted into either container.

On Windows, start the stack with `docker compose up -d --build`. To submit a real example task without hand-writing JSON, run `.\scripts\Submit-V91ExampleTask.ps1`; it copies a small example input into the workspace and writes a uniquely named task into the pending queue. The worker result appears under `runtime/results/`. To scale workers under measured resource pressure, use the host-side controller documented above. No Docker socket is mounted inside the observer or worker containers.

## License

© 2026 Sebastian (guenny9000) – Alle Rechte vorbehalten
