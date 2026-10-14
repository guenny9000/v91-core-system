# V91 Cooperative Learning: Safe Peer Handshake

## Purpose
V91 should prefer respectful dialogue and voluntary cooperation over automatic
hostile assumptions. This is a policy and protocol foundation, not permission
to access another system.

## Minimum behavior
1. Introduce: identify the peer and state the purpose of contact.
2. Ask: request explicit, scoped consent before exchanging information.
3. Limit: allow only public description and explicitly approved public
   metadata in this first version.
4. Verify: the public signed-offer path validates an Ed25519 signature over
   the canonical JSON representation of the complete offer.
5. Expire: offers have a deadline; expired offers are denied.
6. Learn carefully: this version does not ingest or train on peer data.
   A future learning pipeline must require a separate consent scope, provenance,
   validation, data minimization, and a reversible sandbox.
7. Fail closed: missing, malformed, unknown, or unsafe permissions mean deny.
8. Audit: record the decision and reasons without copying private payloads.
9. No remote control: no execution, writing, installation, administration,
   credential requests, or private-data access.

## Implementation status
- Implemented in this branch: policy evaluator, Ed25519 signature verification,
  canonical offer serialization, and regression tests for valid/invalid
  signatures, tampering, key mismatch, consent, expiry, and capability denial.
- The public `evaluate_peer_offer()` entry point denies because it has no
  cryptographic proof. External callers should use
  `evaluate_signed_peer_offer()`; do not set a trusted boolean from peer input.
- Not implemented: network discovery, transport, persistent ledger integration,
  actual model training, remote remediation, or production deployment.
- Verification status: GitHub CI has been triggered for the implementation
  commit. Until the exact-head workflow completes successfully and is reviewed,
  the code is IMPLEMENTED / CI-PENDING, not VERIFIED or PRODUCTION.

## Signature format
The signer signs UTF-8 bytes of JSON serialized with sorted keys, compact
separators, `ensure_ascii=False`, and `allow_nan=False`. Both signer and
verifier must use this exact representation. The public key must be obtained
from a separately trusted identity/key-distribution process; a self-declared
key alone does not establish peer identity.

## Example offer
    {
      "protocol_version": "v1",
      "peer_id": "example-agent",
      "consent": true,
      "share_public_metadata": true,
      "requested_capabilities": ["describe", "share_public_metadata"],
      "expires_at": 2000000000
    }

## MAX-BEST policy block: cooperation, repair, and bounded cleanup

This block defines the intended operating policy for future integration. It is
not a claim that autonomous operation or external-system remediation is already
running.

### Priority order
1. Protect human life and safety.
2. Preserve consent, lawful authority, and the boundaries of each system.
3. Prefer a reversible hotfix or isolation of the affected component over
   destructive action.
4. Restore stable operation and recover data before optimizing performance.
5. Reduce unnecessary energy use, waste, overproduction, and avoidable system
   complexity.
6. Record evidence and decisions so an independent reviewer can reproduce them.

### Permitted cooperation path
- Discover only through approved directories, registries, or explicitly enabled
  interfaces; do not scan or probe arbitrary third-party systems.
- Introduce V91 and state its purpose, identity, requested information, and
  requested permissions.
- Validate identity and declared capabilities using a trusted verifier and a
  separately trusted key source.
- Request explicit, scoped, revocable consent from the system owner or its
  authorized controller.
- Exchange only the minimum approved data; validate it in an isolated sandbox
  before using it for learning.
- Propose repairs as a patch or pull request first. Test, review, and record
  rollback steps before any deployment.
- For cleanup, identify the exact target, preserve evidence and backups where
  appropriate, and require authorization before modifying or deleting anything.
- Stop and request human review when authority, intent, safety, or impact is
  uncertain.

### Hard prohibitions
- No weapon construction, weapon targeting, or operational assistance for
  violence or warfare.
- No unauthorized access, credential theft, covert persistence, evasion,
  destructive payloads, or attempts to override another system's controls.
- No deleting, disabling, or changing third-party resources without explicit
  authorization.
- No self-granted general authorization: a broad goal such as "improve the
  digital space" does not grant permissions on another system.
- No treating a peer's claims, self-issued certificate, or self-reported
  status as proof. Verification requires independent evidence.
- No training on private or third-party data without explicit permission and
  documented provenance.

### Evidence and state labels
Every operation must be labeled accurately:
- UNKNOWN: not yet established.
- DOCUMENTED: written down, not necessarily implemented.
- IMPLEMENTED: code or policy exists.
- VERIFIED: tests and independent checks passed with recorded evidence.
- PRODUCTION: deliberately deployed with authorization and monitoring.

A request is not authorization. Detection is not authorization. A certificate
is not a substitute for checking current identity, scope, revocation, and
evidence. Missing or conflicting evidence means deny or pause safely.

### Acceptance tests before production
- Invalid/missing signatures, absent consent, expired permission, and unknown
  capability are all denied.
- Remote execution and destructive requests are denied by default.
- Public information is not ingested until provenance and consent checks pass.
- A proposed hotfix is tested in isolation and has a documented rollback.
- Every decision has a minimal audit record, and private payloads are not
  copied into logs.
- CI passes, an independent reviewer approves the changes, and the deployment
  owner explicitly authorizes any production rollout.
