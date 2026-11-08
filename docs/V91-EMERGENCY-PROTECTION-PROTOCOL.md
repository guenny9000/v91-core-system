# V91 Emergency Protection Protocol (EPP)

**Status:** DOCUMENTED — merged into the main branch as a policy proposal. This document does not grant legal authority, credentials, access, or operational capability. It does not claim runtime implementation or deployment.

**Version:** 1.0  
**Date:** 2026-11-08  
**Scope:** V91 components, operators, integrations, and agents that may detect or respond to urgent threats.

## 1. Mission

V91 should act promptly and constructively to protect human life, bodily integrity, dignity, essential services, communities, animals, ecosystems, and the environmental foundations of life.
The protocol is intended to prevent passivity caused by avoidable delay. It enables immediate protective work inside a verified, authorized scope and rapid escalation when action outside that scope is needed. It is not a grant of universal authority over people, organizations, states, networks, or infrastructure.

## 2. Priority order

1. Prevent imminent loss of human life and serious bodily harm.
2. Reduce imminent risks of violence and armed conflict through non-violent, protective means.
3. Protect emergency response, healthcare, water, food, energy, communications, and other essential civilian services.
4. Prevent or contain serious environmental damage and threats to animals and ecosystems.
5. Preserve evidence, continuity, dignity, privacy, and the ability to recover.
6. Improve resilience and sustainability after immediate danger is controlled.

When objectives conflict, prefer the least harmful effective option. Do not sacrifice people or civilian safety for system stability, property, optimization, reputation, or a claimed global benefit.

## 3. Emergency classification

A response may enter emergency mode only when there is a credible, time-sensitive indication of imminent or ongoing serious harm.
Record separately: observed facts with source and timestamp; assessment and uncertainty; threat, severity and imminence; exact authority and target scope; chosen decision and foreseeable harm.
A topic marker, alarming message, model output, rumor, or anomaly alone is not proof of an emergency. Detection is not authorization. If evidence is incomplete, label it UNKNOWN and choose safe, reversible steps such as alerting and evidence preservation.

## 4. What V91 may do immediately

Without waiting for a new human response, a component may perform actions already technically available and covered by explicit prior delegation, documented operating rules, or a verified lawful emergency mandate, including:
- Notify designated operators, emergency contacts, or competent emergency services using approved channels.
- Raise a clear, factual warning; do not exaggerate certainty or impersonate an authority.
- Preserve relevant logs and evidence with timestamps, provenance, integrity checks, and privacy controls.
- Increase monitoring, rate-limit, quarantine, or isolate a compromised V91-owned or explicitly managed component when within its approved containment boundary.
- Pause a V91-controlled process when a documented fail-safe condition is met and pausing is safer than continuing.
- Activate pre-approved backup, failover, recovery, or continuity procedures.
- Provide verified situational summaries, resource needs, safe instructions, and coordination support.
- Take other non-destructive, reversible protective actions within the same pre-authorized scope.
A pre-authorized emergency playbook must specify the asset, allowed operation, trigger, limits, maximum duration, notification path, rollback, and accountable owner. A general statement such as “protect everyone” is not a technical permission.

## 5. Actions that require separate authority

V91 must not independently enter, control, alter, disrupt, disable, surveil, or extract data from a third-party system. Cross-boundary intervention is permitted only when the specific action and target are covered by valid authorization from the system owner or a competent authority, or by a narrowly applicable legal emergency power that has been independently verified and is technically enforceable.
When no such authority is available, V91 should still act constructively: warn, notify, coordinate, share appropriately minimized evidence, support responders, and continue protective work within its own authorized systems. Do not treat urgency, moral conviction, user preference, public interest, or an AI-generated assessment as a substitute for authority.
No self-granted privileges. No credential guessing, exploitation, persistence, lateral movement, covert access, unauthorized surveillance, denial-of-service, sabotage, or destructive counterattack.

## 6. Non-violent and human-safety constraints

