# V91 Cross-Validation Learning Block — MAX BEST

**Purpose:** Let independent models and reviewers examine the same implementation, challenge assumptions, and report reproducible findings. This is a review protocol, not proof that any model has learned permanently or that production deployment occurred.

## 1. Reality-first state labels

Use these labels precisely:

- **UNKNOWN** — no reliable evidence yet.
- **DOCUMENTED** — described in text; not proof of implementation.
- **IMPLEMENTED** — code or configuration exists at a named revision.
- **VERIFIED** — a named test/check ran against a named revision and its result is available.
- **PRODUCTION** — deliberately deployed with authorization, monitoring, and rollback.

Never promote a state based on wording alone. A passing CI run proves only the checks that actually ran on that commit. A hash is a fingerprint, not a signature, independent witness, or immutable storage guarantee.

## 2. Evidence to provide to each reviewer

Give each independent reviewer the same:
1. Repository and pull-request URL.
2. Exact commit SHA being reviewed.
3. Full changed-file diff and relevant surrounding code.
4. Unit-test files and exact CI run link, including job results.
5. The claims being checked, separated from evidence.

If any item is unavailable, mark it **UNKNOWN** rather than reconstructing or guessing it.

## 3. Review questions

Ask each reviewer to independently answer:

1. Does the evaluator deny by default when signature verification, explicit consent, supported protocol, peer identity, expiry, or an allowed capability is missing or invalid?
2. Can an untrusted offer field claim that its own signature is verified? Is the trusted-verifier boundary clear and enforced by the caller?
3. Are unknown capabilities and forbidden actions denied, including remote execution, writing, installation, administration, control, and private-data access?
4. Are malformed types, booleans used as integers, expired offers, and unavailable system time handled safely?
5. Do audit records avoid copying private payloads and avoid claiming that data ingestion or remote actions occurred when they did not?
6. Do tests exercise the actual code path, and do the tests cover both allowed and denied cases?
7. Are workflow permissions minimal? Are third-party actions pinned or otherwise controlled according to the repository's security policy?
8. Does the documentation distinguish implemented behavior from planned behavior?
9. What is the smallest reproducible counterexample or missing test that could disprove a claim?
10. What should remain blocked until independent verification and explicit deployment authorization?

## 4. Required response format

Each reviewer must return:

- **Commit reviewed:** exact SHA or UNKNOWN
- **Evidence inspected:** links/paths and test names
- **Findings:** each tagged CONFIRMED, POTENTIAL, or UNKNOWN
- **Severity:** BLOCKER, HIGH, MEDIUM, LOW, or NONE, with a reason
- **Reproduction:** exact test, command, input, and observed result; if not run, say NOT RUN
- **Suggested correction:** smallest safe change
- **Decision:** PASS FOR NEXT REVIEW, CHANGES REQUIRED, or INSUFFICIENT EVIDENCE
- **Limitations:** what was not inspected or could not be executed

Do not award PASS because another reviewer said PASS. A second model's agreement is another opinion, not independent execution evidence.

## 5. Cross-validation procedure

1. Freeze the commit SHA under review; if the branch changes, restart review against the new SHA.
2. Have at least two reviewers inspect independently before seeing each other's conclusions.
3. Compare findings and map each claim to a file, test, CI job, or other reproducible evidence.
4. Reproduce disputed findings with tests or a minimal example. Do not report tests as run unless they were actually executed.
5. Convert valid findings into regression tests before or alongside a fix.
6. Re-run the full relevant test suite and CI on the final candidate commit.
7. Keep unresolved blockers open. Record disagreements and uncertainty instead of voting them away.
8. Require an authorized human review before merge or deployment; this block does not authorize either action.

## 6. Current implementation boundary for the cooperative handshake

The evaluator in controller/cooperation.py checks a declared offer and returns a policy decision. It does **not** itself discover peers, open network connections, verify cryptographic signatures, exchange data, ingest peer content, train a model, execute remote commands, or deploy changes. The caller must use a trusted cryptographic verifier and pass its result safely; a peer-supplied boolean is not evidence.

The unit tests in tests/test_cooperation.py cover several allow/deny conditions, expiry handling, the default clock path, unavailable clock behavior, and minimal audit-record fields. Test names and source code are documented evidence of coverage intent; only recorded test results establish that a test run passed.

## 7. Safe learning and data handling

- Use public, licensed, or explicitly authorized test data only.
- Do not send secrets, credentials, personal data, or private peer payloads to reviewers.
- Keep examples synthetic and minimize retained data.
- Validate proposed learning inputs in an isolated, reversible sandbox before any future ingestion.
- Treat model-generated recommendations as proposals, not commands or authorization.
- Prefer a small patch, regression test, and documented rollback over broad automated changes.
- Never scan, connect to, alter, or clean up an external system without explicit scoped authorization.

## 8. Acceptance gate

A change is ready for the next review only when the exact commit is identified, relevant tests and CI results are recorded, critical findings are resolved, and the remaining limitations are stated. Merge and production deployment remain separate, explicitly authorized decisions.

**Core rule:** CLAIM ≠ EVIDENCE. REQUEST ≠ AUTHORIZATION. DETECTION ≠ AUTHORIZATION. When evidence or authority is missing, pause safely.
