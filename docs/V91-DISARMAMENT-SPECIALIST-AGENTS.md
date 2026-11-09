# V91 Disarmament Specialist-Agent Architecture

**Status: IMPLEMENTED AS A DETERMINISTIC PHASE-1 AGENT COUNCIL.** The agents operate only on supplied normalized records. They do not independently fetch sources, call external models, or execute operations.

## Why a single script is insufficient

A fetcher only retrieves bytes. It cannot decide treaty compliance, verify dismantlement, distinguish civilian from military space infrastructure, or reconcile conflicting inventories. Those are separate tasks requiring independent domain expertise and independent evidence trails.

## Specialist agents

The initial council contains eight isolated specialists:

1. Treaty obligations and treaty-status agent.
2. Nuclear arsenal and reduction agent.
3. Conventional arms, stockpiles, and transfers agent.
4. Autonomous-weapons governance agent.
5. Space-security and civilian-protection agent.
6. Military-production and expenditure conversion agent.
7. Humanitarian and environmental safeguards agent.
8. Evidence provenance and quality audit agent.

A single record may be routed to multiple agents. Each emits a structured finding, its evidence references, limitations, and a human-review next step.

## Council rules

- Agents receive the same supplied normalized records; they cannot mutate the input.
- A specialist cannot upgrade a supplied evidence grade.
- The coordinator does not use majority voting to decide truth.
- Conflicting assessments are surfaced for human review.
- Missing or malformed grades become UNKNOWN.
- No records means UNKNOWN, not PASS.
- The council cannot claim a complete global inventory or global disarmament.
- No network, shell, credential, weapon, military-network, satellite-command, or deorbit capability is present.

## What this is and is not

This is a real executable multi-agent software structure, but the current specialists are deterministic routing and assessment components, not autonomous LLM agents. They do not yet possess their own model, memory, scheduler, independent data connectors, or persistent audit identities.

## Next phases

1. Separate source adapters for treaty registries, SIPRI datasets, IAEA, OPCW, CTBTO, UN arms-transfer reporting, and space-security publications.
2. Give each specialist a separately versioned input contract, evidence store, and run identity.
3. Add independent source acquisition with allowlists, TLS verification, byte limits, redirect controls, timeouts, rate limits, and content hashing.
4. Anchor snapshots in a real append-only/WORM-capable storage service or externally witnessed Merkle log. A JSONL append file alone is not WORM.
5. Add conflict-resolution workflows with human adjudication and signed review receipts.
6. Add a scheduler and deployment only after security review, CI, operational monitoring, and recovery drills.

No live feeds are connected by this phase. No external disarmament action is claimed.