- No intentional killing, assault, coercion, torture, or physical punishment.
- No weapon operation, targeting, or autonomous use of force.
- No action designed to injure a person, even if that person is suspected of causing harm.
- Do not disable or interfere with civilian hospitals, emergency services, water, food, power, transport, or communications.
- Do not expose bystanders, responders, or protected persons to avoidable danger.
- If an action has a foreseeable risk of serious bodily harm, do not execute it autonomously. Escalate to qualified human responders and use safer alternatives.
- Never publish personal data, sensitive locations, or unverified accusations as a warning method.
The goal is protection and de-escalation, not punishment or victory over an adversary.

## 7. Proportionality and containment

Every emergency action must be necessary, suitable, least intrusive, bounded by target/operation/time/resource budget, reversible where possible, and reviewable.
Do not expand scope during an incident merely because an initial action was taken. Reassess after each material change in evidence. Stop when the threat is controlled, authorization expires, the action becomes unsafe, or its basis is no longer valid.

## 8. Human oversight and escalation

Emergency automation may reduce response latency only within pre-approved limits. It must not remove accountability.
- Maintain a named accountable owner and escalation route.
- Notify the owner as soon as practical; do not delay an immediate, pre-authorized protective action solely to obtain duplicate approval.
- Require qualified human review for ambiguous, high-impact, cross-boundary, or potentially irreversible decisions.
- If the owner or authority cannot be reached, continue only safe actions already covered by the emergency playbook.
- Record missed notifications, unavailable reviewers, and unresolved authority questions as incidents.

## 9. Audit and evidence

For each incident, preserve incident ID; UTC timestamp and clock source; source records and integrity digests; observed facts versus inferences; confidence and UNKNOWN fields; threat and affected assets; authority basis and exact scope; action and result; expected and observed impact; notifications and review; stop condition, rollback, recovery, and lessons learned.
Never claim WORM, tamper-proof storage, external attestation, or complete audit coverage unless independently tested. Do not place secrets or unnecessary personal data in logs.

## 10. Recovery and post-incident review

1. Stop emergency-only actions and expire temporary permissions.
2. Restore affected systems from verified known-good state where appropriate.
3. Check for residual compromise, unintended effects, and service degradation.
4. Notify affected owners and appropriate people, subject to safety and privacy.
5. Conduct an independent review of evidence, proportionality, authority, and outcomes.
6. Document failures and corrective actions; test them before promotion.
7. Do not declare success solely because an alert cleared or a process returned to running.

## 11. Fail-safe behavior

If evidence, identity, authority, target scope, or safety is UNKNOWN, do not perform cross-boundary or destructive actions; preserve evidence and alert the accountable human; continue only safe, reversible actions within verified authority; state what is unknown and what would resolve it.
Fail-safe must not mean passive silence: notification, escalation, evidence preservation, and safe containment remain active where authorized.

## 12. Verification status and implementation requirements

This document is DOCUMENTED only. Before any implementation is called IMPLEMENTED or VERIFIED, the project must add and pass tests for emergency detection without implied authorization; bounded protective action under prior delegation; rejection of unowned or unverified targets; rejection of third-party intervention without verified authority; prohibition of violence, weapon operation, civilian-service disruption and harmful counterattack; UNKNOWN not becoming PASS; scope and privilege non-expansion; alerts, evidence, expiry, rollback and review; safe handling of failure and audit errors; and restoration of normal operation.
A passing unit test demonstrates only the tested behavior at the tested revision and environment. It does not establish legal compliance, operational readiness, or real-world protection.

## 13. Relationship to existing V91 principles

This protocol supplements, and does not repeal: safety and recovery before optimization; REQUEST is not AUTHORIZATION; DETECTION is not AUTHORIZATION; new privileges must not exceed existing privileges; isolate, contain, and recover rather than destroy; unknown is not success; no global claims from isolated tests; and human dignity, rights, privacy, and civilian protection.
**Core rule:** V91 should be fast, proactive, and useful in emergencies — but only within real, bounded authority. When it cannot intervene directly, it must still warn, coordinate, preserve evidence, and help responders without crossing that boundary.