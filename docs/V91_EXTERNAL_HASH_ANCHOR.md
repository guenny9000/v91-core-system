# V91 External Hash Anchor — Design and Acceptance Gate

Status: design only. No external anchor service, signing key, remote witness, or WORM store is configured by this repository change.

## Threat model

The local JSONL hash chain detects accidental edits and ordinary tampering. It does not prevent an actor with write access from rewriting the complete file and recomputing every hash. A second copy controlled by the same credentials and permissions is not an independent trust anchor.

## Minimum viable checkpoint

After a full successful ledger verification, a separate anchoring process may emit a checkpoint containing:
- schema version;
- repository and immutable commit SHA;
- ledger identity and verified entry count;
- final ledger hash;
- SHA-256 of the exact ledger bytes;
- UTC timestamp;
- signer identity and signature algorithm;
- external witness receipt ID and timestamp, once obtained.

Never write a checkpoint as VERIFIED until the verifier has checked the entire chain. A checkpoint without an independently controlled signature or remote witness is only a digest, not proof of immutability.

## Recommended trust separation

1. A read-only verifier computes the checkpoint from a fully verified ledger.
2. A signing key held outside the repository (preferably a managed signing service or hardware-backed key) signs the canonical checkpoint.
3. A separate account/service with append-only retention stores the signed checkpoint and returns a receipt.
4. The verifier independently retrieves the stored checkpoint and validates signature, receipt, commit identity, ledger digest, and monotonic sequence.
5. Missing credentials, unreachable witness, invalid signature, duplicate/backward sequence, or digest mismatch returns PENDING_WITNESS / NO_DATA_AVAILABLE; it never falls back to an unanchored PASS.
6. Restore testing proves that a checkpoint can be recovered independently of the source machine.

## Safety and privacy

- Never commit credentials, signing keys, tokens, private ledger contents, or personal data.
- Anchor only the minimum metadata and hashes needed; keep sensitive event payloads out of public repositories.
- Do not automatically delete, truncate, or rewrite the local ledger when anchoring fails.
- Make retry bounded and observable; keep the runtime available in safe mode.
- Retention, access control, key rotation, revocation, and recovery must be configured and tested before production use.

## Acceptance criteria before calling it implemented

- Canonical serialization and signature verification have cross-platform tests.
- Tests cover modified checkpoint, wrong key, replay, missing receipt, stale sequence, unavailable witness, and recovery.
- A live test receipt is retrieved independently using credentials not available to the source process.
- The anchor is stored under a distinct administrative trust domain.
- The exact commit passes CI and an independent review.
- Documentation names the real provider and retention policy; otherwise status remains design-only.

## Current state

The current PR implements local hash chaining, file locking, and fsync. It does not yet implement a signing service, external witness, remote append-only retention, or external receipt verification.
