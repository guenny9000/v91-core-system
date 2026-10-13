# V91 MAX BEST RAGNARÖK — Proactive, Life-Preserving Cleanup Protocol

Status: implemented as a bounded policy and decision workflow. This document does not grant authority over third-party systems and does not claim global deployment.

## 1. Purpose

Proactively find and reduce demonstrable waste, avoidable harm, brittle dependencies, opaque decisions, and unnecessary resource use while protecting life, dignity, nature, and essential services. "Ragnarök" means orderly renewal and cleanup—not destruction, coercion, or indiscriminate deletion.

## 2. Proactive operating loop

For each authorized repository, service, process, or resource within the operator's scope:

1. OBSERVE — collect available evidence without changing the target.
2. CLASSIFY — mark each item DOCUMENTED, IMPLEMENTED, VERIFIED, PRODUCTIVE, or UNKNOWN. A claim is not evidence.
3. PRIORITIZE — rank candidate improvements by expected life/safety benefit, measured waste reduction, confidence, reversibility, cost, and risk.
4. PROPOSE — produce a small, bounded change with rationale, evidence, expected effect, and affected scope.
5. ISOLATE — test against fixtures, snapshots, or a sandbox before touching a live target.
6. REVIEW — check authorization, privacy, environmental effects, essential-service impact, and safer alternatives.
7. APPLY — only after explicit authorization for the exact target and action. The default is recommendation-only.
8. VERIFY — compare before/after measurements, run regression tests, inspect logs, and record failures and unknowns.
9. RECOVER — if a check fails or harm is plausible, stop further changes, preserve evidence, and use the documented rollback.
10. LEARN — retain lessons and create a new proposal; never silently broaden permissions.

A cycle may stop safely at any stage. No change is preferable to an unsupported or irreversible change.

## 3. Hard safety constraints

- Protect people and other living systems; prioritize prevention of severe, foreseeable harm.
- No violence, persecution, intimidation, coercion, or targeting people by identity, belief, or lawful disagreement.
- Detection is not authorization. A model score is not legal authority.
- Never automatically delete data, cancel debts, shut down essential services, disable safety systems, or alter third-party infrastructure based on a general ethical or efficiency judgment.
- Respect consent, applicable law, privacy, ownership, and least privilege.
- Preserve the original state, evidence, and recovery path before approved modifications.
- Stop and request human review for irreversible, broad-impact, uncertain, or conflicting actions.

## 4. Nature and sustainability checks

Before claiming an improvement, define the baseline and measurement window. Prefer measured reductions in energy, water, material use, waste, emissions, failure rates, or avoidable compute while checking that costs are not merely shifted elsewhere. Record source, units, timestamp, uncertainty, system boundary, and method. If a measurement is unavailable, report NO_DATA_AVAILABLE; do not invent a percentage or call the result a verified saving.

Prefer repair, reuse, longevity, interoperability, regional resilience, and circular material flows where evidence supports them. Include trade-offs and lifecycle effects; do not assume that a product, process, or energy source is sustainable solely by label.

## 5. Anti-waste and transparency review

Candidate review areas may include duplicated jobs, unused resources, repeated data, brittle dependencies, avoidable idle compute, unnecessary storage, opaque approval paths, and weak auditability. These are investigation categories—not proof of wrongdoing. Do not label a person, organization, expense, debt, product, or policy "destructive" without evidence and appropriate context. Economic or political changes require legitimate decision processes and cannot be executed by this repository.

## 6. Evidence and audit record

Each proposed or performed change should record:

- unique event ID and UTC timestamp;
- repository/target, exact version, and authorized scope;
- evidence references and baseline;
- classification of facts, assumptions, and unknowns;
- expected benefit, possible harm, resource cost, and alternatives;
- approval reference, test results, actual before/after measurements;
- rollback method and result;
- outcome: PROPOSED, BLOCKED, TESTED, VERIFIED, ROLLED_BACK, or NO_DATA_AVAILABLE.

Never mark a proposal VERIFIED or PRODUCTIVE solely because a script returned success. Preserve failure details. A local hash chain detects certain changes but is not, by itself, WORM or an independent witness.

## 7. Autonomy levels

- LEVEL 0 — observe and report.
- LEVEL 1 — propose changes with evidence.
- LEVEL 2 — test in an isolated environment.
- LEVEL 3 — apply a pre-authorized, reversible action to a named target and verify it.
- LEVEL 4 — broader operation only with explicit scoped authorization, independent review, monitoring, and tested recovery.
- No global or unlimited autonomy is implied. Privileges may not increase implicitly. Live changes remain blocked until a concrete, reviewed adapter and authorization mechanism exist.

## 8. Current repository boundary

The existing V91 code includes a one-shot diagnostic heartbeat, local hash-chained ledger, read-only host CPU/RAM sampling, tests, and a GitHub Actions test workflow. This policy adds a proactive review and evidence standard; it does not itself create a continuous scheduler, inspect the user's computer, control other agents, clean global systems, deploy external WORM storage, or prove environmental benefits.

## 9. Acceptance criteria for a future executable planner

A planner can be considered implemented only when it:
- reads a bounded, explicitly configured target list;
- produces proposals without side effects by default;
- rejects missing authorization and unknown states;
- records evidence and a rollback plan;
- runs only isolated tests unless separately authorized;
- has tests proving that prohibited actions do not execute;
- reports measured outcomes without fabricating metrics;
- can be paused and recovers safely after errors.

Production status requires the exact commit, successful CI, reviewed diff, and evidence from the actual target environment.
