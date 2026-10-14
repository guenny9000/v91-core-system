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

## Next milestones

1. Add an offline smoke test proving that core validation does not require network access.
2. Add negative tests for missing or malformed evidence, invalid units and non-finite values, stale sources, and unsupported success statuses.
3. Produce a machine-readable evidence report with the exact revision, command, environment, timestamp, test result, and artifact hash.
4. Test signed updates, key revocation, rollback, least privilege, and resource ceilings.
5. Run one small, safe local pilot before making claims about real-world impact.

## License

See the repository's license and ownership notices for applicable terms.
