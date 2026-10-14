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
2. Can an untrusted offer field claim that its own signature is verified? Is the trusted-verifier boundary clear and enforced by the public API?
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

The public `evaluate_signed_peer_offer()` path in `controller/cooperation.py` verifies an Ed25519 signature over canonical JSON and then applies the offer policy. The public `evaluate_peer_offer()` path has no signature inputs and therefore denies by default. The policy-only helper is private. This implementation does **not** discover peers, open network connections, exchange data, ingest peer content, train a model, execute remote commands, or deploy changes.

A valid signature proves possession of the corresponding private key for the signed bytes; it does not, by itself, establish that the key belongs to a particular trusted identity. Key distribution, identity binding, revocation, transport, and integration remain separate requirements.

The new `tests/test_crypto_verify.py` covers valid signatures, modified offers, invalid signatures, wrong keys, expired signed offers, unknown capabilities, and unserializable input. `tests/test_cooperation.py` also checks that the public unsigned entry point denies by default. Source code establishes implementation intent; only recorded test results establish that tests passed.

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

## 9. Current GitHub change — 2026-10-14

- PR #4 was closed as superseded by PR #5. Closing it did not merge either PR.
- PR #5 remains open, marked ready for review, and unmerged.
- The Ed25519 verification implementation and regression tests have been added to PR #5's branch.
- GitHub Actions run #75 completed successfully on exact head commit `8f8041c93017141a6696210c494ac04c8134b435`: https://github.com/guenny9000/v91-core-system/actions/runs/38562805691
- The implementation is **IMPLEMENTED / CI-VERIFIED** for the configured tests on that exact commit. Independent security review, trusted identity/key distribution, merge, and deployment remain outstanding.

**Core rule:** CLAIM ≠ EVIDENCE. REQUEST ≠ AUTHORIZATION. DETECTION ≠ AUTHORIZATION. When evidence or authority is missing, pause safely.
