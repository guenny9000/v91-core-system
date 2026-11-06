# V91 Capability-Aware Model Autonomy

**Status: DOCUMENTED / IMPLEMENTATION REQUIRED.** This specification defines a distributed, local-first design. It does not claim that a model runner, federation, distributed storage, or lock service is already deployed.

## 1. Objective

V91 autonomy belongs to each participating node, not to one powerful computer or central server. A node may be a local model, a remote model service, a workstation, a server, or a constrained device. Each node contributes only the compute, memory, storage, network, and verification capabilities it can actually provide.

A participant with limited GPU memory is not a failure and must not be treated as the system's bottleneck. It may run a smaller model, verify metadata, retain a small encrypted record set, or request an authorized peer to perform a task or store an encrypted object. A participant with no spare capacity simply does not accept that work.

## 2. Core invariants

1. **Local-first:** each node can inspect its own configuration, verify local records, and continue local work without GitHub, cloud control planes, or peer availability.
2. **Capability honesty:** advertised capacity is a time-bounded claim; actual admission uses fresh local measurements and hard quotas. Missing measurements are UNKNOWN, never unlimited capacity.
3. **No mandatory hardware profile:** no RTX 5080, GPU, large RAM pool, or always-on coordinator is required.
4. **Opt-in contribution:** storage, compute, indexing, and data sharing are independently enabled by the resource owner. No peer may silently consume another node's resources.
5. **Deterministic verification:** inputs, model artifact, tokenizer, runtime, inference parameters, seed, precision/quantization, and relevant backend settings are pinned in a run manifest. The result is reproducible only to the level actually demonstrated by the selected backend.
6. **Independent verification:** a model cannot certify its own output as independently verified. A separate verifier replays or checks the result against the declared verification contract.
7. **Integrity is not truth:** hashes detect byte changes; signatures bind bytes to a key; neither alone proves the source data is true or the model reasoning is correct.
8. **No authority by message:** capability advertisements, heartbeats, model outputs, storage receipts, and lock requests do not grant execution or administrative authority.
9. **Bounded operation:** per-node CPU, RAM/VRAM, disk, bandwidth, task size, retention, concurrency, and retry budgets are explicit and enforced locally.
10. **Safe degradation:** peer loss, storage exhaustion, or network partition reduces optional cooperation only. It must not disable the node's local safety checks or corrupt its known-good records.

## 3. Capability manifest

Each node publishes a signed, versioned capability manifest containing:
- stable node and key identifiers, schema version, software build and expiry;
- model runner identifiers and exact model/tokenizer artifact digests where applicable;
- supported inference features, deterministic mode availability, precision and backend constraints;
- measured available CPU, RAM, VRAM, disk and bandwidth, each with units, source, timestamp and confidence;
- maximum accepted task size, concurrency, storage quota, retention window and allowed data classes;
- separately enabled contributions: compute, verification, encrypted object storage, metadata/index service;
- policy version, trust state, and revocation information.

Manifests are advertisements, not promises. The receiver validates schema, signature, key binding, freshness, quotas and policy before using them. A peer's own statement that it is trusted is never sufficient.

## 4. Deterministic model runner

The runner is a bounded, replaceable adapter. It must not execute arbitrary instructions supplied by a model or peer.

A run record pins:
- model name and immutable artifact digest;
- tokenizer and vocabulary digest;
- inference engine and version;
- runtime/container digest and relevant library versions;
- prompt/input digest and declared data classification;
- sampling settings, seed, context limits and output limits;
- precision, quantization, device/backend and deterministic-kernel settings;
- start/end time, exit status, output digest and verification method.

The runner exposes explicit states: NOT_AVAILABLE, READY, RUNNING, COMPLETED_UNVERIFIED, VERIFIED_EXACT, VERIFIED_WITH_TOLERANCE, NONDETERMINISTIC, FAILED, and UNKNOWN.

Exact reproducibility is only claimed when independent replay yields the same canonical output under the pinned conditions. If GPU kernels, hardware, quantization, parallel scheduling or provider internals prevent bit-identical replay, the result must say so and use a declared tolerance or semantic test. A similarity score is not exact determinism. A signed run record proves which key signed the record, not that the model answer is correct.

## 5. Cooperative compute and storage

A scheduler may select peers only from fresh, verified capability manifests. Selection is local policy, capability-aware, and revocable. The owner can set contribution limits or withdraw at any time.

