# V91 Local Emergency Stop (Issue #70)

**Status: IMPLEMENTED AS A TESTED LOCAL PRIMITIVE; NOT WIRED INTO ANY RUNTIME ENTRY POINT (SCRIPTED != INSTALLED).**

## What it does

`controller/emergency_stop.py` provides `LocalEmergencyStop`:

- **Atomic stop flag:** activation writes a temp file, fsyncs, then `os.replace` — the flag is never half-written.
- **Reason-bound confirmation:** activate/reset require `HMAC-SHA256(key, domain || reason)`; a confirmation for one reason or domain is useless for another.
- **HMAC-chained ledger:** every action appends one JSONL entry; `verify_ledger()` recomputes the full chain, and reset is refused when the chain is broken.
- **Fail-closed everywhere:** key missing/short (< 32 bytes, env `V91_EMERGENCY_KEY`) refuses startup; an unreadable flag counts as STOPPED, never as RUNNING.

## Scope and limits

- Affects ONLY the local V91 instance via its flag file. No network calls, no external processes, no third-party systems, no platform effects.
- The key holder (the operator) can always confirm or refuse an activation; the module never decides on its own.
- The ledger is local HMAC state, not a distributed WORM store; privileged filesystem rollback is out of scope and detectable only via the chain.
- Runtime wiring (checking the flag at the real entry point, e.g. the cycle scheduler) is the explicitly separate next step.

## Tests

`tests/test_emergency_stop.py`: 9 unit tests — activate/reset happy paths, wrong confirmation, wrong domain, reason binding, tampered ledger refusal, short/missing key, unreadable flag fail-closed, env-key path.