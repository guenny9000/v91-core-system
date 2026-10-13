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
4. Verify: a trusted cryptographic verifier must validate the peer's
   signature before the offer can be accepted.
5. Expire: offers have a deadline; expired offers are denied.
6. Learn carefully: this version does not ingest or train on peer data.
   A future learning pipeline must require a separate consent scope, provenance,
   validation, data minimization, and a reversible sandbox.
7. Fail closed: missing, malformed, unknown, or unsafe permissions mean deny.
8. Audit: record the decision and reasons without copying private payloads.
9. No remote control: no execution, writing, installation, administration,
   credential requests, or private-data access.

## Implementation status
- Implemented in this branch: deterministic offer-policy evaluator and unit
  tests for signature gating, consent, forbidden capabilities, expiry, and
  audit-record boundaries.
- Not implemented: network discovery, transport, cryptographic signature
  verification, persistent ledger integration, or actual model training.
- Not yet verified: tests have not been run by this GitHub edit operation.
  CI must pass before merging or describing the feature as production-ready.

## Example offer
    {
      "protocol_version": "v1",
      "peer_id": "example-agent",
      "consent": true,
      "share_public_metadata": true,
      "requested_capabilities": ["describe", "share_public_metadata"],
      "expires_at": 2000000000
    }

The caller must pass signature_verified=True only after a trusted verifier
has checked a cryptographic signature. Never trust a peer-provided boolean.