Storage uses content-addressed objects:
- compute a digest before transfer and verify it after receipt;
- encrypt private or user-controlled data before it leaves the owner's node;
- keep encryption keys under owner control, never in public manifests;
- enforce per-owner quotas, expiry, retention and deletion requests;
- return a signed receipt containing object digest, byte count, storage node, policy, and expiry;
- replicate only to explicitly authorized peers and only within the owner's replication policy.

A storage receipt is evidence of a peer's signed acknowledgement, not proof of perpetual availability. Availability requires fresh challenge/verification or retrieval evidence. If no suitable peer is available, retain locally if possible or report NO_CAPACITY; never silently upload to an unrelated service.

## 6. Distributed locks and write coordination

Locks are short-lived leases, not permanent flags. Each lease contains resource key, owner identity, monotonically increasing fencing token, issued/expiry times, scope and signature.

- The resource owner or explicitly trusted coordinator issues leases.
- A writer must present the newest fencing token; stale holders are rejected.
- Lease expiry is bounded and uses a defined clock-skew allowance.
- A partitioned node cannot extend a lease by itself.
- Conflicting writes are preserved as CONFLICT; no silent last-writer-wins overwrite for protected records.
- Critical local state remains writable through a local append-only journal where policy permits; synchronization can reconcile later.
- A peer cannot lock another participant's machine, processes, or data merely by sending a lock request.

## 7. Trust, identity and verification

Use independently provisioned Ed25519 trust roots for peer identity and signed manifests. Support key activation, rotation, expiry and revocation. HMAC may be used only inside a deliberately shared-secret trust domain and must not be described as public-key identity or non-repudiation.

Every accepted artifact passes schema validation, signature verification, digest verification, freshness checks, authorization checks, quota checks and malware-safe data handling. Data remains data; no downloaded model output or artifact is executed automatically.

For high-impact claims, use a second independent verifier with a separately controlled trust path. If independent verification is unavailable, retain UNVERIFIED or UNKNOWN.

## 8. Privacy and ownership

- Data ownership and access scope remain with the contributing user or operator.
- Default sharing is off for private data; public, internal, confidential and personal data classes are distinct.
- Share only the minimum required object or derived result.
- No training, retention, indexing, or onward sharing is inferred from a compute request.
- A participant can decline a task without losing access to its own local system.
- Revocation stops future access and replication; already copied data requires a defined deletion/cryptographic-erasure process and honest reporting.

## 9. Implementation stages and acceptance tests

### Stage A — schema and deterministic local verification
- [ ] Validate capability manifest schema, bounds, units, expiry and unknown fields.
- [ ] Canonical serialization and Ed25519 signature verification.
- [ ] Reject stale, forged, revoked, malformed and over-quota manifests.
- [ ] Create a pinned model-run manifest and distinguish exact, tolerance-based and non-deterministic outcomes.
- [ ] Add tests for missing model artifacts, changed tokenizer/runtime, changed seed, and output mismatch.

### Stage B — local resource admission
- [ ] Read actual local resource measurements through named platform adapters.
- [ ] Enforce CPU/RAM/VRAM/disk/task quotas before admission.
- [ ] Refuse work safely when measurements are missing or stale.
- [ ] Prove no task exceeds configured limits under load.

### Stage C — two-node cooperative test
- [ ] Two isolated test nodes exchange signed capability manifests.
- [ ] A task is accepted only when the receiving node opts in and has capacity.
- [ ] Peer loss leaves both local cores operational.
- [ ] Independent verifier checks the run record; model self-attestation alone fails.

### Stage D — encrypted storage and lease locks
- [ ] Verify encrypted object transfer, content digest and signed receipt.
- [ ] Test owner revocation, expiry, quota exhaustion and unavailable storage.
- [ ] Test fencing tokens, stale lease rejection, clock skew and network partition.
- [ ] Prove protected records are never silently overwritten.

### Stage E — independent review and release
- [ ] Security/privacy review, threat model and recovery test.
- [ ] Reproducible test report with exact commit, environment, commands, exit codes and artifact hashes.
- [ ] Production status only after deployment and operational evidence.

## 10. Explicit non-goals and safety boundaries

This protocol does not create a global AI, promise unlimited compute/storage, or make every model deterministic across all hardware. It does not authorize arbitrary remote execution, remote shell, model training on shared data, unilateral locking, destructive action, or access to third-party systems. Emergency response remains governed by the separate V91 emergency/defense protocol and applicable authority.

**Current evidence:** existing repository modules include a deterministic model admission gate, peer heartbeat validation, and trusted Ed25519 key lookup. They do not yet implement this complete capability-aware runner, cooperative encrypted storage, distributed lease locks, or end-to-end multi-node verification. See the linked issues for implementation work.