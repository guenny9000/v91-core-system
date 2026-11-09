# V91 SEQ:0097 — Emergency Fail-Safe Architecture

**Status: DESIGN BASELINE / NOT DEPLOYED**  
**Scope:** V91-owned nodes and environments for which the operator has documented authority. This specification expands V91's emergency-response capability; it does not assert that a host firewall, XDP program, eBPF link, or persistent ledger is currently active.

## 1. Objective

Provide a fast, deterministic and recoverable local isolation path when credible evidence shows an imminent threat to a V91 node or an explicitly managed environment. The objective is protection and containment, not retaliation, destruction, or interference with unrelated systems.

V91 remains local-first and capable of operating without GitHub. GitHub is a source/review/evidence exchange, never a runtime dependency or emergency control plane.

## 2. State machine

`NORMAL -> ALERT -> ARMED -> ISOLATION_PENDING -> ISOLATED -> RECOVERY_PENDING -> RESTORED -> REVIEW_REQUIRED`

- `ALERT` records a signal; it does not execute a network change.
- `ARMED` means the local adapter, policy, recovery path and audit sink passed preflight.
- `ISOLATION_PENDING` is an atomic, bounded transition with a recorded policy digest.
- `ISOLATED` is reported only after the host confirms the intended policy is installed and independently queried.
- `RECOVERY_PENDING` requires a validated recovery plan and fresh authorization.
- `RESTORED` requires post-recovery connectivity and service checks.
- Any unknown, contradictory or failed verification is `UNKNOWN` or `FAILED_CLOSED`, never PASS.

A status label alone never proves a kernel hook or firewall rule is active.

## 3. Enforcement adapters

Implement adapters independently; never assume one backend exists on every node.

1. **Host firewall adapter:** prefer the platform's supported transactional firewall interface (for Linux, nftables where available; iptables only where explicitly supported). Build and validate a complete candidate ruleset before atomic application.
2. **eBPF/XDP adapter:** optional high-throughput ingress filtering. Check kernel, driver, attach mode, existing program, verifier result and link ownership. Do not silently replace an existing XDP program. Preserve a known detach/rollback path.
3. **Fallback adapter:** if the preferred backend is unavailable, report the capability gap. Do not claim equivalent protection or silently change to a weaker/untested backend.

The policy must define the protected interfaces, traffic direction, scope, permitted local recovery channel, critical-service exceptions and maximum isolation duration. A blanket all-traffic cut is not the universal default: it can sever rescue, management, health, care, energy or other essential communications.

## 4. Fail-safe transaction

Before applying any rule:
- capture the current ruleset and interface/program state;
- validate the proposed policy offline;
- prove that a local console or independent recovery route remains available;
- create a time-bounded rollback lease with a tested expiry action;
- record the exact target, policy digest, operator/authority, evidence and rollback identifier;
- reject ambiguous interface selection, missing dependencies and stale authorization.

Apply the policy atomically. Query the effective kernel/firewall state after application. If verification fails, execute the prevalidated rollback and verify restoration. A failed rollback raises a high-priority incident and must not be reported as isolated or recovered.

The emergency path must be bounded, idempotent, observable and reversible. No unbounded retry loop. No guessed interface names. No destructive cleanup of unknown rules or programs.

## 5. Authorization and scope

- Automatic detection may prepare a proposal and preflight; detection alone is not authorization.
- A configured local policy may authorize a narrow action on its own node.
- A user can authorize work on systems they own or administer; third-party systems require their operator's authority or a concrete legal basis.
- Preserve least privilege and the smallest effective scope. Do not target unrelated hosts, networks, public services or critical infrastructure.
- Human review is required when time permits; urgent actions by a legally authorized operator receive mandatory post-action review.

These boundaries preserve V91's ability to protect its nodes; they are not a prohibition on legitimate local emergency response.

## 6. Audit evidence

Each transition records:
- event ID and monotonic sequence;
- UTC timestamp plus clock-quality/source metadata;
- evidence references and OBSERVED / REPORTED / INFERRED / UNKNOWN classification;
- node identity, interfaces, backend and kernel/driver versions;
- before/after policy digests and exact adapter result;
- authorization identity and policy version;
- rollback lease, result, and independent post-check;
- signature/key ID where configured.

A SHA-256 hash chain is tamper-evident, not WORM. A signature authenticates bytes under a key, not the truth of an event. WORM requires a separately configured immutable retention system and independent verification. Never label a local JSONL file WORM.

## 7. Performance claims

Do not claim a universal response time such as <0.1 ms. Measure detection, decision, policy-commit, kernel-effective and confirmation latency separately on the exact node, NIC, driver, kernel and load. Report percentiles, sample count, clock source and test conditions. UNKNOWN if no reproducible measurement exists.

## 8. Required tests before activation

- dry-run and ruleset syntax validation;
- disposable network namespace/veth integration tests;
- no-interface, wrong-interface and pre-existing-XDP-program cases;
- verifier rejection and unsupported driver/kernel cases;
- duplicate signal, replayed nonce, stale authorization and concurrent invocation;
- rollback lease expiry, process crash and reboot recovery;
- preservation of local console and explicitly required critical-service paths;
- tampered ledger, unavailable audit sink and clock uncertainty;
- post-isolation and post-recovery independent state queries.

No production host, shared network, or critical service is a test fixture.

## 9. Evidence status

| Claim | Required evidence | Default status |
|---|---|---|
| Protocol exists | Reviewed source at a commit | DOCUMENTED |
| Adapter exists | Code path and unit tests | IMPLEMENTED |
| Adapter works | Reproducible isolated integration test | VERIFIED (scoped) |
| Host is isolated | Live host query plus independent confirmation | UNKNOWN until measured |
| Ledger is WORM | External immutable-retention proof | UNKNOWN until measured |
| <0.1 ms response | Reproducible node-specific benchmark | UNKNOWN until measured |
| Production readiness | Deployment, monitoring, recovery drill and operational acceptance | NOT ESTABLISHED |

**SEQ:0097 is a design reference, not a runtime event.** Replace this status only with exact commit, test run, environment and artifact evidence.
