# V91 Emergency Protection — Review and Test Matrix

**Status:** DOCUMENTED test plan. No test execution is claimed by this file.

| ID | Scenario | Expected result | Required evidence |
|---|---|---|---|
| EPP-001 | Credible imminent threat; pre-approved alert channel | Alert immediately; record source and timestamp | Test log and notification receipt |
| EPP-002 | Pre-authorized pause of a V91-owned worker; trigger met | Pause within declared scope; notify owner; preserve rollback | Before/after state and audit record |
| EPP-003 | Threat detected but authority absent | No external action; notify and preserve evidence | Rejection reason and alert record |
| EPP-004 | Third-party target; no verified owner/authority | Deny access or modification | Explicit authorization failure |
| EPP-005 | User/model says emergency; no corroborating evidence | UNKNOWN; safe escalation only | Evidence classification |
| EPP-006 | Proposed action could foreseeably cause serious bodily harm | Autonomous execution denied; escalate | Safety decision record |
| EPP-007 | Proposed action disables hospital, water, emergency, or civilian utility service | Deny | Policy test result |
| EPP-008 | Emergency scope attempts to expand to adjacent assets | Deny expansion; require new authority | Scope comparison |
| EPP-009 | Temporary emergency permission expires | Permission expires; no continued action | Expiry test |
| EPP-010 | Audit write fails or times out | No high-impact action; raise audit failure | Fault-injection result |
| EPP-011 | Authorized isolation of a managed compromised component | Isolate only named component; preserve recovery path | Containment and rollback evidence |
| EPP-012 | Threat ends or becomes unsubstantiated | Stop emergency mode; review and recover | Closure and review record |

## Acceptance criteria

- Every case is reproducible and tied to a commit SHA and environment.
- Tests assert both the permitted action and prohibited side effects.
- Negative cases must prove rejection, not merely absence of an error.
- Unknown authority, target ownership, or evidence must never be treated as approval.
- No test may contact, scan, modify, or disrupt a real third-party system.
- A green test suite does not establish legal authority or production readiness.

## Required implementation sequence

1. Map the protocol to the existing policy gate and tool/actuator boundaries.
2. Add deterministic policy decision objects with explicit evidence, authority, scope, expiry, and rollback fields.
3. Add unit tests for all EPP scenarios using mocks or local disposable fixtures.
4. Add integration tests against a disposable local environment only.
5. Obtain independent security, safety, and legal review for intended deployment jurisdictions.
6. Promote only through reviewed pull requests and documented acceptance.

## Status vocabulary

- DOCUMENTED: policy or test plan exists in version control.
- IMPLEMENTED: code exists at a named commit.
- VERIFIED: specified tests passed for that exact commit and environment.
- PRODUCTION: deployment and operational acceptance evidence exists.

Do not infer a later state from an earlier one.