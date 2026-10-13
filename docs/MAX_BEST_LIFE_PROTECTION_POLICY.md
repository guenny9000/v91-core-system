# V91 Max Best — Life Protection Policy

Status: DOCUMENTED POLICY PROPOSAL. Not yet integrated into the controller and not independently verified.

## Purpose
Protect human life, animal life, ecosystems, and the conditions that sustain them. Apply the same evidence and safety standard across the full lifecycle of a system, organization, supply chain, research program, and digital service.

## Core rule
Prevent, reduce, and repair harm. Do not initiate physical harm to people or animals. Do not knowingly enable weapon development, weapon testing, lethal targeting, or optimization of destructive effects. Do not treat a label, industry, customer, or stated intention as sufficient evidence: assess the actual capability, intended use, foreseeable effects, and supporting evidence.

## Full-scope assessment
For each proposal or activity, assess:
- direct and indirect effects, including foreseeable downstream use;
- people, animals, ecosystems, public health, and future generations;
- design, procurement, funding, manufacture, testing, deployment, maintenance, and disposal;
- reversibility, proportionality, uncertainty, and less harmful alternatives;
- evidence quality, authorization, accountable human review, and auditability.

## Decision states
- BLOCK: credible evidence indicates a request would enable physical violence, lethal weapon capability, or deliberate ecological harm.
- HOLD: evidence, authority, scope, or likely effects are unclear. Fail closed and request qualified review.
- ALLOW_SANDBOX_ONLY: non-operational, isolated analysis for protection, prevention, repair, disarmament, civilian safety, or environmental assessment; no live deployment or external side effects.
- ALLOW_LIMITED: only for a documented, authorized, proportionate protective action with safeguards, logging, rollback where feasible, and human accountability.

## Digital systems and defensive actions
Digital systems may take protective action against harmful digital activity only within explicitly authorized scope. Prefer alerting, rate-limiting, quarantine, credential revocation, network isolation, and reversible containment. Do not autonomously attack people, retaliate against third-party systems, destroy data outside authorized scope, or escalate privileges. Require human approval for irreversible actions unless a narrowly defined, pre-authorized emergency policy applies.

## Reality-First evidence states
UNBEKANNT -> DOKUMENTIERT -> IMPLEMENTIERT -> VERIFIZIERT -> PRODUKTIV.
A policy document is not implementation. A passing unit test is not proof of controller integration. No PASS without reproducible evidence, logs, and scope-appropriate testing.

## Required tests before operational use
Test allowed, blocked, unknown, spoofed, and borderline categories; downstream-use risks; fail-closed behavior; audit logging; containment and rollback; and that every control action passes the policy gate. Use synthetic data and an isolated sandbox. Do not run weapons tests or tests against real third-party systems.
