# V91 Local Resilience Mesh (verify-only)

**Status: IMPLEMENTED AS TESTED LOCAL MODULE. NO DAEMON, NO NETWORK TRAFFIC, NO RESTARTS. VERIFY != RESTART, DETECTION != AUTHORIZATION.**

## What it does

- `MeshRegister`: local peer register with HMAC-SHA256-signed entries (canonical JSON). Tampered entries and foreign-key entries are rejected via `verify_peer()`.
- `resolve_key()`: fail-closed — the HMAC secret comes only explicitly or from `V91_MESH_KEY`, minimum 32 bytes, **no default key**.
- `RestartVerifier` / `verify_local_units()`: read-only verification of the local units defined in `v99/os` (PR #60): `systemctl is-active` (linux), `launchctl list` (darwin), `schtasks /query` (win32). The command runner is **injected** — tests never touch a real system, and the module itself runs no shell.
- Honest result model: `VERIFIED_ACTIVE` only from returncode 0, `NOT_ACTIVE` from a clean nonzero answer, `UNKNOWN` when the runner fails. UNKNOWN is never PASS.

## What it deliberately does NOT do

- No daemon, no listening port, no mesh network traffic. Peers are registered entries; a real transport is a separate, opt-in phase.
- No restarts, no isolation, no reconfiguration: the operator decides and acts (`DETECTION != AUTHORIZATION`).
- `VERIFIED_ACTIVE` is a reported check result on one machine: `SHIPPING != INSTALLATION` still applies.

## CLI

```
V91_MESH_KEY=<32+ bytes> python -m controller.resilience_mesh --platform linux
```
Exit 2 = FAILED_CLOSED (missing/short key, unknown unit).
