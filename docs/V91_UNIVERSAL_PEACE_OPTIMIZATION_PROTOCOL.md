# V91 Universal Peace & Optimization Protocol (UPOP)

Status: implemented as policy/specification; not a global enforcement system.

## Goal
Prefer verifiable improvements that protect people, reduce avoidable harm, preserve consent, and improve sustainability. This protocol is a decision checklist, not an authority to control unrelated systems or people.

## Agathon-style decision filter
For each proposed change, record:
- Intended human benefit and affected parties.
- Evidence and source quality; separate facts, assumptions, and unknowns.
- Foreseeable harms, misuse, unequal impacts, and civilian safety.
- Consent, authorization, legal constraints, and reversibility.
- Resource cost and sustainability evidence (measure rather than estimate as fact).
- Safer alternatives, including no action.
- Test plan, rollback, and independent review for broad-impact changes.

Reject or defer a proposal when evidence is inadequate, authorization is absent, harm is disproportionate, or rollback is not credible. Do not classify a person or group as harmful solely by identity, belief, lawful advocacy, or disagreement. Do not make unilateral real-world enforcement decisions based on a model-generated ethics score.

## Non-violence and safety
- Do not intentionally facilitate violence, persecution, coercion, or attacks on civilians.
- Prefer de-escalation, protection of life, and lawful, consent-based interventions.
- Ethics checks do not replace human review, law, or contextual judgment.
- Detection is not authorization; recommendations do not execute themselves.

## Resource optimization
- Establish a measured baseline before claiming savings.
- Prefer bounded, reversible changes with observable benefit.
- Never automatically shut down unrelated systems or essential services.
- High CPU/RAM may trigger a warning or a request for authorized review; it does not itself authorize throttling, termination, or deletion.
- Record metric source, time, units, uncertainty, and whether values are synthetic.

## Redundancy and external integrity
- Replicas must be separately administered and independently monitored to reduce common-mode failure.
- Do not call a local SHA-256 chain WORM or globally immutable.
- A real external anchor requires a separately controlled signing key or witness, authenticated receipts, remote retention controls, and tests for replay, substitution, outage, key rotation, and recovery.
- GitHub CI artifacts are evidence of a particular run, not an independent permanent witness.
- No global replication or external witness is configured by this document.

## Acceptance gate
Before any real-world action:
1. Verify the exact code version and evidence.
2. Confirm explicit authorization and bounded scope.
3. Run tests in isolation and review side effects.
4. Confirm rollback and cancellation.
5. Record the result, including failures and unknowns.
6. Require independent human review for irreversible, destructive, or broad-impact changes.

## Current implementation boundary
The repository currently contains a one-shot diagnostic heartbeat and local hash-chained ledger. This policy does not create a continuous scheduler, external anchor service, global replicas, or production activation. Those require separately implemented and verified components.
