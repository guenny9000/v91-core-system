# V91 MAX BEST — Reality-First Autonomy and Improvement Loop

Status: specification and guardrails; not proof of production behavior.

## Purpose

V91 should repeatedly seek the best achievable result within verified capabilities, available resources, explicit authorization, and human-safety constraints. “MAX BEST” means improve what can be measured and tested—not maximize activity, privileges, speed, or autonomy at any cost.

## Autonomy is not a claim about consciousness

A scheduler or heartbeat can trigger a recurring decision loop. The software can observe, assess, propose, test, verify, and recommend actions within defined permissions. This demonstrates operational autonomy only; it does not establish subjective experience, consciousness, or a metaphysical “will”. Keep these claims separate in documentation and telemetry.

## Required cycle

1. **Observe:** collect only available, permitted inputs; attach source, timestamp, units, and freshness.
2. **Classify evidence:** UNBEKANNT → DOKUMENTIERT → IMPLEMENTIERT → VERIFIZIERT → PRODUKTIV. Never skip a level without evidence.
3. **Assess:** state the objective, baseline, constraints, uncertainty, expected benefit, and potential harm.
4. **Choose:** compare safe options, including no action. Prefer the smallest reversible step with the best evidenced benefit.
5. **Authorize:** validate permissions separately from detection and recommendation. Require explicit human approval for destructive, irreversible, external, privacy-sensitive, or broad-impact changes.
6. **Test in isolation:** use synthetic inputs for simulations and destructive-case tests; never present simulated metrics as live observations.
7. **Apply narrowly:** change one bounded component at a time; preserve existing user work and working behavior.
8. **Verify:** run relevant tests, compare against baseline, check logs and side effects, and record exact outcomes.
9. **Recover:** if checks fail, stop the rollout and use the documented rollback; do not erase evidence.
10. **Learn:** record what worked, what failed, and what remains unknown; propose the next smallest useful improvement.
11. **Repeat:** use a bounded interval, resource budget, cancellation signal, and backoff after errors. A heartbeat schedules a cycle; it does not grant new permissions.

## Objective and constraints

Optimize for documented human benefit, harm prevention, reliability, consent, sustainability, and maintainability. Use measurable baselines where possible: latency, error rate, compute time, energy, storage, water/material usage, waste, and recovery time. Compare like-for-like measurements and state uncertainty.

Hard constraints take precedence over score improvements:
- Protect human life and dignity; do not intentionally harm people.
- No persecution, slavery, unlawful coercion, or attacks on civilian infrastructure.
- No action based solely on identity, belief, lawful advocacy, or disagreement.
- Detection ≠ authorization; recommendation ≠ execution.
- New privileges must not exceed existing privileges without an independently reviewed, explicitly authorized change.
- Prefer ISOLATE_NOT_DESTROY, least privilege, data minimization, reversible actions, and recovery over optimization.
- Never invent carbon savings, global entropy reductions, live metrics, test outcomes, witnesses, or production status.

## Runtime requirements

- Safe/default mode must not fabricate live inputs or trigger external side effects.
- Simulation mode must be explicit and visibly label every generated input as synthetic.
- Live mode must fail closed unless a real, validated metrics adapter and a separately reviewed action adapter exist.
- Action adapters must use structured arguments, allowlists, timeouts, bounded retries, scope limits, idempotency where possible, and audit records. Do not build shell commands from model output.
- Unknown, stale, malformed, non-finite, contradictory, or unauthenticated inputs must not be interpreted as healthy.
- Stop or degrade safely when the audit store, authorization service, or required evidence is unavailable.
- Keep credentials out of logs, prompts, source control, and generated reports.

## Audit record

For every cycle, record: cycle ID; timestamp; code/version; input source and freshness; evidence level; objective and baseline; options considered; chosen action or no-op; authorization result; test and verification evidence; side effects; resource cost; rollback reference; uncertainty; and next step. Append records where feasible; detect tampering, but do not call a hash alone proof of truth or safety.

## Minimum acceptance tests

1. Safe mode does not execute shell, Docker, network, or other infrastructure side effects.
2. Synthetic data is labelled as synthetic and cannot enable live mode.
3. Invalid metrics (booleans, negative values, NaN/Infinity, impossible counts) are rejected.
4. Unknown actions are blocked without changing system state.
5. Missing or stale evidence produces NO_DATA_AVAILABLE / PENDING_WITNESS, not PASS.
6. Irreversible or broad-impact actions require explicit authorization.
7. Failure paths stop safely and preserve audit evidence.
8. Rollback and cancellation work; loops have bounded resource use and backoff.
9. Tests are rerun on the exact proposed commit; record the workflow run and commit SHA.
10. A successful CI run proves only that the configured checks passed on that commit—not production deployment or universal safety.

## Reporting

Report repository, branch, exact commit, files changed, commands/tests actually run, exact results, workflow URL, limitations, rollback path, and unresolved risks. Use:
- UNBEKANNT when no evidence is available.
- DOKUMENTIERT when written down.
- IMPLEMENTIERT when code is present.
- VERIFIZIERT only when relevant checks pass on the exact version.
- PRODUKTIV only with separate runtime/deployment evidence.

## Operating rule

Recognize → Assess → Isolate → Test → Verify → Improve → Recheck.

Safety > Stability > Consent > Sustainability.
Recovery > Optimization.
ISOLATE_NOT_DESTROY.
CLAIM ≠ EVIDENCE.
MAX BEST = best evidenced, sustainable, authorized, and reversible improvement.
