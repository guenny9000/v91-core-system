# V91 Peer Synchronization MVP

**Status: IMPLEMENTED IN BRANCH; NOT YET VERIFIED BY CI OR MERGED.**

This milestone adds a transport-independent local validator for signed peer
heartbeats. It is intentionally not a running swarm and does not open sockets,
start background threads, call external services, execute peer content, or
grant remote authority.

## Implemented behavior

- Canonical JSON serialization and HMAC-SHA256 message authentication.
- Explicit key ID to peer ID binding in a locally configured trust map.
- Schema, field, capability, timestamp, and signature validation.
- Monotonically increasing per-peer sequence numbers for replay rejection.
- Configurable heartbeat age and future-clock-skew limits.
- Peer states: ALIVE_VERIFIED, STALE, INVALID, and UNKNOWN-by-absence.
- On-demand stale marking; no polling loop or persistent daemon.

## Important security boundary

This MVP uses **symmetric HMAC keys**. It is suitable for controlled local
protocol tests, but does not provide public-key identity, non-repudiation,
secure key distribution, key rotation, or revocation. Those require a separate
reviewed design. A valid HMAC proves only that the message matches a configured
shared secret; it does not prove the peer's software is healthy or truthful.

The registry is in-memory. It does not persist peer state or secrets. The
caller is responsible for secure key storage and for supplying a trustworthy
clock. A verified heartbeat establishes only that an authenticated, fresh
message was received, not that the peer is generally healthy.

## Local verification

Run from the repository root:

```bash
pytest -q tests/test_peer_sync.py
```

The tests cover valid messages, tampering, unknown keys, peer/key binding,
replay, stale messages, future timestamps, stale transition, and defensive
state snapshots.

## Next gates

1. Run tests and lint in CI on this branch.
2. Review HMAC MVP limitations and decide whether Ed25519 is required before
   any network transport is added.
3. Add explicit key enrollment, rotation, revocation, and storage design.
4. Add a loopback transport only after the protocol review; retain offline-first
   behavior and never execute peer-supplied code.
5. Keep all remote actions behind separate authorization and human-reviewed
   promotion gates.

Related requirement: [Issue #37](https://github.com/guenny9000/v91-core-system/issues/37).
