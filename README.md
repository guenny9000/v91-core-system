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

## Emergency response and self-defense

The documented emergency pathway is in [`docs/V91-NOTFALL-NOTWEHR-PROTOKOLL.md`](docs/V91-NOTFALL-NOTWEHR-PROTOKOLL.md). It defines proportionate protection, isolation, narrowly authorized shutdown, evidence handling, and recovery. This is documentation only; it does not grant blanket authority to control third-party systems or implement automatic emergency actions.

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

MIT (see LICENSE). Operator selection 2026-11-25, consistent with the freeware grant of 2026-11-22 (free use and spread for all). See CONTRIBUTING.md for the binding participation rules.

## Ledger & Stewardship Gate (advisory)

- `controller/ledger.py`: append-only SHA-256 hash chain (tamper-evident, verifies on open, resumes head after restart).
- `controller/enforcement.py`: scores proposals, hard veto on human impact, records decisions only (`executed: false`). It never shuts down anything; execution needs a separate, explicitly authorised interface.
- Claims such as global operation or enforcement are not provided by this code; only what the tests verify.


### CLI

```bash
python controller/v91_cli.py evaluate TARGET --resource-util 0.8 --entropy 0.7 --environment 0.6 --human-impact 0.1
python controller/v91_cli.py verify
python controller/v91_cli.py stewardship-report --ledger ledger.jsonl
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


## Installation, syntax and platform checks

Use the repository's declared Python version and dependencies as the starting point. The GitHub Actions audit currently runs Python 3.11 on Ubuntu; a local result on another Python version or operating system is useful but is not a substitute for the CI result on the exact commit.

### Minimal local validation

From the repository root, in an isolated environment:

```bash
python --version
python -m pip install --upgrade pip
python -m pip install pytest
python -m py_compile controller/*.py v91_*.py tests/*.py
python -m pytest tests/ -v
docker compose --file docker-compose.yml config --quiet
```

The compile command checks Python syntax without starting the runtime. The test command checks the behaviors covered by the tests. The Compose command checks configuration parsing; none of these alone proves production readiness. Run the Docker integration workflow where Docker is available.

On Windows PowerShell, the equivalent Python commands can be run from the repository root; if shell wildcard expansion differs, compile files individually or use a short Python script with `pathlib`. Do not assume a Bash command or path is portable to PowerShell.

### Syntax, encoding and translation errors

When a command fails, classify the failure before changing code:

1. **Syntax/parse error:** the source cannot be parsed by the selected language version. Run the compiler or parser first.
2. **Encoding or line-ending issue:** inspect the file encoding (prefer UTF-8), BOM, LF/CRLF handling, and accidental replacement characters. Do not repair text by blind global replacement.
3. **Version/platform mismatch:** record the exact Python version, operating system, shell, and command. Check APIs and path separators supported by that environment.
4. **Dependency/configuration error:** verify installed package versions and parse JSON, YAML, and Compose files with their actual validators.
5. **Runtime/test failure:** preserve the full traceback and failing test, reproduce it, make the smallest safe correction, then rerun the focused test and the full suite.

Automated repair should preserve the original, create a reviewable diff, run bounded checks, and report the exact commit and command results. If validation fails or the cause is uncertain, stop the change and report the evidence; do not label it fixed. Do not create a second overlapping pull request for the same fix—extend the existing change where appropriate.

### Installation and environment evidence

Before calling an installation verified, record the operating system, Python version, dependency-install result, Compose validation result (if applicable), test result, commit SHA, and log/artifact reference. A README instruction is documentation, not proof that installation succeeded on a particular machine.


## Capability-aware model autonomy

V91's target is distributed local autonomy, not dependence on one powerful workstation. Each participating node may contribute only its explicitly enabled and currently available compute, verification, encrypted storage, or metadata capacity. Smaller devices remain valid participants; they may decline work or request an authorized peer when local capacity is insufficient.

The design contract and staged acceptance criteria are documented in [V91 Capability-Aware Model Autonomy](docs/V91-CAPABILITY-AWARE-MODEL-AUTONOMY.md). The machine-readable capability manifest is [node-capabilities.schema.json](schemas/node-capabilities.schema.json). The current branch also includes a standard-library run-manifest builder and exact-replay comparison gate. This records pinned model/tokenizer/runtime/input/settings digests and distinguishes exact replay from mismatched conditions or differing outputs; it does not launch or execute a model. Cooperative encrypted storage, distributed lease locks, a full runner adapter, and multi-node operation remain unimplemented and unverified.


## Production operation: target architecture and acceptance gate (reality-first)

This section defines what a complete production system must provide. It does **not** reclassify the current repository as production-ready. A component is production-ready only when its implementation, tests, operational evidence, security review, recovery exercise, and named owner are linked to an exact release commit.

### Component map and current evidence boundary

| Component | Required production capability | Current status in this repository |
|---|---|---|
| Local observer | Read-only, timestamped measurements with source and quality metadata | Partial implementation; host-specific operation must be verified |
| Metrics and KPI engine | Versioned formulas, units, windows, uncertainty, provenance | Partial; no universal live telemetry |
| Anomaly detection | Explainable thresholds, false-positive tracking, safe fallback | Experimental; scope depends on tests |
| Policy / stewardship gate | Human-impact veto, least privilege, explicit authorization | Advisory decision path; no blanket execution authority |
| Task queue / worker | Validated offline tasks, bounded resources, idempotency | Implemented for documented offline task types; production acceptance not established |
| Runtime controller | Observe-plan-approve-act-verify-rollback lifecycle | Opt-in local Docker worker scaling only; not a general infrastructure controller |
| Audit ledger | Append-only records, chain verification, external trust anchor where required | SHA-256 hash chain is tamper-evident, not WORM by itself |
| Identity and authentication | Per-node identity, authenticated APIs, scoped tokens, revocation | Incomplete; route-by-route security review required |
| Secrets and key lifecycle | Secret store, least exposure, rotation/revocation procedures, incident response | Not fully implemented or independently verified |
| Update / supply-chain gate | Signed artifacts, pinned dependencies, provenance, staged rollout, rollback | Design milestones remain; no general trusted updater demonstrated |
| Peer federation | Mutual authentication, opt-in discovery, leases, quotas, partition handling | Not implemented as a verified multi-node service |
| Model execution adapter | Capability negotiation, model/runtime pinning, sandboxing, resource limits | Run-manifest/replay comparison exists; model execution adapter not demonstrated |
| Resource and energy manager | Real CPU/RAM/GPU/storage/network/power measurements and hard limits | Partial local CPU/memory observation; GPU, energy and fleet data not established |
| Data portability / recovery | Export, backup, restore, integrity checks, tested RPO/RTO | Recovery acceptance evidence incomplete |
| Privacy and retention | Data minimization, access logging, retention/deletion policy, export | Policy and implementation require review |
| Human operations | Runbooks, incident roles, escalation, maintenance and accessibility | Documentation incomplete for production |

**No missing component is silently treated as completed.** The table is a work register. Promote a row only with code paths, tests, exact commit, CI run, operational evidence, and review references.

### Production acceptance sequence

1. **Inventory and threat model:** identify every process, endpoint, data store, secret, dependency, network path, operator role, and failure domain.
2. **Secure defaults:** bind local-only services to loopback; deny by default; authenticate every non-public endpoint; validate inputs; apply least privilege; keep external synchronization opt-in.
3. **Evidence pipeline:** every measurement carries timestamp_utc, source_id, source_type, unit, raw_value, normalized_value, quality, uncertainty, collector_version, and commit_sha. Preserve raw observations.
4. **Resource bounds:** enforce CPU, memory, GPU memory, disk, bandwidth, task duration, queue depth, and retry limits. Missing measurements are UNKNOWN, never zero or unlimited.
5. **Resilience:** test process crash, host restart, disk-full, clock skew, network partition, corrupt input, unavailable provider, expired credential, and failed rollback in isolated environments.
6. **Recovery:** document backup frequency, restore procedure, recovery point objective (RPO), recovery time objective (RTO), and evidence from an actual restore drill.
7. **Security review:** test authentication and authorization on every route; scan dependencies and artifacts; review secrets exposure and key revocation; record unresolved findings.
8. **Pilot:** begin with one explicitly owned, non-critical local node and read-only observation. Require a human approval gate for any action with external effects.
9. **Release decision:** require a reviewed change, exact immutable artifact digest, successful CI on that digest, signed provenance, rollback plan, operational owner, and explicit release approval. No CI-only production claim.
10. **Operations:** monitor availability, error rates, saturation, queue age, integrity, security events, recovery readiness, and cost. Publish incident and change records.

### KPI catalogue: formulas, units and evidence

KPI values are **not pre-filled with invented measurements**. Each value must be computed from a cited source and a defined measurement window. A KPI without adequate data is UNKNOWN.

| KPI | Definition / calculation | Unit | Required evidence |
|---|---|---|---|
| Service availability | successful eligible probes / all eligible probes × 100 | % per window | Probe log, probe policy, clock source |
| Request success | successful requests / total valid requests × 100 | % | Application counters and error classification |
| P95 latency | 95th percentile of end-to-end request duration | ms | Timestamped request histogram |
| Error rate | failed eligible requests / total eligible requests × 100 | % | Application metrics |
| Queue age | now − enqueue timestamp for oldest pending task | seconds | Queue records and synchronized clock |
| Queue completion | completed valid tasks / accepted valid tasks × 100 | % | Task lifecycle ledger |
| Resource headroom | (limit − observed use) / limit × 100 | % per resource | Direct CPU/RAM/GPU/disk/network readings |
| Energy intensity | measured energy / completed useful work | Wh per task or kWh per unit | Calibrated meter and workload counter |
| Water intensity | measured water consumed / useful output | L per unit | Metered water and output data |
| Recovery time | service restored time − incident start time | minutes | Timed restore drill |
| Recovery point | incident time − latest successfully restored data point | minutes | Backup and restore evidence |
| Integrity verification | verified records / records checked × 100 | % | Ledger verifier output and record range |
| Evidence completeness | observations with all mandatory provenance fields / observations sampled × 100 | % | Schema validator report |
| False-positive rate | false alerts / all alerts classified after review × 100 | % | Alert labels and review window |
| Autonomy ratio | eligible work completed locally / all eligible work × 100 | % | Local and peer task ledgers; fixed eligibility rules |
| Provider concentration | largest provider's eligible workload / total eligible workload × 100 | % | Provider-attributed workload records |
| Network dependency | successful critical local operations while WAN unavailable / tested critical local operations × 100 | % | Controlled offline exercise |
| Biodiversity / ecological impact | project-specific field indicators against a declared baseline | native units | Field protocol, sampling design, independent source |

### Geometry and network-topology KPIs

“Geometry” is treated as measurable topology, not as a decorative score. Compute these only from an explicit, consented node-and-link inventory:

- **Node count:** number of active, authenticated, opted-in nodes (count).
- **Link density:** observed links divided by all possible undirected links, 2E / (N(N−1)) for N > 1 (ratio).
- **Mean degree:** 2E / N for an undirected graph (links per node).
- **Component count:** number of disconnected connected components (count).
- **Largest-component share:** nodes in largest connected component / all eligible nodes (ratio).
- **Path redundancy:** number of edge-disjoint paths between declared critical node pairs (count); report pairs and algorithm.
- **Provider concentration / centrality:** share of workload or traffic dependent on the most central node/provider (ratio); disclose the centrality method.
- **Geographic diversity:** distribution across declared regions, only where location collection is lawful and necessary (count/share; never infer precise location).
- **Partition recovery:** time until authenticated connectivity is restored after a controlled test partition (seconds).

Do not optimize for maximum connectivity. A safer network can deliberately isolate a compromised node. Topology collection is opt-in, privacy-minimized, and read-only by default. A node count or graph score does not prove trustworthiness, independence, or resilience.

### Frequency, signal and timing KPIs

Frequency is not a universal “system frequency” and must always identify the measured physical or logical layer:

- **Sampling frequency:** samples per second (Hz), with sensor, calibration, and anti-aliasing details.
- **Signal frequency / spectrum occupancy:** Hz and occupied bandwidth in Hz, measured only with lawful receive-only equipment or authorized test equipment.
- **Mains frequency:** Hz, with location, instrument, sampling interval, and tolerance; never use a software estimate as a safety measurement.
- **Clock drift:** offset and drift rate relative to a declared trusted time source (ms and ppm).
- **Network throughput:** bit/s; **latency:** ms; **jitter:** ms; **packet loss:** %.
- **Model token rate:** tokens/s, with exact model, quantization, hardware, prompt/output lengths and runtime revision.

V91 must not transmit on radio frequencies, alter public networks, or interfere with communications. Any RF transmission or spectrum test requires lawful spectrum access, suitable equipment, and separate authorization. Missing calibration or source metadata means UNKNOWN.

### KPI quality rules

- Store raw values; never overwrite them with normalized or estimated values.
- Label each value DIRECT, CALCULATED, ESTIMATED, or MANUAL.
- Record unit, formula version, sample count, time window, uncertainty, and source.
- Do not compare values with different units, windows, workload definitions, or hardware without an explicit normalization method.
- Show median and spread where useful; do not hide outliers.
- Do not convert a score into a pass/fail safety decision without a validated threshold and review.
- A KPI improvement is accepted only when the baseline and after-period are comparable and the measurement uncertainty is disclosed.

### Safe implementation order for missing components

Implement in small, independently reviewable increments: (1) schemas and provenance; (2) read-only local collectors; (3) KPI calculation and fixture-based tests; (4) authentication coverage map and route tests; (5) backup/restore drill; (6) signed artifact verification; (7) opt-in peer protocol in a disposable test network; (8) resource adapters for additional hardware; (9) independent security and operational review. Do not combine these into one large untestable change.

### Operational status declaration

At the time of this documentation change, production operation remains **NOT VERIFIED**. The repository contains useful experimental and locally bounded components, but the missing capabilities above must be implemented and independently tested before a production claim. No live deployment, fleet, radio network, global control plane, or autonomous world-scale effect is asserted.
