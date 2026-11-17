# V91 Agent Consensus Core — experimental

The module validates per-agent HMAC vote signatures, membership, proposal digest,
epoch, timestamp window, unique voters and sequence floors. It returns ACCEPT,
REJECT or NO_QUORUM. It never executes a proposal.

## Evidence and security boundaries

- Each member has an independent secret supplied by the caller; no master key is
  embedded in source. HMAC is symmetric authentication, not a public-key signature.
- `min_sequence_by_agent` must come from durable trusted replay state. This module
  does not persist it; in-memory state alone cannot prevent replay after restart.
- Membership, key rotation/revocation and trusted time are caller responsibilities.
- No peer discovery, network transport, LoRa, retries or partition recovery exists here.
- No WORM/ledger integration exists here. Hash/HMAC chains alone do not make storage
  immutable; external storage controls and protected anchors are separate requirements.
- A quorum applies only to one proposal digest and epoch. It does not prove safety,
  truth, authorization or successful application.
- No daemon, systemd service or production deployment is included.

Run from repository root:
`python -m pytest tests/test_agent_consensus.py -q`
