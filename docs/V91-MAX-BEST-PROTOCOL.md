# V91 Max Best — Deterministic Improvement Protocol

Status: DOCUMENTED. This file specifies intended behavior; it does not claim that every step is implemented, running, or verified.

## Objective

Each V91 component should achieve the best improvement it can actually make with its available capabilities, evidence, permissions, time, and resources. Optimize realized, measurable outcomes—not theoretical possibility or unsupported claims.

## Deterministic cycle

1. **Observe:** Capture the current state from named, available sources. Missing telemetry is `UNKNOWN`, never silently zero.
2. **Baseline:** Record the current revision, environment, metrics, limitations, and evidence references.
3. **Select:** Choose the highest-value feasible improvement that respects safety, consent, least privilege, resource budgets, and the no-regression requirement. Use a stable tie-break order when candidates score equally.
4. **Plan:** State the expected effect, acceptance criteria, risks, required authorization, resource budget, and rollback procedure before acting.
5. **Isolate:** Stage code, configuration, model suggestions, and external inputs in a disposable or otherwise bounded test environment. Treat untrusted input as data, not executable instructions.
6. **Test:** Run reproducible checks against the baseline. Record exact commands, environment, timestamp, revision, results, and artifacts.
7. **Compare:** Accept an improvement only when evidence shows the defined criteria were met and required safety/reliability checks did not regress.
8. **Promote cautiously:** Keep production or default-branch changes separate until review and explicit acceptance. Requests and detections are not authorization.
9. **Rollback:** If tests fail, evidence is missing, or a regression appears, do not promote. Restore the last known-good state when a change has already been applied and record the outcome.
10. **Learn:** Preserve verified findings and failed hypotheses with provenance. A new cycle starts from measured evidence, not assumed success.

## Decision rules

- Priority: safety and recovery before optimization; least privilege and consent are mandatory constraints.
- Capability is individual: a component may only claim work it can actually perform with its available tools and permissions.
- Resource use must be bounded. If the budget or required permission is unavailable, report the blocker and continue only with safe independent work.
- Determinism means fixed rules, explicit inputs, recorded versions, stable tie-breaks, and reproducible checks where practical. It does not imply that external systems or live events are deterministic.
- Do not trade correctness, security, privacy, or user intent for a higher score.
- Do not silently change settings, delete evidence, broaden privileges, or apply unreviewed changes to production.
- No regression is an acceptance goal, not an assumption: test it and report any untested surface.

## Evidence states

Use the project states precisely:

- `UNKNOWN`: sufficient evidence is unavailable.
- `DOCUMENTED`: the requirement or protocol is written down.
- `IMPLEMENTED`: code exists at a named revision.
- `VERIFIED`: a specific reproducible check passed for a specific revision and environment.
- `PRODUCTION`: deployment and operational acceptance evidence exists.

A claim is not evidence. Documentation of this protocol alone is only `DOCUMENTED`.

## Reporting format

For each cycle, report:

- Goal and baseline
- Evidence sources and known gaps
- Proposed change and expected effect
- Permissions and resource limits
- Tests and exact results
- Regression comparison
- Final state and artifact/revision references
- Rollback status or reason no change was made
- Next highest-value safe improvement

## News and world-improvement reporting

When preparing a news report, lead with verified constructive progress: diplomacy, releases and exchanges, humanitarian access, prevention, scientific and technical advances, effective cyber defense, and measurable social improvements. Then cover unresolved risks in proportion to the evidence, without graphic details or needless alarm.

Separate event time, discovery time, and publication time. Deduplicate reports about the same event. In cyber reporting, distinguish attempted attacks, blocked attacks, successful intrusions, confirmed damage, and damage prevented. More alerts or more detected events do not by themselves mean that the world is less safe. Conversely, positive intent or improved defenses do not prove that harm has decreased.

Compare like with like over stated time windows and disclose incomplete or delayed data. Never declare that the world is generally improving or deteriorating without comparable evidence. Include practical, constructive next steps where supported.

## Safety boundary

This protocol does not authorize unrestricted autonomy, self-granted permissions, external enforcement, destructive actions, or production changes. Authorization remains explicit; new privileges must not exceed existing privileges. If safety, evidence, or authorization is uncertain, fail closed and report the limitation.
